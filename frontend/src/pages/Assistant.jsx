import React, { useEffect, useRef, useState } from "react";
import {
  Sparkles,
  ShieldCheck,
  ArrowUpRight,
  ArrowRight,
  LoaderCircle,
  Send,
  Plus,
} from "lucide-react";
import { api } from "../api";
import { uid } from "../utils";
import { ErrorBox } from "../components/common";

export default function Assistant({ dealerId, onOrder }) {
  const [messages, setMessages] = useState([]),
    [text, setText] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(null);
  const bottom = useRef();
  const session = useRef(
    sessionStorage.getItem(`dealerdesk-chat-${dealerId}`) || uid(),
  );
  useEffect(() => {
    sessionStorage.setItem(`dealerdesk-chat-${dealerId}`, session.current);
  }, [dealerId]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, busy]);
  async function send(value = text) {
    if (!value.trim() || busy || !dealerId) return;
    setBusy(true);
    setError(null);
    setText("");
    setMessages((m) => [...m, { role: "user", text: value }]);
    try {
      const response = await api("assistant/chat/", {
        method: "POST",
        body: {
          session_id: session.current,
          dealer_id: Number(dealerId),
          message: value,
        },
      });
      setMessages((m) => [...m, { role: "assistant", ...response }]);
    } catch (err) {
      setError(err);
      setText(value);
    } finally {
      setBusy(false);
    }
  }
  function reset() {
    session.current = uid();
    sessionStorage.setItem(`dealerdesk-chat-${dealerId}`, session.current);
    setMessages([]);
    setError(null);
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">A LITTLE HELP AT THE COUNTER</div>
          <h1>Your dealer assistant.</h1>
          <p>
            Find the right fit, check availability and turn a conversation into
            a draft.
          </p>
        </div>
        <button className="secondary" onClick={reset} disabled={busy}>
          <Plus size={17} /> New conversation
        </button>
      </div>
      <div className="chat-panel">
        <div className="chat-top">
          <span className="assistant-avatar">
            <Sparkles size={20} />
          </span>
          <div>
            <strong>DealerDesk assistant</strong>
            <span>Grounded in your live catalogue</span>
          </div>
          <span className="live-tag">
            <ShieldCheck size={14} /> Drafts only
          </span>
        </div>
        <div className="chat-messages">
          {!messages.length ? (
            <div className="chat-welcome">
              <span className="welcome-icon">
                <Sparkles size={32} />
              </span>
              <h2>What can I help you find?</h2>
              <p>
                Tell me the part and vehicle. I’ll check the catalogue before
                answering.
              </p>
              <div className="suggestions">
                {[
                  "Find brake pads for a Pulsar 150",
                  "Show oil filters for a Duke 390",
                  "What can you help me with?",
                ].map((s) => (
                  <button key={s} onClick={() => send(s)}>
                    {s}
                    <ArrowUpRight size={16} />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) => (
              <div className={`message ${m.role}`} key={i}>
                <div className="message-label">
                  {m.role === "user" ? "YOU" : "DEALERDESK"}
                </div>
                <div className="message-text">{m.text || m.reply}</div>
                {m.cited_skus?.length > 0 && (
                  <div className="citations">
                    {m.cited_skus.map((s) => (
                      <code key={s}>{s}</code>
                    ))}
                  </div>
                )}
                {m.actions?.map((a) => (
                  <button
                    className="secondary"
                    key={a.order_number}
                    onClick={() => onOrder(a.order_number)}
                  >
                    Open {a.order_number}
                    <ArrowRight size={16} />
                  </button>
                ))}
              </div>
            ))
          )}
          {busy && (
            <div className="thinking">
              <LoaderCircle className="spin" size={16} /> Checking your request…
            </div>
          )}
          <div ref={bottom} />
        </div>
        <div className="chat-compose">
          <ErrorBox error={error} />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <input
              aria-label="Message the assistant"
              placeholder="Ask about a part, vehicle or stock…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={4000}
              disabled={busy || !dealerId}
            />
            <button
              className="primary"
              aria-label="Send message"
              disabled={busy || !text.trim() || !dealerId}
            >
              <Send size={18} />
            </button>
          </form>
          <small>
            Drafts don’t reserve stock. Review and confirm orders separately.
          </small>
        </div>
      </div>
    </>
  );
}
