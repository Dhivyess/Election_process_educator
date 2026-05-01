import ReactMarkdown from 'react-markdown'
import { FileText, ThumbsUp, ThumbsDown, Copy, Check } from 'lucide-react'
import { STRINGS } from '../utils/i18n'
import { submitFeedback } from '../utils/Api'
import { useState, useCallback } from 'react'

export function TypingIndicator() {
    return (
        <div className="message-row">
            <div className="avatar bot">🗳️</div>
            <div className="typing-indicator">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
            </div>
        </div>
    )
}

export function MessageBubble({ message, lang, sessionId }) {
    const t = STRINGS[lang]
    const isUser = message.role === 'user'
    const [copied, setCopied] = useState(false)
    const [feedback, setFeedback] = useState(null) // null | 1 | -1

    const handleCopy = useCallback(() => {
        navigator.clipboard.writeText(message.content).then(() => {
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        })
    }, [message.content])

    const handleFeedback = useCallback((rating) => {
        if (feedback !== null) return  // already voted
        setFeedback(rating)
        submitFeedback({
            session_id: sessionId,
            question: message.question || '',
            answer: message.content,
            rating,
        })
    }, [feedback, message, sessionId])

    // Format timestamp
    const timestamp = message.timestamp
        ? new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        : null

    return (
        <div className={`message-row ${isUser ? 'user' : ''}`}>
            {/* Avatar */}
            <div className={`avatar ${isUser ? 'user-av' : 'bot'}`}>
                {isUser ? '👤' : '🗳️'}
            </div>

            <div className="bubble-wrap">
                {/* Bubble */}
                <div
                    className={`bubble ${isUser ? 'user' : `bot${message.lowConfidence ? ' low-conf' : ''}`}`}
                    style={{ fontFamily: lang === 'ta' ? 'var(--font-tamil)' : 'inherit' }}
                >
                    {isUser ? (
                        message.content
                    ) : (
                        <ReactMarkdown
                            components={{
                                // Open links in a new tab
                                a: ({ node, ...props }) => (
                                    <a {...props} target="_blank" rel="noopener noreferrer" />
                                ),
                            }}
                        >
                            {message.streaming && !message.content ? '…' : message.content}
                        </ReactMarkdown>
                    )}
                </div>

                {/* Timestamp + actions row */}
                <div className="bubble-meta">
                    {timestamp && <span className="msg-timestamp">{timestamp}</span>}

                    {!isUser && !message.streaming && (
                        <div className="bubble-actions">
                            {/* Copy */}
                            <button
                                className={`action-btn ${copied ? 'active' : ''}`}
                                onClick={handleCopy}
                                title="Copy response"
                                aria-label="Copy response"
                            >
                                {copied ? <Check size={12} /> : <Copy size={12} />}
                            </button>

                            {/* Thumbs up */}
                            <button
                                className={`action-btn ${feedback === 1 ? 'active good' : ''}`}
                                onClick={() => handleFeedback(1)}
                                disabled={feedback !== null}
                                title="Good answer"
                                aria-label="Good answer"
                            >
                                <ThumbsUp size={12} />
                            </button>

                            {/* Thumbs down */}
                            <button
                                className={`action-btn ${feedback === -1 ? 'active bad' : ''}`}
                                onClick={() => handleFeedback(-1)}
                                disabled={feedback !== null}
                                title="Bad answer"
                                aria-label="Bad answer"
                            >
                                <ThumbsDown size={12} />
                            </button>
                        </div>
                    )}
                </div>

                {/* Source chips */}
                {!isUser && message.sources && message.sources.length > 0 && (
                    <div className="source-chips">
                        <span className="source-chip">
                            <FileText size={10} />
                            {t.sourceLabel}
                        </span>
                        {message.sources.map((src, i) => (
                            <span key={i} className="source-chip">
                                {src}
                            </span>
                        ))}
                    </div>
                )}

                {/* Low confidence warning */}
                {!isUser && message.lowConfidence && (
                    <div className="conf-warning">{t.lowConfWarning}</div>
                )}
            </div>
        </div>
    )
}