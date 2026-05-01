const BASE_URL = import.meta.env.VITE_API_URL || '/api'

/**
 * Ask the election assistant a question (blocking).
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
 * Stream an answer via Server-Sent Events.
 * onToken(token)     — called for each streamed token
 * onDone({sources, low_confidence, session_id}) — called when complete
 * onError(err)       — called on failure
 * Returns a cleanup function to abort the stream.
 */
export function streamQuestion(question, sessionId, language = 'en', { onToken, onDone, onError }) {
    const controller = new AbortController()

    fetch(`${BASE_URL}/ask/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, session_id: sessionId || undefined, language }),
        signal: controller.signal,
    })
        .then(async (res) => {
            if (!res.ok) {
                const err = await res.json().catch(() => ({}))
                throw new Error(err.detail || `Server error ${res.status}`)
            }
            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''
            let capturedSessionId = sessionId

            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n')
                buffer = lines.pop()         // keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue
                    const payload = JSON.parse(line.slice(6))
                    if (payload.type === 'init') {
                        capturedSessionId = payload.session_id
                    } else if (payload.type === 'token') {
                        onToken?.(payload.token)
                    } else if (payload.type === 'done') {
                        onDone?.({ ...payload, session_id: capturedSessionId })
                    } else if (payload.type === 'error') {
                        onError?.(new Error(payload.error))
                    }
                }
            }
        })
        .catch((err) => {
            if (err.name !== 'AbortError') onError?.(err)
        })

    return () => controller.abort()
}

/**
 * Submit feedback (thumbs up/down) on an answer.
 */
export async function submitFeedback({ session_id, question, answer, rating, comment }) {
    await fetch(`${BASE_URL}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id, question, answer, rating, comment }),
    }).catch(() => { })   // fire-and-forget; don't surface feedback errors to user
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