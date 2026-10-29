import { useRef, useState } from "react";
import { api } from "./api.js";

const LANGS = [
  { value: "auto", label: "Auto-detect (Hindi + English)" },
  { value: "hinglish", label: "Hinglish (Roman script)" },
  { value: "hi", label: "Hindi (हिन्दी)" },
  { value: "en", label: "English" },
];

// Downsample Float32 @ any rate -> Int16 @ 16 kHz
function toInt16At16k(f32, inRate) {
  const ratio = inRate / 16000;
  const outLen = Math.floor(f32.length / ratio);
  const out = new Int16Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.max(start + 1, Math.min(Math.floor((i + 1) * ratio), f32.length));
    let sum = 0;
    for (let j = start; j < end; j++) sum += f32[j];
    const s = Math.max(-1, Math.min(1, sum / (end - start)));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

export default function Recorder({ onSaved }) {
  const [status, setStatus] = useState("idle"); // idle | connecting | recording | stopping
  const [language, setLanguage] = useState("auto");
  const [finals, setFinals] = useState([]);
  const [partial, setPartial] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const r = useRef({});            // audio/ws handles
  const finalsRef = useRef([]);
  const langsRef = useRef(new Set());
  const startedAt = useRef(0);

  const cleanupAudio = () => {
    const { stream, ctx, node } = r.current;
    try { node && node.disconnect(); } catch {}
    stream && stream.getTracks().forEach((t) => t.stop());
    ctx && ctx.state !== "closed" && ctx.close();
  };

  const finish = async () => {
    const text = finalsRef.current.join(" ").trim();
    const duration = (Date.now() - startedAt.current) / 1000;
    setPartial("");
    setStatus("idle");
    if (!text) { setNotice("No speech detected, nothing saved."); return; }
    try {
      const langs = [...langsRef.current].join(",") || language;
      await api.create({ text, language: langs, duration_seconds: Math.round(duration * 10) / 10 });
      setNotice("Saved to history ✔");
      onSaved && onSaved();
    } catch (e) {
      setError("Could not save: " + e.message);
    }
  };

  const start = async () => {
    setError(""); setNotice(""); setFinals([]); setPartial("");
    finalsRef.current = []; langsRef.current = new Set();
    setStatus("connecting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      const ctx = new AudioContext();
      await ctx.audioWorklet.addModule("/pcm-worklet.js");
      const src = ctx.createMediaStreamSource(stream);
      const node = new AudioWorkletNode(ctx, "pcm-processor");
      const mute = ctx.createGain(); mute.gain.value = 0;
      src.connect(node); node.connect(mute); mute.connect(ctx.destination);

      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/ws/transcribe`);
      r.current = { stream, ctx, node, ws };

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "config", language }));
        startedAt.current = Date.now();
        setStatus("recording");
      };
      node.port.onmessage = (e) => {
        if (ws.readyState === WebSocket.OPEN) ws.send(toInt16At16k(e.data, ctx.sampleRate).buffer);
      };
      ws.onmessage = (e) => {
        const m = JSON.parse(e.data);
        if (m.type === "partial") setPartial(m.text);
        else if (m.type === "final") {
          finalsRef.current = [...finalsRef.current, m.text];
          if (m.language) langsRef.current.add(m.language);
          setFinals(finalsRef.current);
          setPartial("");
        } else if (m.type === "error") setError(m.message);
        else if (m.type === "done") { ws.close(); finish(); }
      };
      ws.onerror = () => { setError("WebSocket connection failed."); cleanupAudio(); setStatus("idle"); };
    } catch (e) {
      cleanupAudio();
      setStatus("idle");
      setError(e.name === "NotAllowedError" ? "Microphone permission denied." : e.message);
    }
  };

  const stop = () => {
    setStatus("stopping");
    cleanupAudio();
    const { ws } = r.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "stop" }));
      setTimeout(() => { if (r.current.ws === ws && ws.readyState === WebSocket.OPEN) { ws.close(); finish(); } }, 15000);
    } else finish();
  };

  const recording = status === "recording";
  return (
    <section className="card">
      <h2>🎙️ Live transcription</h2>
      <div className="row">
        <select value={language} onChange={(e) => setLanguage(e.target.value)} disabled={status !== "idle"}>
          {LANGS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
        </select>
        {!recording ? (
          <button className="primary" onClick={start} disabled={status !== "idle"}>
            {status === "connecting" ? "Connecting…" : "Start recording"}
          </button>
        ) : (
          <button className="danger" onClick={stop}>■ Stop &amp; save</button>
        )}
        {recording && <span className="pulse">● live</span>}
        {status === "stopping" && <span className="muted">Finishing last words…</span>}
      </div>

      <div className="transcript" aria-live="polite">
        {finals.length === 0 && !partial && <span className="muted">Your words will appear here as you speak…</span>}
        {finals.join(" ")} <span className="partial">{partial}</span>
      </div>
      {error && <p className="error">{error}</p>}
      {notice && <p className="ok">{notice}</p>}
    </section>
  );
}
