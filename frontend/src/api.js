async function req(url, options) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.status === 204 ? null : res.json();
}

export const api = {
  list: (q = "") => req(`/api/transcriptions?q=${encodeURIComponent(q)}`),
  create: (data) => req("/api/transcriptions", { method: "POST", body: JSON.stringify(data) }),
  update: (id, data) => req(`/api/transcriptions/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  remove: (id) => req(`/api/transcriptions/${id}`, { method: "DELETE" }),
};
