import { useEffect, useRef, useState } from "react";
import { VoiceSession } from "../audio/VoiceSession";
import type { CallState, VoiceEvent } from "../audio/VoiceSession";

type Message = { role: "user" | "assistant"; text: string };
const labels: Record<CallState, string> = {
  idle: "Ready when you are",
  connecting: "Connecting to Nephele",
  listening: "Listening to you",
  thinking: "Thinking it through",
  speaking: "Nephele is speaking",
  error: "Let's try that again",
};

export default function VoiceOverlay() {
  const [state, setState] = useState<CallState>("idle");
  const [error, setError] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const session = useRef<VoiceSession | null>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const active = state !== "idle" && state !== "error";

  useEffect(
    () => () => {
      session.current?.stop();
    },
    [],
  );
  useEffect(() => {
    transcript.current?.scrollTo({
      top: transcript.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  function receive(event: VoiceEvent) {
    if (!event.content) return;
    const content = event.content;
    setMessages((previous) => {
      if (event.type === "user_text")
        return [...previous, { role: "user", text: content }].slice(
          -40,
        ) as Message[];
      if (event.type !== "text") return previous;
      const last = previous[previous.length - 1];
      return last?.role === "assistant"
        ? [
            ...previous.slice(0, -1),
            { role: "assistant", text: last.text + content },
          ]
        : ([...previous, { role: "assistant", text: content }].slice(
            -40,
          ) as Message[]);
    });
  }

  function toggle() {
    if (active) {
      session.current?.stop();
      session.current = null;
      setState("idle");
      return;
    }
    setMessages([]);
    setError("");
    session.current?.stop();
    session.current = new VoiceSession((next, reason) => {
      setState(next);
      if (reason) setError(reason);
    }, receive);
    void session.current.start();
  }

  return (
    <section className="conversation" aria-label="Talk with Nephele">
      <div
        className={`call-status state-${state}`}
        role="status"
        aria-live="polite"
      >
        <span className="status-dot" />
        {labels[state]}
      </div>
      <h1>
        A little clarity.
        <br />
        <span>A lot more confidence.</span>
      </h1>
      <p className="intro">
        Your placement journey, one conversation at a time. Talk through
        interviews, resumes, and what comes next.
      </p>

      <div className="conversation-card">
        <div className="card-heading">
          <h2>Your conversation</h2>
          <span>VOICE / LIVE</span>
        </div>
        <div
          className="transcript"
          ref={transcript}
          role="log"
          aria-label="Conversation transcript"
          aria-live="polite"
          aria-relevant="additions text"
          tabIndex={0}
        >
          {messages.length ? (
            messages.map((message, index) => (
              <div className={`message message-${message.role}`} key={index}>
                <span className="speaker">
                  {message.role === "user" ? "You" : "Nephele"}
                </span>
                <p>{message.text}</p>
              </div>
            ))
          ) : (
            <div className="empty-conversation">
              <span className="quote-mark" aria-hidden="true">
                “
              </span>
              <p>
                {active
                  ? "Take your time. I'm here to listen."
                  : "Start with whatever's on your mind."}
              </p>
              <span>
                {active
                  ? "Your conversation will appear here."
                  : "“How do I introduce myself in an interview?”"}
              </span>
            </div>
          )}
        </div>
        {error && (
          <p className="call-error" role="alert">
            {error}
          </p>
        )}
        <div className="call-controls">
          <button
            className={`call-button ${active ? "is-active" : ""}`}
            onClick={toggle}
          >
            {active ? (
              <span className="stop-icon" aria-hidden="true" />
            ) : (
              <svg
                viewBox="0 0 24 24"
                width="20"
                height="20"
                aria-hidden="true"
              >
                <rect
                  x="9"
                  y="2"
                  width="6"
                  height="13"
                  rx="3"
                  fill="currentColor"
                />
                <path
                  d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
              </svg>
            )}
            {active
              ? state === "connecting"
                ? "Cancel connection"
                : "End conversation"
              : state === "error"
                ? "Try again"
                : "Start a conversation"}
          </button>
          <p className="mic-note">
            {active
              ? "Your microphone is on. End the call to turn it off."
              : "Microphone starts only when you choose."}
          </p>
        </div>
      </div>
      <p className="privacy-note">
        Voice is processed by Deepgram and OpenAI. Avoid sharing sensitive
        details. Nephele can make mistakes; check important advice.
      </p>
    </section>
  );
}
