import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SKIP_MODEL_LOAD"] = "1"

import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app import transcriber


def test_crud_flow():
    with TestClient(app) as c:
        r = c.post("/api/transcriptions", json={"text": "नमस्ते, let's start the meeting", "language": "hi"})
        assert r.status_code == 201
        item = r.json()
        assert item["title"].startswith("नमस्ते")

        assert any(i["id"] == item["id"] for i in c.get("/api/transcriptions?q=meeting").json())
        assert c.get("/api/transcriptions?q=zzzz").json() == []

        r = c.put(f"/api/transcriptions/{item['id']}", json={"title": "Standup", "text": "edited"})
        assert r.json()["title"] == "Standup" and r.json()["text"] == "edited"

        assert c.delete(f"/api/transcriptions/{item['id']}").status_code == 204
        assert c.get(f"/api/transcriptions/{item['id']}").status_code == 404


def test_websocket_stream(monkeypatch):
    monkeypatch.setattr(transcriber, "transcribe", lambda audio, mode="auto": ("hello namaste", "hi"))
    tone = (np.sin(np.linspace(0, 800 * np.pi, 16000 * 2)) * 0.3 * 32767).astype(np.int16)
    silence = np.zeros(16000, dtype=np.int16)
    with TestClient(app) as c, c.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"type": "config", "language": "hinglish"})
        for i in range(0, len(tone), 4000):
            ws.send_bytes(tone[i:i + 4000].tobytes())
        for i in range(0, len(silence), 4000):
            ws.send_bytes(silence[i:i + 4000].tobytes())
        ws.send_json({"type": "stop"})
        types = []
        while True:
            m = ws.receive_json()
            types.append(m["type"])
            if m["type"] == "done":
                break
        assert "final" in types
