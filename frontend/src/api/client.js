/**
 * api/client.js — Axios instance + all LiquorIQ API calls
 *
 * Single place for every network request. The route layer never calls
 * fetch/axios directly — it always goes through a function here.
 *
 * Auth flow:
 *   - After login, the JWT is stored in memory (AuthContext)
 *   - The request interceptor below reads it and adds Authorization header
 *   - If the token expires, the response interceptor clears auth state
 */

import axios from 'axios'

// Base URL: in dev, Vite proxy forwards /auth → localhost:8000/auth
// In production, change this to your deployed API URL
const api = axios.create({
  baseURL: '/',
  headers: { 'Content-Type': 'application/json' },
})

// ── Auth token injection ──────────────────────────────────────────────────────
// Token is stored in sessionStorage so it survives Vite HMR reloads.
// sessionStorage is cleared when the browser tab closes (unlike localStorage).
export const setAuthToken = (token) => {
  if (token) {
    sessionStorage.setItem('liq_token', token)
  } else {
    sessionStorage.removeItem('liq_token')
  }
}

export const getAuthToken = () => sessionStorage.getItem('liq_token')

api.interceptors.request.use((config) => {
  const token = getAuthToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Auth endpoints ────────────────────────────────────────────────────────────

export const authApi = {
  register: (data) => api.post('/auth/register', data),
  login: (email, password) =>
    api.post(
      '/auth/login',
      new URLSearchParams({ username: email, password }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    ),
  me: () => api.get('/auth/me'),
}

// ── Store endpoints ───────────────────────────────────────────────────────────

export const storeApi = {
  create: (data) => api.post('/stores', data),
  get: () => api.get('/stores/me'),
  update: (data) => api.put('/stores/me', data),
}

// ── Upload endpoints ──────────────────────────────────────────────────────────

export const uploadApi = {
  upload: (file, source) => {
    const form = new FormData()
    form.append('file', file)
    form.append('source', source)
    return api.post('/uploads/report', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list: () => api.get('/uploads'),
  get: (id) => api.get(`/uploads/${id}`),
  parse: (id) => api.post(`/uploads/${id}/parse`),
}

// ── Analytics endpoints ───────────────────────────────────────────────────────

export const analyticsApi = {
  summary: () => api.get('/analytics/summary'),
  topProducts: (limit = 10) => api.get(`/analytics/top-products?limit=${limit}`),
  slowProducts: (limit = 10) => api.get(`/analytics/slow-products?limit=${limit}`),
  categoryPerformance: () => api.get('/analytics/category-performance'),
  channelPerformance: () => api.get('/analytics/channel-performance'),
}

// ── AI endpoints ──────────────────────────────────────────────────────────────

export const aiApi = {
  generate: (limit = 5) => api.post('/ai/generate-promotion', { limit }),
  list: () => api.get('/ai/strategies'),
  get: (id) => api.get(`/ai/strategies/${id}`),
}

// ── Ad Creative endpoints ─────────────────────────────────────────────────────

export const creativeApi = {
  // DALL-E 3 + GPT-4o — slow call, 15-30s
  generate: (strategyId) => api.post('/creative/generate', { strategy_id: strategyId }),
  // Latest creative for a strategy — 404 if none generated yet
  get: (strategyId) => api.get(`/creative/${strategyId}`),
}

export default api
