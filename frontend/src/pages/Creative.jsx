/**
 * Creative.jsx — Ad Creative studio (Phase 10)
 *
 * Flow:
 *   1. Pick a strategy (pre-selected if arriving via /creative?strategy=<id>)
 *   2. If a creative already exists for it → shown immediately
 *   3. Generate / Regenerate → DALL-E 3 image + platform copy (15-30s)
 *   4. One-click copy for every platform, image download button
 */

import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { aiApi, creativeApi, assetUrl } from '../api/client'
import Layout from '../components/Layout'
import { Megaphone, Download, RefreshCw, Image as ImageIcon, Tags, Trash2 } from 'lucide-react'

// ── Copy-to-clipboard box (same pattern as AIStrategy.jsx) ────────────────────
function CopyBox({ label, text }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div className="bg-gray-50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-gray-500">{label}</p>
        <button onClick={copy} className="text-xs text-brand-500 hover:underline">
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{text}</p>
    </div>
  )
}

export default function Creative() {
  const [searchParams] = useSearchParams()
  const preselected = searchParams.get('strategy')

  const [strategies, setStrategies] = useState([])
  const [selectedId, setSelectedId] = useState(preselected ?? '')
  const [creative, setCreative] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  // Phase 11 — price overlay state
  const [priceRows, setPriceRows] = useState([])       // [{product_name, price}]
  const [composing, setComposing] = useState(false)
  const [composeError, setComposeError] = useState('')

  // Load strategy list once; default to preselected or newest
  useEffect(() => {
    (async () => {
      try {
        const { data } = await aiApi.list()
        setStrategies(data)
        if (!preselected && data.length > 0) setSelectedId(data[0].id)
      } catch {
        // ignore — empty state shown below
      } finally {
        setLoading(false)
      }
    })()
  }, [preselected])

  // When the selected strategy changes, fetch its latest creative (404 = none yet)
  useEffect(() => {
    if (!selectedId) return
    setCreative(null)
    setError('')
    setPriceRows([])
    setComposeError('')
    ;(async () => {
      try {
        const { data } = await creativeApi.get(selectedId)
        setCreative(data)
      } catch {
        // 404 — no creative yet, that's fine
      }
    })()
  }, [selectedId])

  // Phase 11: when a creative exists, prefill prices — from the last compose
  // if there was one, otherwise from the store's own sales data
  useEffect(() => {
    if (!creative) return
    if (creative.price_items?.length) {
      setPriceRows(creative.price_items.map((r) => ({ ...r, price: r.price ?? '' })))
      return
    }
    ;(async () => {
      try {
        const { data } = await creativeApi.prices(creative.strategy_id)
        setPriceRows(data.map((r) => ({ ...r, price: r.price ?? '' })))
      } catch {
        // fall back to empty editor — owner can still type rows manually
        setPriceRows([{ product_name: '', price: '' }])
      }
    })()
  }, [creative])

  const handleGenerate = async () => {
    setError('')
    setGenerating(true)
    try {
      const { data } = await creativeApi.generate(selectedId)
      setCreative(data)
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Failed to generate creative.')
    } finally {
      setGenerating(false)
    }
  }

  // ── Phase 11: price editor handlers ──
  const updateRow = (i, field, value) => {
    setPriceRows((rows) => rows.map((r, idx) => (idx === i ? { ...r, [field]: value } : r)))
  }
  const removeRow = (i) => setPriceRows((rows) => rows.filter((_, idx) => idx !== i))
  const addRow = () => setPriceRows((rows) => [...rows, { product_name: '', price: '' }])

  const validRows = priceRows
    .filter((r) => r.product_name.trim() && r.price !== '' && Number(r.price) > 0)
    .map((r) => ({ product_name: r.product_name.trim(), price: Number(r.price) }))

  const handleCompose = async () => {
    setComposeError('')
    setComposing(true)
    try {
      const { data } = await creativeApi.compose(creative.id, validRows.slice(0, 5))
      setCreative(data)
    } catch (err) {
      setComposeError(err.response?.data?.detail ?? 'Failed to compose final ad.')
    } finally {
      setComposing(false)
    }
  }

  const selectedStrategy = strategies.find((s) => s.id === selectedId)

  return (
    <Layout>
      <div className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Ad Creative</h1>
        <p className="text-sm text-gray-500 mb-8">
          Turn a strategy into a ready-to-post ad — image + copy for every platform
        </p>

        {/* ── Generate panel ── */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-8">
          <div className="flex items-center gap-3 mb-4">
            <Megaphone size={20} className="text-brand-500" />
            <h2 className="text-sm font-semibold text-gray-700">Create ad creative</h2>
          </div>

          {error && <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{error}</div>}

          {loading ? (
            <p className="text-gray-400 text-sm">Loading strategies…</p>
          ) : strategies.length === 0 ? (
            <p className="text-sm text-gray-500">
              No strategies yet — generate one on the <span className="font-medium">AI Strategy</span> page first.
            </p>
          ) : (
            <div className="flex items-end gap-4 flex-wrap">
              <div className="flex-1 min-w-64">
                <label className="block text-xs text-gray-500 mb-1">Strategy</label>
                <select
                  value={selectedId}
                  onChange={(e) => setSelectedId(e.target.value)}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  {strategies.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.strategy_title} · {new Date(s.created_at).toLocaleDateString()}
                    </option>
                  ))}
                </select>
              </div>
              <button
                onClick={handleGenerate}
                disabled={generating || !selectedId}
                className="flex items-center gap-2 bg-brand-500 hover:bg-brand-600 text-white font-semibold px-5 py-2.5 rounded-xl text-sm transition-colors disabled:opacity-60"
              >
                {creative ? <RefreshCw size={16} /> : <ImageIcon size={16} />}
                {generating
                  ? 'Generating… (15-30s)'
                  : creative
                  ? 'Regenerate'
                  : 'Generate creative'}
              </button>
            </div>
          )}
        </div>

        {/* ── Result ── */}
        {generating && !creative && (
          <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center">
            <p className="text-3xl mb-3 animate-pulse">🎨</p>
            <p className="text-gray-600 font-medium">Painting your ad…</p>
            <p className="text-gray-400 text-sm mt-1">DALL-E 3 is generating the image — this takes up to 30 seconds.</p>
          </div>
        )}

        {creative && (
          <div className="space-y-6">
            {/* ── Final composed ad (Phase 11) — the postable one ── */}
            {creative.final_image_url && (
              <div className="bg-white rounded-2xl border-2 border-brand-200 shadow-sm overflow-hidden">
                <div className="px-6 py-3 bg-brand-50 flex items-center gap-2">
                  <Tags size={15} className="text-brand-600" />
                  <p className="text-xs font-semibold text-brand-700 uppercase tracking-wide">
                    Final ad — ready to post
                  </p>
                </div>
                <img
                  src={assetUrl(creative.final_image_url)}
                  alt="Final ad with prices"
                  className="w-full aspect-square object-cover"
                />
                <div className="flex items-center justify-end px-6 py-4">
                  <a
                    href={assetUrl(creative.final_image_url)}
                    download="liquoriq-final-ad.png"
                    className="flex items-center gap-1.5 text-xs font-semibold text-brand-500 hover:underline"
                  >
                    <Download size={14} />
                    Download final PNG
                  </a>
                </div>
              </div>
            )}

            {/* ── Price editor (Phase 11) ── */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <div className="flex items-center gap-3 mb-1">
                <Tags size={18} className="text-brand-500" />
                <h2 className="text-sm font-semibold text-gray-700">Prices on the ad</h2>
              </div>
              <p className="text-xs text-gray-400 mb-4">
                Prefilled from your sales data — adjust to your promo prices, then compose.
                Text is stamped on exactly as typed (max 5 items).
              </p>

              {composeError && (
                <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{composeError}</div>
              )}

              <div className="space-y-2">
                {priceRows.map((row, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={row.product_name}
                      onChange={(e) => updateRow(i, 'product_name', e.target.value)}
                      placeholder="Product name"
                      className="flex-1 border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
                      <input
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={row.price}
                        onChange={(e) => updateRow(i, 'price', e.target.value)}
                        placeholder="0.00"
                        className="w-28 border border-gray-200 rounded-xl pl-7 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                    </div>
                    <button
                      onClick={() => removeRow(i)}
                      className="text-gray-300 hover:text-red-400 transition-colors"
                      title="Remove"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>

              <div className="flex items-center justify-between mt-4">
                <button
                  onClick={addRow}
                  className="text-xs font-semibold text-brand-500 hover:underline"
                >
                  + Add item
                </button>
                <button
                  onClick={handleCompose}
                  disabled={composing || validRows.length === 0}
                  className="flex items-center gap-2 bg-brand-500 hover:bg-brand-600 text-white font-semibold px-5 py-2.5 rounded-xl text-sm transition-colors disabled:opacity-60"
                >
                  <Tags size={15} />
                  {composing
                    ? 'Composing…'
                    : creative.final_image_url
                    ? 'Recompose final ad'
                    : 'Compose final ad'}
                </button>
              </div>
            </div>

            {/* ── Original AI background ── */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <div className="px-6 py-3 border-b border-gray-100">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
                  AI background (no prices)
                </p>
              </div>
              <img
                src={assetUrl(creative.image_url)}
                alt="Generated ad creative"
                className="w-full aspect-square object-cover"
              />
              <div className="flex items-center justify-between px-6 py-4">
                <p className="text-xs text-gray-400">
                  {new Date(creative.created_at).toLocaleString()} · {creative.model_used} · 1024×1024
                </p>
                <a
                  href={assetUrl(creative.image_url)}
                  download="liquoriq-ad.png"
                  className="flex items-center gap-1.5 text-xs font-semibold text-brand-500 hover:underline"
                >
                  <Download size={14} />
                  Download PNG
                </a>
              </div>
            </div>

            {/* Platform copy */}
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
                Platform copy {selectedStrategy && `— ${selectedStrategy.strategy_title}`}
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <CopyBox label="📸 Instagram" text={creative.instagram_caption} />
                <CopyBox label="👥 Facebook" text={creative.facebook_post} />
                <CopyBox label="🛵 Uber Eats" text={creative.ubereats_description} />
                <CopyBox label="🚗 DoorDash" text={creative.doordash_description} />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                <CopyBox label="🌐 Website banner — headline" text={creative.website_banner_headline} />
                <CopyBox label="🌐 Website banner — text" text={creative.website_banner_text} />
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
