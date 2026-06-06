import { useState, useRef, useEffect } from 'react';
import { assistantApi } from '../services/api';

export default function AssistantPage({ messages, setMessages, history, setHistory }) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg = { role: 'user', text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const res = await assistantApi.chat(text, history);
      setHistory(res.history);
      setMessages((prev) => [...prev, { role: 'assistant', text: res.reply }]);
    } catch (err) {
      setError(err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    setHistory([]);
    setError(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)', gap: '1rem' }}>
      <p style={{ margin: 0, color: 'var(--text-muted, #aaa)', fontSize: '0.9rem' }}>
        Ask questions about your data in plain English. The assistant uses real warehouse data to answer.
        Try: <em>"What assets do you have?"</em> or <em>"Summarize the trend for BTC"</em>.
      </p>

      {error && <div className="error-banner">{error}</div>}

      {/* Message list */}
      <div className="card" style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {messages.length === 0 && (
          <div className="empty-state">No messages yet. Ask something above.</div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <div
              style={{
                maxWidth: '80%',
                padding: '0.6rem 0.9rem',
                borderRadius: '0.75rem',
                background: msg.role === 'user'
                  ? 'var(--accent, #646cff)'
                  : 'var(--surface-2, #1e2235)',
                color: msg.role === 'user' ? '#fff' : 'var(--text, inherit)',
                whiteSpace: 'pre-wrap',
                lineHeight: 1.5,
                fontSize: '0.95rem',
              }}
            >
              {msg.text}
            </div>
            <span style={{ fontSize: '0.7rem', marginTop: '0.2rem', color: 'var(--text-muted, #888)' }}>
              {msg.role === 'user' ? 'You' : 'Assistant'}
            </span>
          </div>
        ))}
        {loading && (
          <div style={{ alignSelf: 'flex-start' }}>
            <div
              style={{
                padding: '0.6rem 0.9rem',
                borderRadius: '0.75rem',
                background: 'var(--surface-2, #1e2235)',
                color: 'var(--text-muted, #aaa)',
                fontStyle: 'italic',
                fontSize: '0.9rem',
              }}
            >
              Thinking…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input row */}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <textarea
          className="form-field"
          style={{ flex: 1, resize: 'none', height: '3rem', padding: '0.6rem', fontFamily: 'inherit', fontSize: '0.95rem' }}
          placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button className="btn-primary" onClick={sendMessage} disabled={loading || !input.trim()}>
          Send
        </button>
        <button onClick={clearChat} disabled={loading} title="Clear conversation">
          Clear
        </button>
      </div>
    </div>
  );
}
