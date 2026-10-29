import { useEffect, useState } from "react";
import { api } from "./api.js";

export default function History({ refreshKey }) {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");

  const load = async (query = q) => {
    try { setItems(await api.list(query)); setError(""); }
    catch (e) { setError(e.message); }
  };

  useEffect(() => { load(); }, [refreshKey]);
  useEffect(() => { const t = setTimeout(() => load(q), 250); return () => clearTimeout(t); }, [q]);

  const save = async () => {
    try {
      await api.update(editing.id, { title: editing.title, text: editing.text });
      setEditing(null); load();
    } catch (e) { setError(e.message); }
  };
  const remove = async (id) => {
    if (!confirm("Delete this transcription?")) return;
    try { await api.remove(id); load(); } catch (e) { setError(e.message); }
  };
  const addManual = async () => {
    const text = prompt("Enter text for the new entry:");
    if (!text) return;
    try { await api.create({ text }); load(); } catch (e) { setError(e.message); }
  };

  return (
    <section className="card">
      <div className="row space">
        <h2>📜 Transcription history</h2>
        <button onClick={addManual}>+ Add manually</button>
      </div>
      <input className="search" placeholder="Search history…" value={q} onChange={(e) => setQ(e.target.value)} />
      {error && <p className="error">{error}</p>}
      {items.length === 0 && <p className="muted">No transcriptions yet.</p>}

      <ul className="list">
        {items.map((t) => (
          <li key={t.id}>
            <div className="row space">
              <strong>{t.title}</strong>
              <span className="muted small">
                {new Date(t.created_at).toLocaleString()} · {t.language || "—"} · {t.duration_seconds}s
              </span>
            </div>
            <p className="text">{t.text}</p>
            <div className="row">
              <button onClick={() => navigator.clipboard.writeText(t.text)}>Copy</button>
              <button onClick={() => setEditing({ ...t })}>Edit</button>
              <button className="danger-outline" onClick={() => remove(t.id)}>Delete</button>
            </div>
          </li>
        ))}
      </ul>

      {editing && (
        <div className="modal" onClick={() => setEditing(null)}>
          <div className="modal-body" onClick={(e) => e.stopPropagation()}>
            <h3>Edit transcription</h3>
            <input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} />
            <textarea rows={8} value={editing.text} onChange={(e) => setEditing({ ...editing, text: e.target.value })} />
            <div className="row">
              <button className="primary" onClick={save}>Save</button>
              <button onClick={() => setEditing(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
