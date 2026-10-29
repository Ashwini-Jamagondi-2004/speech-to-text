import { useState } from "react";
import Recorder from "./Recorder.jsx";
import History from "./History.jsx";

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);
  return (
    <main>
      <header>
        <h1>Speech → Text</h1>
        <p className="muted">Real-time multilingual (Hindi + English) transcription · Faster-Whisper · FastAPI · PostgreSQL</p>
      </header>
      <Recorder onSaved={() => setRefreshKey((k) => k + 1)} />
      <History refreshKey={refreshKey} />
    </main>
  );
}
