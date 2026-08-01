/**
 * LabelStudio.jsx — MODULE 2: LABEL STUDIO
 *
 * Makes SHELF LABELS: the small printed card a store clips to the shelf edge —
 * bottle name, rating, price. No product photo; just clean, readable type.
 *
 * Two deliberate design choices:
 *  1. Structured fields, not a drag-and-drop canvas. Filling in a good template
 *     produces a professional label every time; dragging text boxes produces
 *     something that looks homemade.
 *  2. The SERVER draws the preview (POST /label-studio/preview → PNG). There is
 *     no second layout engine in the browser, so the preview is pixel-identical
 *     to what comes out of the printer.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { labelStudioApi, assetUrl } from '../api/client'
import Layout from '../components/Layout'
import {
  Tag, Plus, Trash2, Save, Printer, Download, Loader2, Search, Check,
} from 'lucide-react'

const DEBOUNCE_MS = 350

export default function LabelStudio() {
  const [options, setOptions] = useState(null)
  const [products, setProducts] = useState([])
  const [labels, setLabels] = useState([])          // saved labels
  const [current, setCurrent] = useState(null)      // {id, spec} being edited
  const [spec, setSpec] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [rendering, setRendering] = useState(false)
  const [selected, setSelected] = useState([])      // ids chosen for the print sheet
  const [productQuery, setProductQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const previewRef = useRef('')   // last object URL, so we can revoke it

  // ── Initial load ───────────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const [o, p, l] = await Promise.all([
          labelStudioApi.options(),
          labelStudioApi.products().catch(() => ({ data: [] })),
          labelStudioApi.list(),
        ])
        setOptions(o.data)
        setProducts(Array.isArray(p.data) ? p.data : [])
        setLabels(Array.isArray(l.data) ? l.data : [])
        setSpec(o.data.blank)
      } catch (e) {
        setError(e.response?.data?.detail ?? e.message ?? 'Could not load Label Studio.')
      } finally {
        setLoading(false)
      }
    })()
    return () => { if (previewRef.current) URL.revokeObjectURL(previewRef.current) }
  }, [])

  // ── Live preview, debounced (the server renders it) ────────────────────────
  const renderPreview = useCallback(async (s) => {
    if (!s) return
    setRendering(true)
    try {
      const res = await labelStudioApi.preview(s)
      const url = URL.createObjectURL(res.data)
      if (previewRef.current) URL.revokeObjectURL(previewRef.current)
      previewRef.current = url
      setPreviewUrl(url)
    } catch {
      /* keep the previous frame rather than flashing an empty box */
    } finally {
      setRendering(false)
    }
  }, [])

  useEffect(() => {
    if (!spec) return
    const t = setTimeout(() => renderPreview(spec), DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [spec, renderPreview])

  const set = (patch) => setSpec((s) => ({ ...s, ...patch }))
  const setRating = (patch) => setSpec((s) => ({ ...s, rating: { ...s.rating, ...patch } }))

  const setDetail = (i, value) => {
    const details = [...(spec.details || [])]
    details[i] = value
    set({ details: details.filter((d, idx) => d?.trim() || idx < details.length - 1) })
  }

  // ── Saved-label actions ────────────────────────────────────────────────────
  const newLabel = () => {
    setCurrent(null)
    setSpec(options.blank)
    setError('')
  }

  const openLabel = (row) => {
    setCurrent(row)
    setSpec(row.design_json)
    setError('')
  }

  const handleSave = async () => {
    setBusy(true); setError('')
    try {
      const { data } = current
        ? await labelStudioApi.save(current.id, spec)
        : await labelStudioApi.create(spec)
      setCurrent(data)
      setSpec(data.design_json)
      setLabels((ls) => {
        const rest = ls.filter((l) => l.id !== data.id)
        return [data, ...rest]
      })
    } catch (e) {
      setError(e.response?.data?.detail ?? 'Could not save the label.')
    } finally { setBusy(false) }
  }

  const handleExport = async () => {
    if (!current) { await handleSave(); return }
    setBusy(true); setError('')
    try {
      const { data } = await labelStudioApi.exportPng(current.id)
      setCurrent(data)
      setLabels((ls) => ls.map((l) => (l.id === data.id ? data : l)))
      window.open(assetUrl(data.final_image_url), '_blank', 'noopener')
    } catch (e) {
      setError(e.response?.data?.detail ?? 'Could not export the label.')
    } finally { setBusy(false) }
  }

  const handleDelete = async (row) => {
    if (!window.confirm(`Delete "${row.name}"?`)) return
    try {
      await labelStudioApi.remove(row.id)
      setLabels((ls) => ls.filter((l) => l.id !== row.id))
      setSelected((s) => s.filter((id) => id !== row.id))
      if (current?.id === row.id) newLabel()
    } catch (e) {
      setError(e.response?.data?.detail ?? 'Could not delete.')
    }
  }

  const handlePrint = async () => {
    setBusy(true); setError('')
    try {
      await labelStudioApi.printSheet(selected)
    } catch (e) {
      setError(e.response?.data?.detail ?? 'Could not build the print sheet.')
    } finally { setBusy(false) }
  }

  const toggleSelect = (id) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  // ── Product prefill ────────────────────────────────────────────────────────
  const filteredProducts = useMemo(() => {
    const q = productQuery.trim().toLowerCase()
    if (!q) return products.slice(0, 6)
    return products.filter((p) => p.product_name.toLowerCase().includes(q)).slice(0, 6)
  }, [products, productQuery])

  const usePrefill = (p) => {
    set({ product_name: p.product_name, price: p.price || spec.price })
    setProductQuery('')
  }

  const sizeInfo = options?.sizes?.find((s) => s.key === spec?.size)

  if (loading) {
    return <Layout><p className="text-sm text-gray-400">Loading Label Studio…</p></Layout>
  }
  if (!options || !spec) {
    return (
      <Layout>
        <div className="max-w-xl bg-red-50 text-red-600 rounded-xl p-4 text-sm">
          {error || 'Label Studio is unavailable.'}
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto">
        <div className="flex items-start justify-between gap-4 flex-wrap mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 mb-1 flex items-center gap-2">
              <Tag size={20} className="text-brand-500" /> Label Studio
            </h1>
            <p className="text-sm text-gray-500">
              Shelf labels with the bottle name, rating and price — print a sheet and clip them to the shelf.
            </p>
          </div>
          <button onClick={newLabel}
            className="flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-xl border border-gray-200 hover:border-brand-300">
            <Plus size={14} /> New label
          </button>
        </div>

        {error && <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{error}</div>}

        <div className="flex flex-col lg:flex-row gap-6 items-start">
          {/* ── Preview ── */}
          <div className="lg:sticky lg:top-4">
            <div className="bg-gray-100 rounded-2xl p-4 inline-block relative">
              {previewUrl ? (
                <img src={previewUrl} alt="Label preview"
                  className="rounded-lg shadow-sm bg-white"
                  style={{ width: 380, height: 'auto', display: 'block' }} />
              ) : (
                <div className="w-[380px] h-[285px] flex items-center justify-center text-sm text-gray-400">
                  Building preview…
                </div>
              )}
              {rendering && (
                <span className="absolute top-6 right-6 text-gray-400">
                  <Loader2 size={15} className="animate-spin" />
                </span>
              )}
            </div>
            <p className="text-[11px] text-gray-400 mt-2 text-center">
              Exactly what prints · {sizeInfo?.inches?.[0]}″ × {sizeInfo?.inches?.[1]}″
              {sizeInfo && ` · ${sizeInfo.per_page} per page`}
            </p>
            <div className="flex items-center gap-2 mt-3">
              <button onClick={handleSave} disabled={busy}
                className="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold px-3 py-2.5 rounded-xl bg-brand-500 text-white disabled:opacity-60">
                <Save size={14} /> {current ? 'Save changes' : 'Save label'}
              </button>
              <button onClick={handleExport} disabled={busy}
                className="flex items-center gap-1.5 text-xs font-semibold px-3 py-2.5 rounded-xl border border-gray-200">
                <Download size={14} /> PNG
              </button>
            </div>
          </div>

          {/* ── Fields ── */}
          <div className="flex-1 min-w-0 space-y-5">
            {/* Prefill from their own sales data */}
            {products.length > 0 && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  Pick from your products <span className="text-gray-300 font-normal">— name &amp; price prefilled from your sales</span>
                </label>
                <div className="relative">
                  <Search size={14} className="absolute left-3 top-2.5 text-gray-300" />
                  <input value={productQuery} onChange={(e) => setProductQuery(e.target.value)}
                    placeholder="Search your best sellers…"
                    className="w-full border border-gray-200 rounded-xl pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                {filteredProducts.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {filteredProducts.map((p) => (
                      <button key={p.product_name} onClick={() => usePrefill(p)}
                        className="text-[11px] px-2.5 py-1 rounded-full border border-gray-200 hover:border-brand-400 hover:text-brand-600 truncate max-w-[240px]">
                        {p.product_name}{p.price ? ` · ${p.price}` : ''}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-gray-500 mb-1">Bottle name</label>
                <input value={spec.product_name} onChange={(e) => set({ product_name: e.target.value })}
                  placeholder="Buffalo Trace Kentucky Straight Bourbon"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Price</label>
                <input value={spec.price} onChange={(e) => set({ price: e.target.value })}
                  placeholder="$27.99"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  Was <span className="text-gray-300 font-normal">(optional)</span>
                </label>
                <input value={spec.was_price} onChange={(e) => set({ was_price: e.target.value })}
                  placeholder="$32.99"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  Banner <span className="text-gray-300 font-normal">(optional — STAFF PICK, NEW ARRIVAL…)</span>
                </label>
                <input value={spec.tagline} onChange={(e) => set({ tagline: e.target.value })}
                  placeholder="STAFF PICK"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
            </div>

            {/* Rating */}
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Rating</label>
              <div className="flex items-center gap-2 flex-wrap">
                <div className="inline-flex rounded-xl border border-gray-200 overflow-hidden text-xs font-semibold">
                  {[['none', 'None'], ['stars', 'Stars'], ['points', 'Points']].map(([v, l]) => (
                    <button key={v} onClick={() => setRating({ kind: v })}
                      className={`px-3 py-1.5 transition-colors ${
                        spec.rating.kind === v ? 'bg-brand-500 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'}`}>
                      {l}
                    </button>
                  ))}
                </div>
                {spec.rating.kind === 'stars' && (
                  <div className="flex items-center gap-2">
                    <input type="range" min="0" max="5" step="0.5" value={spec.rating.value}
                      onChange={(e) => setRating({ value: Number(e.target.value) })} />
                    <span className="text-xs tabular-nums w-8">{spec.rating.value}★</span>
                  </div>
                )}
                {spec.rating.kind === 'points' && (
                  <div className="flex items-center gap-2">
                    <input type="range" min="50" max="100" step="1" value={spec.rating.value}
                      onChange={(e) => setRating({ value: Number(e.target.value) })} />
                    <span className="text-xs tabular-nums w-12">{spec.rating.value} pts</span>
                  </div>
                )}
                {spec.rating.kind !== 'none' && (
                  <input value={spec.rating.source} onChange={(e) => setRating({ source: e.target.value })}
                    placeholder="Source (Vivino…)"
                    className="border border-gray-200 rounded-xl px-3 py-1.5 text-xs w-40" />
                )}
              </div>
            </div>

            {/* Details */}
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Item details <span className="text-gray-300 font-normal">(optional — up to 3)</span>
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[0, 1, 2].map((i) => (
                  <input key={i} value={spec.details?.[i] ?? ''}
                    onChange={(e) => {
                      const details = [...(spec.details || [])]
                      while (details.length < 3) details.push('')
                      details[i] = e.target.value
                      set({ details: details.filter((d) => d && d.trim()) })
                    }}
                    placeholder={['90 proof', '750 ML', 'Aged 12 yrs'][i]}
                    className="border border-gray-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500" />
                ))}
              </div>
            </div>

            {/* Look */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Size</label>
                <select value={spec.size} onChange={(e) => set({ size: e.target.value })}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm">
                  {options.sizes.map((s) => (
                    <option key={s.key} value={s.key}>{s.label} · {s.inches[0]}×{s.inches[1]}″</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Theme</label>
                <select value={spec.theme} onChange={(e) => set({ theme: e.target.value })}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm">
                  {options.themes.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Icon</label>
                <select value={spec.icon} onChange={(e) => set({ icon: e.target.value })}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm">
                  {options.icons.map((i) => (
                    <option key={i.key} value={i.key}>{i.emoji ? `${i.emoji} ` : ''}{i.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <label className="flex items-center gap-2 text-xs text-gray-600">
              <input type="checkbox" checked={spec.show_border}
                onChange={(e) => set({ show_border: e.target.checked })} />
              Print a border (handy as a cut line)
            </label>
            <p className="text-[11px] text-gray-400">
              Icons are drawn as crisp vector art rather than emoji — emoji have no glyphs in the
              print font and would come out as empty boxes on paper.
            </p>
          </div>
        </div>

        {/* ── Saved labels + print sheet ── */}
        <div className="mt-10">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
              Saved labels {labels.length > 0 && `(${labels.length})`}
            </p>
            <button onClick={handlePrint} disabled={busy || selected.length === 0}
              className="flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-xl bg-gray-900 text-white disabled:opacity-40">
              <Printer size={14} />
              {selected.length ? `Print ${selected.length} label${selected.length === 1 ? '' : 's'}` : 'Select labels to print'}
            </button>
          </div>

          {labels.length === 0 ? (
            <p className="text-sm text-gray-500">
              No saved labels yet — fill in the fields above and hit <span className="font-medium">Save label</span>.
            </p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {labels.map((row) => {
                const isSel = selected.includes(row.id)
                return (
                  <div key={row.id}
                    className={`group relative bg-white rounded-xl border p-3 transition-colors ${
                      current?.id === row.id ? 'border-brand-400' : 'border-gray-100'}`}>
                    <button onClick={() => toggleSelect(row.id)}
                      className={`absolute top-2 right-2 w-5 h-5 rounded-md border flex items-center justify-center transition-colors ${
                        isSel ? 'bg-brand-500 border-brand-500 text-white' : 'border-gray-300 bg-white'}`}
                      title="Include in print sheet">
                      {isSel && <Check size={12} />}
                    </button>
                    <button onClick={() => openLabel(row)} className="text-left w-full pr-6">
                      <p className="text-xs font-semibold text-gray-800 truncate">
                        {row.design_json?.product_name || 'Untitled'}
                      </p>
                      <p className="text-sm font-bold text-brand-600">{row.design_json?.price}</p>
                      <p className="text-[10px] text-gray-400 mt-1 capitalize">
                        {row.design_json?.theme} · {row.design_json?.size}
                      </p>
                    </button>
                    <button onClick={() => handleDelete(row)}
                      className="absolute bottom-2 right-2 p-1 text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                      title="Delete">
                      <Trash2 size={13} />
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
