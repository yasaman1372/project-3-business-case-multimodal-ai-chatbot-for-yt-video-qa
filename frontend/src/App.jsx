import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { fetchVideos, sendMessage } from "./api.js";

const TOOL_LABELS = {
  search_video_transcripts: "🔍 Searched transcripts",
  list_available_videos: "📋 Listed videos",
  get_video_transcript: "📄 Read full transcript",
  find_and_add_videos: "➕ Added new videos",
};

const SUGGESTIONS = [
  "What is inside a black hole?",
  "Which videos do you have?",
  "Summarise the Kurzgesagt video",
  "Find videos about the James Webb telescope",
];

const STORAGE_KEY = "yt-qa-chat";

function loadSavedChat() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || { threadId: null, messages: [] };
  } catch {
    return { threadId: null, messages: [] };
  }
}

// Open answer links (video timestamps) in a new tab
const markdownComponents = {
  a: ({ node, ...props }) => <a {...props} target="_blank" rel="noreferrer" />,
};

export default function App() {
  const saved = loadSavedChat();
  const [threadId, setThreadId] = useState(saved.threadId);
  const [messages, setMessages] = useState(saved.messages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [slow, setSlow] = useState(false);
  const [videos, setVideos] = useState([]);
  const [videosError, setVideosError] = useState(null);
  const bottomRef = useRef(null);

  const loadVideos = () =>
    fetchVideos()
      .then((v) => {
        setVideos(v);
        setVideosError(null);
      })
      .catch((e) => setVideosError(e.message));

  useEffect(() => {
    loadVideos();
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ threadId, messages }));
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [threadId, messages, loading]);

  async function send(text) {
    const message = text.trim();
    if (!message || loading) return;

    setInput("");
    setMessages((m) => [...m, { role: "user", content: message }]);
    setLoading(true);
    const slowTimer = setTimeout(() => setSlow(true), 10000);

    try {
      const data = await sendMessage(message, threadId);
      setThreadId(data.thread_id);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: data.answer, tools: data.tools_used, seconds: data.seconds },
      ]);
      if (data.tools_used.includes("find_and_add_videos")) loadVideos();
    } catch (e) {
      setMessages((m) => [...m, { role: "error", content: e.message }]);
    } finally {
      clearTimeout(slowTimer);
      setLoading(false);
      setSlow(false);
    }
  }

  function newChat() {
    setThreadId(null);
    setMessages([]);
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  // Group sidebar videos by topic
  const byTopic = videos.reduce((groups, v) => {
    const topic = v.topic || "Other";
    (groups[topic] ||= []).push(v);
    return groups;
  }, {});

  return (
    <div className="layout">
      <aside className="sidebar">
        <h2>📚 Indexed videos</h2>
        {videosError && <p className="muted">Couldn't load videos: {videosError}</p>}
        {!videosError && videos.length === 0 && <p className="muted">No videos yet.</p>}
        {Object.entries(byTopic).map(([topic, list]) => (
          <section key={topic}>
            <h3>{topic}</h3>
            <ul>
              {list.map((v) => (
                <li key={v.video_id}>
                  <a href={v.url} target="_blank" rel="noreferrer">
                    {v.title || v.video_id}
                  </a>
                  {v.channel && <span className="muted"> · {v.channel}</span>}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </aside>

      <main className="chat">
        <header>
          <h1>🎬 YouTube Video QA</h1>
          <button className="secondary" onClick={newChat} disabled={loading}>
            New chat
          </button>
        </header>

        <div className="messages">
          {messages.length === 0 && (
            <div className="empty">
              <p>Ask anything about the indexed videos. Answers link to the exact moment in the video.</p>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="secondary" onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`message ${m.role}`}>
              {m.role === "assistant" ? (
                <>
                  <ReactMarkdown components={markdownComponents}>{m.content}</ReactMarkdown>
                  <div className="meta">
                    {m.tools?.map((t, j) => (
                      <span key={j} className="chip">
                        {TOOL_LABELS[t] || t}
                      </span>
                    ))}
                    {m.seconds != null && <span className="muted">{m.seconds}s</span>}
                  </div>
                </>
              ) : (
                m.content
              )}
            </div>
          ))}

          {loading && (
            <div className="message assistant thinking">
              {slow ? "Still working… adding new videos can take up to a minute." : "Thinking…"}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the videos…  (Enter to send, Shift+Enter for a new line)"
            rows={2}
            maxLength={2000}
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            Send
          </button>
        </form>
      </main>
    </div>
  );
}
