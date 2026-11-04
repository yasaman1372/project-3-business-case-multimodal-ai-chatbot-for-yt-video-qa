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

export function fetchVideos() {
  return request("/videos");
}

export function sendMessage(message, threadId) {
  return request("/chat", {
    method: "POST",
    body: JSON.stringify({ message, thread_id: threadId }),
  });
}
