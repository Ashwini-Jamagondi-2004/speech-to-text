# 🎙️ Speech → Text (Hindi + English) — Real-time Transcription

Web app that transcribes multilingual speech (Hindi, English, Hinglish) in near real time and stores every
transcription in PostgreSQL, with a dashboard for full CRUD + search.

**Stack:** React (Vite) · FastAPI · [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) (open source, self-hosted) · PostgreSQL · SQLAlchemy · Docker

## How the real-time part works
1. Browser captures mic audio with an `AudioWorklet`, downsamples to 16 kHz PCM16.
2. PCM chunks stream over a **WebSocket** (`/ws/transcribe`).
3. The server buffers the current utterance and re-transcribes it every ~1.5 s → **partial** (grey) text.
4. After ~0.8 s of silence (or 15 s of speech) the utterance is committed → **final** text.
5. On *Stop*, the full transcript is saved to the database and shows up in History.

> This is chunked near-real-time transcription (~1–3 s latency on CPU), not true word-by-word streaming.

**Language modes:** Auto-detect · Hinglish (Roman script, Hindi language + romanised prompt) · Hindi · English.

## Features
- Live transcription with partial/final text, mic start/stop, language selector
- History dashboard: **Create** (auto-save after recording, or manual add) · **Read** (list, search) · **Update** (edit modal) · **Delete**
- REST API with Swagger docs at `/docs`
- Tests (`pytest`) for CRUD + WebSocket flow

## REST API
| Method | Path | Description |
|---|---|---|
| POST | `/api/transcriptions` | create |
| GET | `/api/transcriptions?q=&skip=&limit=` | list / search |
| GET | `/api/transcriptions/{id}` | read one |
| PUT | `/api/transcriptions/{id}` | update title/text |
| DELETE | `/api/transcriptions/{id}` | delete |
| WS | `/ws/transcribe` | live audio stream |

## Run locally

### Option A — Docker (app + PostgreSQL)
```bash
docker compose up --build
# open http://localhost:8000   (mic works on localhost)
```

### Option B — Manual (Windows / Mac / Linux)
```bash
# 1) Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # optional; default DB is SQLite
# PostgreSQL: set DATABASE_URL=postgresql://user:pass@localhost:5432/speech_db
uvicorn app.main:app --reload --port 8000
```
First start downloads the Whisper model (~150 MB for `base`).
```bash
# 2) Frontend (new terminal)
cd frontend
npm install
npm run dev                      # http://localhost:5173
```
Tests: `cd backend && pytest`

## Deploy (Render)
1. Push this repo to GitHub.
2. Render → **New → Blueprint** → select the repo (uses `render.yaml`: Docker web service + PostgreSQL).
3. Wait for build; open the `https://….onrender.com` URL (HTTPS is required for microphone access).

Live previews: `PARTIAL_EVERY_SEC` (default `0` = off, the recording is transcribed once on Stop; set `1.5` on a machine with at least 1 CPU). `WHISPER_THREADS` defaults to `1`.

Model size tip: `WHISPER_MODEL=tiny|base|small`. `base` needs ~1 GB RAM in practice; use `tiny` on 512 MB plans.
Accuracy for Hindi improves noticeably with `small`.

## Project layout
```
backend/app   main.py (API + WebSocket) · transcriber.py (Whisper) · models.py · schemas.py · database.py
backend/tests pytest suite
frontend/src  Recorder.jsx (live mic) · History.jsx (CRUD dashboard) · api.js
Dockerfile · docker-compose.yml · render.yaml
```

## Known limitations / next steps
- No auth: history is global. Add user accounts + per-user rows for production.
- Partial results re-transcribe the current utterance, so CPU load grows with speakers; a GPU or streaming model (e.g. whisper-streaming) would improve latency.
- Code-switching within one sentence is best-effort; try *Hinglish* mode for Roman-script output.
