const API_BASE = import.meta.env.VITE_API_URL || '/api'

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    })
  } catch {
    throw new Error('Cannot reach the SQLRefine API. Confirm that the Flask server is running.')
  }

  let body
  try {
    body = await response.json()
  } catch {
    throw new Error('The API returned an unreadable response.')
  }
  if (!response.ok) throw new Error(body?.error?.message || 'The analysis request failed.')
  return body
}

export function compareQuery(query) {
  return request('/compare', { method: 'POST', body: JSON.stringify({ query }) })
}

