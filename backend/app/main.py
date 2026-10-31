import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models, schemas, transcriber
from .database import Base, engine, get_db

SR = transcriber.SAMPLE_RATE
# Live previews re-run Whisper every N seconds of new audio. That needs far more CPU than
# Render's free plan has (0.15 CPU, ~7-15 s per run), so they are off by default (0) and the
# whole recording is transcribed once when the user presses Stop. Set e.g. 1.5 on a bigger box.
PARTIAL_EVERY_SEC = float(os.getenv("PARTIAL_EVERY_SEC", "0"))
MAX_UTTERANCE_SEC = 15      # force-finalise long utterances
SILENCE_TAIL_SEC = 0.8      # trailing silence that ends an utterance
SILENCE_RMS = 0.01


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if os.getenv("SKIP_MODEL_LOAD") != "1":
        await asyncio.to_thread(transcriber.load_model)  # warm up so first request is fast
    yield


app = FastAPI(title="Speech to Text API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok", "model": transcriber.MODEL_SIZE}


# ------------------------------ CRUD ------------------------------
@app.post("/api/transcriptions", response_model=schemas.TranscriptionOut, status_code=201)
def create(payload: schemas.TranscriptionCreate, db: Session = Depends(get_db)):
    title = payload.title.strip() or (payload.text.strip()[:40] or "Untitled")
    row = models.Transcription(title=title, text=payload.text.strip(),
                               language=payload.language,
                               duration_seconds=payload.duration_seconds)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.get("/api/transcriptions", response_model=List[schemas.TranscriptionOut])
def list_all(q: Optional[str] = None, skip: int = 0,
             limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    query = db.query(models.Transcription)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(models.Transcription.text.ilike(like),
                                 models.Transcription.title.ilike(like)))
    return query.order_by(models.Transcription.created_at.desc(),
                          models.Transcription.id.desc()).offset(skip).limit(limit).all()


@app.get("/api/transcriptions/{item_id}", response_model=schemas.TranscriptionOut)
def get_one(item_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Transcription, item_id)
    if not row:
        raise HTTPException(404, "Transcription not found")
    return row


@app.put("/api/transcriptions/{item_id}", response_model=schemas.TranscriptionOut)
def update(item_id: int, payload: schemas.TranscriptionUpdate, db: Session = Depends(get_db)):
    row = db.get(models.Transcription, item_id)
    if not row:
        raise HTTPException(404, "Transcription not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@app.delete("/api/transcriptions/{item_id}", status_code=204)
def delete(item_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Transcription, item_id)
    if not row:
        raise HTTPException(404, "Transcription not found")
    db.delete(row)
    db.commit()


# ------------------------ Real-time WebSocket ------------------------
def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


@app.websocket("/ws/transcribe")
async def ws_transcribe(ws: WebSocket):
    """
    Protocol
      client -> server : text  {"type":"config","language":"auto|en|hi|hinglish"}
                         bytes raw PCM int16 mono 16kHz (little-endian)
                         text  {"type":"stop"}
      server -> client : {"type":"partial","text":...}  live hypothesis (only if PARTIAL_EVERY_SEC > 0)
                         {"type":"final","text":...,"language":...}  committed utterance
                         {"type":"done"}

    Transcription never runs inside the receive loop, so a slow CPU can't make audio
    (or the Stop message) queue up behind it: at most one background run at a time,
    and Stop triggers exactly one final run over whatever audio is still pending.
    """
    await ws.accept()
    mode = "auto"
    chunks: List[np.ndarray] = []   # pending (not yet finalised) audio
    pending = 0                     # samples in `chunks`
    new_samples = 0                 # samples since the last background run started
    speech_seen = False             # any loud-enough sample since the last reset
    task: Optional[asyncio.Task] = None

    def audio() -> np.ndarray:
        nonlocal chunks
        if len(chunks) > 1:
            chunks = [np.concatenate(chunks)]
        return chunks[0] if chunks else np.zeros(0, dtype=np.float32)

    def tail(n: int) -> np.ndarray:
        out, got = [], 0
        for c in reversed(chunks):
            out.append(c)
            got += len(c)
            if got >= n:
                break
        return np.concatenate(out[::-1])[-n:] if out else np.zeros(0, dtype=np.float32)

    def drop(n: int):
        """Remove the first n samples (they've been finalised)."""
        nonlocal chunks, pending, speech_seen
        rest = audio()[n:]
        chunks = [rest] if len(rest) else []
        pending = len(rest)
        speech_seen = pending > 0 and float(np.abs(rest).max()) > 0.05

    async def background(snapshot: np.ndarray, final: bool):
        try:
            text, lang = await asyncio.to_thread(transcriber.transcribe, snapshot, mode)
            if final:
                drop(len(snapshot))
                if text:
                    await ws.send_json({"type": "final", "text": text, "language": lang})
            elif text:
                await ws.send_json({"type": "partial", "text": text, "language": lang})
        except Exception as exc:
            try:
                await ws.send_json({"type": "error", "message": str(exc)})
            except Exception:
                pass

    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("text") is not None:
                data = json.loads(msg["text"])
                if data.get("type") == "config":
                    mode = data.get("language", "auto")
                elif data.get("type") == "stop":
                    if task and not task.done():
                        await task              # can't cancel a running thread; let it finish
                    if pending >= SR * 0.4:
                        text, lang = await asyncio.to_thread(transcriber.transcribe, audio().copy(), mode)
                        if text:
                            await ws.send_json({"type": "final", "text": text, "language": lang})
                    await ws.send_json({"type": "done"})
                    break
                continue

            chunk = np.frombuffer(msg["bytes"], dtype=np.int16).astype(np.float32) / 32768.0
            if not len(chunk):
                continue
            chunks.append(chunk)
            pending += len(chunk)
            new_samples += len(chunk)
            if float(np.abs(chunk).max()) > 0.05:
                speech_seen = True

            busy = task is not None and not task.done()
            if not speech_seen and pending > 3 * SR and not busy:   # long silence: drop it
                chunks, pending, new_samples = [], 0, 0
                continue

            if PARTIAL_EVERY_SEC > 0 and not busy and new_samples >= PARTIAL_EVERY_SEC * SR \
                    and pending >= SR * 0.4:
                tail_silent = _rms(tail(int(SILENCE_TAIL_SEC * SR))) < SILENCE_RMS
                too_long = pending >= MAX_UTTERANCE_SEC * SR
                new_samples = 0
                task = asyncio.create_task(
                    background(audio().copy(), final=(speech_seen and tail_silent) or too_long))
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # report and close cleanly
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass


# --------------------- Serve built React frontend ---------------------
_here = Path(__file__).resolve().parent
FRONTEND_DIR = None
for candidate in (_here.parent / "frontend_dist", _here.parent.parent / "frontend" / "dist"):
    if (candidate / "index.html").exists():
        FRONTEND_DIR = candidate
        break

if FRONTEND_DIR:
    if (FRONTEND_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith(("api/", "ws/")):
            raise HTTPException(404)
        file = FRONTEND_DIR / full_path
        if full_path and file.is_file():
            return FileResponse(file)
        return FileResponse(FRONTEND_DIR / "index.html")
