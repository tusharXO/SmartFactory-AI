const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/+$/, '')

export class ApiError extends Error {
  constructor(message, status = 0, details = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

async function request(path, { signal, method = 'GET', body } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method, signal,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError('Cannot connect to the data service. Please try again.')
  }
  let data
  try { data = await response.json() } catch {
    throw new ApiError('The API returned an unreadable response. Please try again.', response.status)
  }
  if (!response.ok) {
    const details = Array.isArray(data.detail) ? data.detail : []
    const unavailableMessage = path === '/predict'
      ? 'Predictions are temporarily unavailable. Please try again later.'
      : path === '/model-metrics'
        ? 'Model evaluation is temporarily unavailable. Please try again later.'
        : 'The dataset is temporarily unavailable. Please retry.'
    const message = response.status === 503 ? unavailableMessage
      : typeof data.detail === 'string' ? data.detail
      : details.length ? 'Check the highlighted fields and try again.' : 'The request failed. Please retry.'
    throw new ApiError(message, response.status, details)
  }
  return data
}

export const getHealth = (options) => request('/health', options)
export const getOverview = (options) => request('/overview', options)
export const getCharts = (options) => request('/charts', options)
export const getModelMetrics = (options) => request('/model-metrics', options)

export function getObservations({ limit = 10, offset = 0, type = '', failure = '', signal } = {}) {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (type) query.set('type', type)
  if (failure !== '' && failure !== undefined && failure !== null) query.set('failure', String(failure))
  return request(`/observations?${query}`, { signal })
}

export const predict = (measurement, options = {}) => request('/predict', {
  ...options, method: 'POST', body: measurement,
})
