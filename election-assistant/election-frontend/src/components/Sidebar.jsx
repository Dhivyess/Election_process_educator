import { PlusCircle, Menu, X } from 'lucide-react'
import { STRINGS, TIMELINE } from '../utils/i18n'

export default function Sidebar({ lang, setLang, onQuickAsk, onNewChat, isOpen, onToggle }) {
    const t = STRINGS[lang]

    return (
        <>
            {/* Mobile overlay backdrop */}
            {isOpen && (
                <div
                    className="sidebar-backdrop"
                    onClick={onToggle}
                    aria-hidden="true"
                />
            )}

            <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
                {/* Mobile close button */}
                <button
                    className="sidebar-close-btn"
                    onClick={onToggle}
                    aria-label="Close sidebar"
                >
                    <X size={18} />
                </button>

                {/* Header / Brand */}
                <div className="sidebar-header">
                    <div className="brand-eyebrow">{t.eyebrow}</div>
                    <h1 className="brand-title" style={{ whiteSpace: 'pre-line' }}>
                        {t.brandTitle}
                    </h1>
                    <p className="brand-subtitle">{t.brandSubtitle}</p>

                    {/* Language Toggle */}
                    <div className="lang-toggle" role="group" aria-label="Language selection">
                        <button
                            className={`lang-btn ${lang === 'en' ? 'active' : ''}`}
                            onClick={() => setLang('en')}
                            aria-pressed={lang === 'en'}
                        >
                            {t.langEn}
                        </button>
                        <button
                            className={`lang-btn ${lang === 'ta' ? 'active' : ''}`}
                            onClick={() => setLang('ta')}
                            aria-pressed={lang === 'ta'}
                        >
                            <span className="tamil-label">{t.langTa}</span>
                        </button>
                    </div>
                </div>

                <div className="sidebar-content">
                    {/* New Chat */}
                    <div style={{ padding: '0 16px', marginBottom: '20px' }}>
                        <button className="new-chat-btn" onClick={onNewChat}>
                            <PlusCircle size={15} />
                            {t.newChat}
                        </button>
                    </div>

                    {/* Quick Questions */}
                    <div className="sidebar-section">
                        <div className="sidebar-section-label">{t.quickLabel}</div>
                        {t.quickQuestions.map((q, i) => (
                            <button
                                key={i}
                                className="quick-btn"
                                onClick={() => { onQuickAsk(q.text); onToggle?.() }}
                                style={{ animationDelay: `${i * 0.05}s` }}
                                aria-label={q.text}
                            >
                                <span className="q-icon">{q.icon}</span>
                                <span style={{ fontFamily: lang === 'ta' ? 'var(--font-tamil)' : 'inherit' }}>
                                    {q.text}
                                </span>
                            </button>
                        ))}
                    </div>

                    {/* Election Timeline */}
                    <div className="sidebar-section">
                        <div className="sidebar-section-label">{t.timelineLabel}</div>
                    </div>
                    <div className="timeline-list">
                        {TIMELINE.map((item, i) => (
                            <div
                                className="timeline-item"
                                key={i}
                                style={{ animationDelay: `${0.1 + i * 0.06}s` }}
                            >
                                <div className={`tl-dot ${item.status}`}>
                                    {item.status === 'done' && '✓'}
                                    {item.status === 'current' && '●'}
                                    {item.status === 'future' && ''}
                                </div>
                                <div className="tl-body">
                                    <div className="tl-date">{item.date}</div>
                                    <div className={`tl-label ${item.status === 'current' ? 'current' : ''}`}>
                                        {lang === 'ta' ? item.labelTa : item.label}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </aside>
        </>
    )
}

export function HamburgerBtn({ onClick }) {
    return (
        <button className="hamburger-btn" onClick={onClick} aria-label="Open menu">
            <Menu size={22} />
        </button>
    )
}