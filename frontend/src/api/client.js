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

// Base URL:
//   dev  — empty string → relative URLs → Vite proxy forwards to localhost:8000
//   prod — VITE_API_URL env var on Vercel, e.g. https://liquoriq.up.railway.app
export const API_BASE = import.meta.env.VITE_API_URL ?? ''

const api = axios.create({
  baseURL: API_BASE || '/',
  headers: { 'Content-Type': 'application/json' },
})

// For non-axios assets (<img src> of generated ad images).
// Two URL shapes come from the backend:
//   - absolute (Cloudinary CDN, prod): use as-is
//   - relative (/static/creatives/..., local dev): prepend the API base
export const assetUrl = (path) =>
  path?.startsWith('http') ? path : `${API_BASE}${path}`

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

// ── Store selection (Phase 14: multi-store) ──────────────────────────────────
// Owners switch stores; the chosen store id rides on every request as
// X-Store-Id and the backend scopes all data to it. Staff never set this —
// the backend pins them to their assigned store.
export const setSelectedStore = (storeId) => {
  if (storeId) sessionStorage.setItem('liq_store', storeId)
  else sessionStorage.removeItem('liq_store')
}
export const getSelectedStore = () => sessionStorage.getItem('liq_store')

api.interceptors.request.use((config) => {
  const token = getAuthToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  const storeId = getSelectedStore()
  if (storeId) {
    config.headers['X-Store-Id'] = storeId
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
  // Phase 14: multi-store + staff
  list: () => api.get('/stores'),
  createStaff: (storeId, data) => api.post(`/stores/${storeId}/staff`, data),
  listStaff: (storeId) => api.get(`/stores/${storeId}/staff`),
  deactivateStaff: (userId) => api.delete(`/stores/staff/${userId}`),
}

// ── Transfer endpoints (Phase 14) ─────────────────────────────────────────────

export const transferApi = {
  // Partners (Phase 14: both stores must be on LiquorIQ; code mandatory)
  partners: () => api.get('/transfers/partners'),
  addPartner: (code, name) => api.post('/transfers/partners', { code, name: name || null }),
  removePartner: (partnerId) => api.delete(`/transfers/partners/${partnerId}`),
  // Exchanges — data: { partner_id, direction: 'outgoing'|'incoming', transfer_date, note, items }
  create: (data) => api.post('/transfers', data),
  list: (partnerId) => api.get('/transfers', { params: { partner_id: partnerId } }),
  undoTransfer: (transferId) => api.delete(`/transfers/${transferId}`),
  ledger: (partnerId) => api.get(`/transfers/ledger/${partnerId}`),
  settle: (partnerId, data) => api.post(`/transfers/settle/${partnerId}`, data),
  payments: (partnerId) => api.get(`/transfers/payments/${partnerId}`),
  undoPayment: (paymentId) => api.delete(`/transfers/payments/${paymentId}`),
  // Downloads the month's CSV statement (auth header required → blob, not <a href>)
  downloadReport: async (partnerId, month) => {
    const res = await api.get(`/transfers/report/${partnerId}`, {
      params: { month, format: 'csv' },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `exchange_${month}.csv`
    a.click()
    URL.revokeObjectURL(url)
  },
}

// ── Upload endpoints ──────────────────────────────────────────────────────────

export const uploadApi = {
  upload: (file, source) => {
    const form = new FormData()
    form.append('file', file)
    // BUG FIX (Phase 13): the backend reads `source` as a QUERY param, not a
    // form field — sending it in the form silently defaulted every upload to
    // "other" (wrong parser). Pass it via params.
    return api.post('/uploads/report', form, {
      params: { source },
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
  // Phase 17: inventory intelligence + action center
  inventory: () => api.get('/analytics/inventory'),
  // Phase 18: sales trend + latest campaign ROI
  trend: () => api.get('/analytics/trend'),
  campaignSummary: () => api.get('/analytics/campaign-summary'),
}

// ── AI endpoints ──────────────────────────────────────────────────────────────

export const aiApi = {
  // Phase 15: steerable — deal_ids, a chosen occasion, and a free-text brief
  generate: (opts = {}) => api.post('/ai/generate-promotion', {
    limit: opts.limit ?? 5,
    deal_ids: opts.dealIds ?? null,
    occasion: opts.occasion ?? null,
    instructions: opts.instructions ?? null,
    target_segment: opts.targetSegment ?? null,
  }),
  list: () => api.get('/ai/strategies'),
  get: (id) => api.get(`/ai/strategies/${id}`),
  holidays: () => api.get('/ai/holidays'),
  // Phase 12: campaign ROI — lift vs pre-campaign baseline, derived live
  performance: (id) => api.get(`/ai/strategies/${id}/performance`),
}

// ── Deal buys (Phase 15: supplier closeouts → high-margin campaigns) ──────────

export const dealApi = {
  list: () => api.get('/deals'),
  create: (data) => api.post('/deals', data),
  remove: (id) => api.delete(`/deals/${id}`),
}

// ── Campaign distribution (Phase 21) ──────────────────────────────────────────

export const campaignApi = {
  preview: (strategyId, channel) => api.get('/campaigns/preview', { params: { strategy_id: strategyId, channel } }),
  send: (strategyId, channel) => api.post('/campaigns/send', { strategy_id: strategyId, channel }),
  history: () => api.get('/campaigns'),
}

// ── Customers + RFM segmentation (Phase 19) ───────────────────────────────────

export const customerApi = {
  upload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/customers/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  segments: () => api.get('/customers/segments'),
  list: (segment = null, search = null) =>
    api.get('/customers', { params: { segment: segment || undefined, search: search || undefined } }),
  create: (data) => api.post('/customers', data),
  // Phase 20: aggregated audience stats for a segment (no PII)
  audience: (segment) => api.get(`/customers/audience/${encodeURIComponent(segment)}`),
}

// ── Ad Creative endpoints ─────────────────────────────────────────────────────

export const creativeApi = {
  // gpt-image-1 + GPT-4o — slow call, 40-60s. offer + instructions + real photo + format.
  generate: (strategyId, { offerOverride = null, instructions = null, productImageUrl = null, imageFormat = 'square' } = {}) =>
    api.post('/creative/generate', {
      strategy_id: strategyId,
      offer_override: offerOverride,
      instructions,
      product_image_url: productImageUrl,
      image_format: imageFormat,
    }),
  // Phase 16: upload a real bottle photo; if productName given it's saved to the
  // reusable library and auto-used for every future ad of that product.
  uploadProductPhoto: (file, productName = null) => {
    const form = new FormData()
    form.append('file', file)
    if (productName) form.append('product_name', productName)
    return api.post('/creative/product-photo', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  // The saved library photo for a product (null if none on file)
  getProductPhoto: (productName) => api.get('/creative/product-photo', { params: { product_name: productName } }),
  // Latest creative for a strategy — 404 if none generated yet
  get: (strategyId) => api.get(`/creative/${strategyId}`),
  // Phase 11: price prefill from the store's own sales data
  prices: (strategyId) => api.get(`/creative/${strategyId}/prices`),
  // Phase 11: compose final ad with exact prices overlaid (Pillow, server-side)
  compose: (creativeId, items) => api.post(`/creative/${creativeId}/compose`, { items }),
}

export default api
