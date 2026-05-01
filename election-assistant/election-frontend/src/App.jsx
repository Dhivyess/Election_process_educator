import { useState, useEffect, useRef, useCallback } from 'react'
import { Send } from 'lucide-react'
import Sidebar, { HamburgerBtn } from './components/Sidebar'
import { MessageBubble, TypingIndicator } from './components/MessageBubble'
import { streamQuestion, checkHealth, clearSession } from './utils/Api'
import { STRINGS } from './utils/i18n'

const STORAGE_KEY = 'ea_messages'
const SESSION_KEY = 'ea_session_id'
const LANG_KEY    = 'ea_lang'

// Load persisted state
function loadPersistedMessages() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

export default function App() {
  const [lang, setLang]         = useState(() => localStorage.getItem(LANG_KEY) || 'en')
  const [messages, setMessages] = useState(loadPersistedMessages)
  const [input, setInput]       = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) || null)
  const [isOnline, setIsOnline]   = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const messagesEndRef = useRef(null)
  const textareaRef    = useRef(null)
  const abortRef       = useRef(null)   // holds the SSE abort fn

  const t = STRINGS[lang]

  // ── Persist messages & session ─────────────────────────────────────────────
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
  }, [messages])

  useEffect(() => {
    if (sessionId) localStorage.setItem(SESSION_KEY, sessionId)
    else localStorage.removeItem(SESSION_KEY)
  }, [sessionId])

  useEffect(() => {
    localStorage.setItem(LANG_KEY, lang)
  }, [lang])

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

  // ── Send message (streaming) ───────────────────────────────────────────────
  const sendMessage = useCallback(async (text) => {
    const question = (text || input).trim()
    if (!question || isLoading) return

    // Cancel any in-flight stream
    abortRef.current?.()

    setInput('')
    const userMsg = { role: 'user', content: question, timestamp: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)

    // Placeholder streaming message
    const placeholderId = Date.now() + '_bot'
    setMessages(prev => [
      ...prev,
      { id: placeholderId, role: 'assistant', content: '', sources: [], lowConfidence: false, streaming: true, timestamp: Date.now(), question },
    ])

    abortRef.current = streamQuestion(question, sessionId, lang, {
      onToken: (token) => {
        setMessages(prev => prev.map(m =>
          m.id === placeholderId ? { ...m, content: m.content + token } : m
        ))
      },
      onDone: ({ sources, low_confidence, session_id }) => {
        setSessionId(session_id)
        setMessages(prev => prev.map(m =>
          m.id === placeholderId ? { ...m, sources, lowConfidence: low_confidence, streaming: false } : m
        ))
        setIsLoading(false)
        textareaRef.current?.focus()
      },
      onError: (err) => {
        setMessages(prev => prev.map(m =>
          m.id === placeholderId
            ? {
                ...m,
                content: lang === 'ta'
                  ? `மன்னிக்கவும், பிழை ஏற்பட்டது: ${err.message}. 1950 அழைக்கவும்.`
                  : `Sorry, an error occurred: ${err.message}. Please try again or call 1950.`,
                sources: [],
                lowConfidence: true,
                streaming: false,
              }
            : m
        ))
        setIsLoading(false)
        textareaRef.current?.focus()
      },
    })
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
    abortRef.current?.()
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
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(o => !o)}
      />

      {/* Main Chat */}
      <main className="chat-area">
        {/* Header */}
        <header className="chat-header">
          <div className="chat-header-left">
            <HamburgerBtn onClick={() => setSidebarOpen(o => !o)} />
            <div>
              <div className="chat-header-title" style={{ fontFamily: 'var(--font-display)' }}>
                {t.chatTitle}
              </div>
              <div className="chat-header-sub">{t.chatSub}</div>
            </div>
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
                <MessageBubble key={msg.id || i} message={msg} lang={lang} sessionId={sessionId} />
              ))}
              {/* Show typing indicator only if loading and the last message isn't streaming yet */}
              {isLoading && messages[messages.length - 1]?.streaming && messages[messages.length - 1]?.content === '' && (
                <TypingIndicator />
              )}
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