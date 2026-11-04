// Calls to the FastAPI backend. Same origin in production, proxied by Vite locally.

async function request(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return data;
}

export function sendMessage(message, threadId) {
  return request("/chat", {
    method: "POST",
    body: JSON.stringify({ message, thread_id: threadId }),
  });
}

// Turns a recorded or uploaded question (audio/video) into text: resolves to { text }
export function transcribeAudio(file, filename) {
  const form = new FormData();
  form.append("file", file, filename);
  // No JSON Content-Type: the browser sets the multipart one (with its boundary)
  return request("/transcribe", { method: "POST", body: form, headers: {} });
}

// Ends a conversation on the server: deletes the videos/embeddings found for it
export function endChat(threadId) {
  return request(`/chat/${encodeURIComponent(threadId)}`, { method: "DELETE" });
}
