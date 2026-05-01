const BASE_URL = import.meta.env.VITE_API_URL || '/api'

/**
 * Ask the election assistant a question.
 * @param {string} question
 * @param {string|null} sessionId
 * @param {'en'|'ta'} language
 * @returns {Promise<{answer, session_id, sources, low_confidence}>}
 */
export async function askQuestion(question, sessionId, language = 'en') {
    const res = await fetch(`${BASE_URL}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            question,
            session_id: sessionId || undefined,
            language,
        }),
    })
    if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Server error ${res.status}`)
    }
    return res.json()
}

/**
 * Health check — returns backend status + vector store doc count.
 */
export async function checkHealth() {
    const res = await fetch(`${BASE_URL}/health`)
    if (!res.ok) throw new Error('Backend offline')
    return res.json()
}

/**
 * Clear conversation history for a session.
 */
export async function clearSession(sessionId) {
    if (!sessionId) return
    await fetch(`${BASE_URL}/session/${sessionId}`, { method: 'DELETE' }).catch(() => { })
}