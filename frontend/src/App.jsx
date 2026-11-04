import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { endChat, sendMessage, transcribeAudio } from "./api.js";
import Illustration from "./Illustration.jsx";

const TOOL_LABELS = {
  search_video_transcripts: { icon: "🔍", label: "Searched transcripts" },
  find_videos_on_topic: { icon: "🎬", label: "Found videos on YouTube" },
  list_videos_in_this_chat: { icon: "📚", label: "Listed chat videos" },
  get_video_transcript: { icon: "📄", label: "Read full transcript" },
};

// One question per subject. The first question on a topic finds videos on YouTube.
const SUGGESTIONS = [
  { icon: "🕳️", title: "What is inside a black hole?", hint: "Space · Astrophysics" },
  { icon: "🎨", title: "Why is Van Gogh's The Starry Night so famous?", hint: "Art · Painting" },
  { icon: "🏛️", title: "Why did the Roman Empire fall?", hint: "History · Ancient Rome" },
  { icon: "🏃", title: "What's the science behind running faster?", hint: "Sport · Sprinting" },
];

// Progress messages while waiting: [seconds after sending, text]
const LOADING_STAGES = [
  [0, "Thinking"],
  [4, "Searching YouTube for videos"],
  [10, "Reading the transcripts"],
  [20, "Embedding the videos into this chat"],
  [35, "Almost there, writing the answer"],
];

const STORAGE_KEY = "yt-qa-chat";

// Spoken questions: recorded with the microphone or uploaded as an audio/video file
const MAX_RECORDING_SECONDS = 120;
const MAX_UPLOAD_MB = 4; // must match MAX_AUDIO_MB on the server (Vercel caps uploads at 4.5 MB)
const UPLOAD_TYPES = ".flac,.m4a,.mp3,.mp4,.mpeg,.mpga,.oga,.ogg,.wav,.webm";
const CAN_RECORD = Boolean(navigator.mediaDevices?.getUserMedia) && typeof MediaRecorder !== "undefined";

// File extension for what the browser records (Chrome/Firefox: webm or ogg, Safari: mp4)
function recordingExtension(mimeType) {
  if (mimeType.includes("mp4")) return "mp4";
  if (mimeType.includes("ogg")) return "ogg";
  return "webm";
}

function formatSeconds(total) {
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

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

function Logo({ size = 36 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <defs>
        <linearGradient id="logo-gradient" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ff5a45" />
          <stop offset="55%" stopColor="#ff8a3d" />
          <stop offset="100%" stopColor="#ffc04d" />
        </linearGradient>
      </defs>
      <rect x="2" y="6" width="36" height="28" rx="9" fill="url(#logo-gradient)" />
      <path d="M17 14.5v11l9-5.5z" fill="#fff" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" stroke="currentColor" strokeWidth="2" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="5" y="5" width="14" height="14" rx="3" fill="currentColor" />
    </svg>
  );
}

function PaperclipIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M20 11.5l-7.8 7.8a5 5 0 0 1-7.1-7.1l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7l-8.5 8.5a1.7 1.7 0 0 1-2.4-2.4l7.8-7.8"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}

export default function App() {
  const saved = loadSavedChat();
  const [threadId, setThreadId] = useState(saved.threadId);
  const [messages, setMessages] = useState(saved.messages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState(0);
  // Voice input: "idle" | "recording" | "transcribing"
  const [voice, setVoice] = useState("idle");
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [voiceError, setVoiceError] = useState(null);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  const recorderRef = useRef(null);
  const recordingTimersRef = useRef([]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ threadId, messages }));
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [threadId, messages, loading]);

  // Grow the textarea with its content (up to the CSS max-height)
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [input]);

  async function send(text) {
    const message = text.trim();
    if (!message || loading) return;

    setInput("");
    setMessages((m) => [...m, { role: "user", content: message }]);
    setLoading(true);
    setStage(0);
    // Advance the progress message. A follow-up on a known topic usually answers
    // before the later stages appear.
    const stageTimers = LOADING_STAGES.slice(1).map(([seconds], i) =>
      setTimeout(() => setStage(i + 1), seconds * 1000)
    );

    try {
      const data = await sendMessage(message, threadId);
      setThreadId(data.thread_id);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: data.answer, tools: data.tools_used, seconds: data.seconds },
      ]);
    } catch (e) {
      setMessages((m) => [...m, { role: "error", content: e.message }]);
    } finally {
      stageTimers.forEach(clearTimeout);
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  // Put the spoken question in the message box, so it can be checked before sending
  async function transcribe(file, filename) {
    setVoiceError(null);
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setVoiceError(`That file is ${(file.size / 1024 / 1024).toFixed(1)} MB; the limit is ${MAX_UPLOAD_MB} MB.`);
      return;
    }
    setVoice("transcribing");
    try {
      const { text } = await transcribeAudio(file, filename);
      setInput((current) => (current.trim() ? `${current.trim()} ${text}` : text));
    } catch (e) {
      setVoiceError(e.message);
    } finally {
      setVoice("idle");
      inputRef.current?.focus();
    }
  }

  async function startRecording() {
    setVoiceError(null);
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setVoiceError("Microphone access was blocked. Allow it in your browser to ask by voice.");
      return;
    }

    const recorder = new MediaRecorder(stream);
    const chunks = [];
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop()); // turn the microphone off
      recordingTimersRef.current.forEach(clearTimeout);
      const type = recorder.mimeType || "audio/webm";
      transcribe(new Blob(chunks, { type }), `question.${recordingExtension(type)}`);
    };
    recorder.start();
    recorderRef.current = recorder;
    setVoice("recording");
    setRecordingSeconds(0);
    recordingTimersRef.current = [
      setInterval(() => setRecordingSeconds((s) => s + 1), 1000),
      setTimeout(stopRecording, MAX_RECORDING_SECONDS * 1000),
    ];
  }

  function stopRecording() {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  function handleFileChosen(e) {
    const file = e.target.files[0];
    e.target.value = ""; // allow choosing the same file again
    if (file) transcribe(file, file.name);
  }

  function newChat() {
    // Delete the old chat's videos and embeddings on the server (no need to wait)
    if (threadId) endChat(threadId).catch(() => {});
    setThreadId(null);
    setMessages([]);
    inputRef.current?.focus();
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="app">
      <div className="backdrop" aria-hidden="true">
        <Illustration />
      </div>

      <header className="topbar">
        <div className="brand">
          <Logo />
          <div>
            <h1>
              Video<span className="gradient-text">QA</span>
            </h1>
            <p>Ask YouTube videos anything</p>
          </div>
        </div>
        <button className="ghost-button" onClick={newChat} disabled={loading || isEmpty}>
          <PlusIcon /> New chat
        </button>
      </header>

      <main className="conversation">
        {isEmpty && (
          <section className="hero">
            <div className="hero-logo">
              <Logo size={72} />
            </div>
            <h2>
              Ask anything.
              <br />
              <span className="gradient-text">Jump to the exact moment.</span>
            </h2>
            <p>
              Ask about any topic. I find YouTube videos on it, read their transcripts, and answer
              with links that open each video at the second it's explained.
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={s.title}
                  className="suggestion"
                  style={{ animationDelay: `${150 + i * 80}ms` }}
                  onClick={() => send(s.title)}
                >
                  <span className="suggestion-icon">{s.icon}</span>
                  <span>
                    <strong>{s.title}</strong>
                    <small>{s.hint}</small>
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}

        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="row user">
              <div className="bubble user-bubble">{m.content}</div>
            </div>
          ) : m.role === "assistant" ? (
            <div key={i} className="row assistant">
              <div className="avatar">
                <Logo size={22} />
              </div>
              <div className="bubble assistant-bubble">
                <div className="markdown">
                  <ReactMarkdown components={markdownComponents}>{m.content}</ReactMarkdown>
                </div>
                {(m.tools?.length > 0 || m.seconds != null) && (
                  <div className="meta">
                    {m.tools?.map((t, j) => (
                      <span key={j} className="chip">
                        <span>{TOOL_LABELS[t]?.icon || "🛠️"}</span>
                        {TOOL_LABELS[t]?.label || t}
                      </span>
                    ))}
                    {m.seconds != null && <span className="time">⚡ {m.seconds}s</span>}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div key={i} className="row assistant">
              <div className="avatar error-avatar">!</div>
              <div className="bubble error-bubble">
                <strong>Something went wrong.</strong> {m.content}
              </div>
            </div>
          )
        )}

        {loading && (
          <div className="row assistant">
            <div className="avatar pulsing">
              <Logo size={22} />
            </div>
            <div className="bubble assistant-bubble thinking">
              <span className="dots">
                <i />
                <i />
                <i />
              </span>
              <span className="shimmer">{LOADING_STAGES[stage][1]}…</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </main>

      <footer className="composer-wrap">
        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about any topic…"
            rows={1}
            maxLength={2000}
            disabled={loading}
            autoFocus
          />
          <input
            ref={fileInputRef}
            type="file"
            accept={UPLOAD_TYPES}
            onChange={handleFileChosen}
            hidden
          />
          <button
            type="button"
            className="icon-button"
            onClick={() => fileInputRef.current?.click()}
            disabled={loading || voice !== "idle"}
            aria-label="Upload an audio or video question"
            title="Upload an audio or video question"
          >
            <PaperclipIcon />
          </button>
          {CAN_RECORD && (
            <button
              type="button"
              className={`icon-button ${voice === "recording" ? "recording" : ""}`}
              onClick={voice === "recording" ? stopRecording : startRecording}
              disabled={loading || voice === "transcribing"}
              aria-label={voice === "recording" ? "Stop recording" : "Ask by voice"}
              title={voice === "recording" ? "Stop recording" : "Ask by voice"}
            >
              {voice === "recording" ? <StopIcon /> : <MicIcon />}
            </button>
          )}
          <button
            type="submit"
            className="send-button"
            disabled={loading || voice !== "idle" || !input.trim()}
            aria-label="Send"
          >
            <SendIcon />
          </button>
        </form>
        {voice === "recording" ? (
          <p className="hint voice-status">
            <span className="rec-dot" /> Recording {formatSeconds(recordingSeconds)} /{" "}
            {formatSeconds(MAX_RECORDING_SECONDS)} · press ■ when you're done
          </p>
        ) : voice === "transcribing" ? (
          <p className="hint voice-status">Turning your question into text…</p>
        ) : voiceError ? (
          <p className="hint hint-error">{voiceError}</p>
        ) : (
          <p className="hint">
            Enter to send · 🎤 ask by voice or 📎 upload an audio/video clip · A new topic takes ~30s
          </p>
        )}
      </footer>
    </div>
  );
}
