import { FileText } from 'lucide-react'
import { STRINGS } from '../utils/i18n'

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

export function MessageBubble({ message, lang }) {
    const t = STRINGS[lang]
    const isUser = message.role === 'user'

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
                    {/* Render answer with line breaks */}
                    {message.content.split('\n').map((line, i) => (
                        <span key={i}>
                            {line}
                            {i < message.content.split('\n').length - 1 && <br />}
                        </span>
                    ))}
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