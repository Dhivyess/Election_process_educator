import { useState, useEffect, useRef, useCallback } from 'react'
import { Send, Wifi, WifiOff } from 'lucide-react'
import Sidebar from './components/Sidebar'
import { MessageBubble, TypingIndicator } from './components/MessageBubble'
import { askQuestion, checkHealth, clearSession } from './utils/api'
import { STRINGS } from './utils/i18n'

export default function App() {
  const [lang, setLang] = useState('en')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [isOnline, setIsOnline] = useState(null) // null = checking
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  const t = STRINGS[lang]

  // ── Health check on mount ──────────────────────────────────────────────────
  useEffect(() => {
    checkHealth()
      .then(() => setIsOnline(true))
      .catch(() => setIsOnline(false))
  }, [])

  // ── Auto-scroll to bottom ──────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // ── Auto-resize textarea ───────────────────────────────────────────────────
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }, [input])

  // ── Send message ───────────────────────────────────────────────────────────
  const sendMessage = useCallback(async (text) => {
    const question = (text || input).trim()
    if (!question || isLoading) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: question }])
    setIsLoading(true)

    try {
      const data = await askQuestion(question, sessionId, lang)
      setSessionId(data.session_id)
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          sources: data.sources,
          lowConfidence: data.low_confidence,
        },
      ])
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: lang === 'ta'
            ? `மன்னிக்கவும், பிழை ஏற்பட்டது: ${err.message}. 1950 அழைக்கவும்.`
            : `Sorry, an error occurred: ${err.message}. Please try again or call 1950.`,
          sources: [],
          lowConfidence: true,
        },
      ])
    } finally {
      setIsLoading(false)
      textareaRef.current?.focus()
    }
  }, [input, sessionId, lang, isLoading])

  // ── Handle Enter key ───────────────────────────────────────────────────────
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  // ── New chat ───────────────────────────────────────────────────────────────
  const handleNewChat = useCallback(async () => {
    if (sessionId) await clearSession(sessionId)
    setMessages([])
    setSessionId(null)
    setInput('')
    textareaRef.current?.focus()
  }, [sessionId])

  // ── Status indicator ───────────────────────────────────────────────────────
  const StatusPill = () => (
    <div className={`status-pill ${isOnline === false ? 'offline' : ''}`}>
      <span className={`status-dot ${isOnline ? 'live' : ''}`} />
      {isOnline === null ? 'Connecting…' : isOnline ? t.statusOnline : t.statusOffline}
    </div>
  )

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <Sidebar
        lang={lang}
        setLang={setLang}
        onQuickAsk={sendMessage}
        onNewChat={handleNewChat}
      />

      {/* Main Chat */}
      <main className="chat-area">
        {/* Header */}
        <header className="chat-header">
          <div className="chat-header-left">
            <div className="chat-header-title" style={{ fontFamily: 'var(--font-display)' }}>
              {t.chatTitle}
            </div>
            <div className="chat-header-sub">{t.chatSub}</div>
          </div>
          <StatusPill />
        </header>

        {/* Messages */}
        <div className="messages-container">
          {messages.length === 0 ? (
            /* Welcome Screen */
            <div className="welcome-screen">
              <div className="welcome-emblem">🗳️</div>
              <h2 className="welcome-title">{t.welcomeTitle}</h2>
              <p
                className="welcome-sub"
                style={{ fontFamily: lang === 'ta' ? 'var(--font-tamil)' : 'inherit' }}
              >
                {t.welcomeSub}
              </p>
              <div className="welcome-chips">
                {t.quickQuestions.slice(0, 4).map((q, i) => (
                  <button
                    key={i}
                    className="welcome-chip"
                    onClick={() => sendMessage(q.text)}
                    style={{
                      animationDelay: `${0.1 + i * 0.07}s`,
                      animation: 'fadeUp 0.4s ease both',
                      fontFamily: lang === 'ta' ? 'var(--font-tamil)' : 'inherit',
                    }}
                  >
                    {q.icon} {q.text}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, i) => (
                <MessageBubble key={i} message={msg} lang={lang} />
              ))}
              {isLoading && <TypingIndicator />}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="input-area">
          <div className="input-box">
            <textarea
              ref={textareaRef}
              className={`input-textarea ${lang === 'ta' ? 'tamil' : ''}`}
              placeholder={t.placeholder}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={isLoading || isOnline === false}
            />
            <button
              className="send-btn"
              onClick={() => sendMessage()}
              disabled={!input.trim() || isLoading || isOnline === false}
              aria-label="Send message"
            >
              {isLoading
                ? <div className="spinner" />
                : <Send size={16} />
              }
            </button>
          </div>
          <div className="input-hint">{t.hint}</div>
        </div>

        {/* Disclaimer */}
        <div
          className="disclaimer-bar"
          style={{ fontFamily: lang === 'ta' ? 'var(--font-tamil)' : 'inherit' }}
        >
          {t.disclaimer}
        </div>
      </main>
    </div>
  )
}