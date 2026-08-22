const API_BASE = import.meta.env.VITE_API_URL || '/api'

async function request(path, { sessionId, ...options } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(sessionId ? { 'X-Connection-Session': sessionId } : {}),
        ...(options.headers || {}),
      },
    })
  } catch {
    throw new Error('Cannot reach SQLRefine. Confirm that the backend is running.')
  }
  let body = null
  if (response.status !== 204) {
    try { body = await response.json() }
    catch { throw new Error('SQLRefine returned an unreadable response.') }
  }
  if (!response.ok) {
    const error = new Error(body?.error?.message || 'The request failed.')
    error.code = body?.error?.code
    error.status = response.status
    throw error
  }
  return body
}

export const testConnection = (details) => request('/connections/test', { method: 'POST', body: JSON.stringify(details) })
export const createConnectionSession = (details) => request('/connection-sessions', { method: 'POST', body: JSON.stringify(details) })
export const deleteConnectionSession = (sessionId) => request('/connection-sessions/current', { method: 'DELETE', sessionId })
export const listDatabases = (sessionId) => request('/databases', { sessionId })
export const loadSchema = (sessionId, database) => request(`/schema?database=${encodeURIComponent(database)}`, { sessionId })
export const analyzeQuery = (sessionId, payload) => request('/analyze', { method: 'POST', sessionId, body: JSON.stringify(payload) })

