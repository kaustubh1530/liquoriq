/**
 * LabelStudio.jsx — MODULE 2: LABEL STUDIO
 *
 * Shelf labels: the printed card clipped to the shelf edge. Modelled on the
 * tags the store already makes in Canva (serif, black on white, red sale price,
 * starburst, REGULAR / SAVE).
 *
 * A label is a list of MOVABLE elements. Styles are one-click starting points,
 * not cages: every piece can be dragged, edited, recoloured, duplicated or
 * deleted. The server renders the preview AND reports where it drew each
 * element, so the drag handles line up exactly with the print.
 *
 * LAYOUT NOTE: this page is a two-column CSS GRID with an explicit left width
 * and `minmax(0,1fr)` on the right. An earlier flex version let a wide row of
 * art chips blow the left column out, which squeezed the editing panel down to
 * one word per line and made delete/edit unreachable. The grid can't do that.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { labelStudioApi, assetUrl } from '../api/client'
import Layout from '../components/Layout'
import LabelCanvas from './labelstudio/LabelCanvas'
import {
  Tag, Trash2, Save, Printer, Download, Loader2, Search, Check, Bookmark,
  Copy, ArrowUp, ArrowDown, Type, Image as ImageIcon, Star, Minus,
  Undo2, Grid3x3, Magnet, Wand2, Plus,
} from 'lucide-react'

const DEBOUNCE_MS = 260
const HISTORY_MAX = 30
const CANVAS_W = 420

export default function LabelStudio() {
  const [options, setOptions] = useState(null)
  const [products, setProducts] = useState([])
  const [labels, setLabels] = useState([])
  const [templates, setTemplates] = useState([])
  const [current, setCurrent] = useState(null)
  const [spec, setSpec] = useState(null)
  const [preview, setPreview] = useState({ image: '', boxes: [] })
  const [selectedId, setSelectedId] = useState(null)
  const [history, setHistory] = useState([])
  const [rendering, setRendering] = useState(false)
  const [selected, setSelected] = useState([])
  const [productQuery, setProductQuery] = useState('')
  const [snapEnabled, setSnapEnabled] = useState(true)
  const [showGrid, setShowGrid] = useState(false)
  const [showStart, setShowStart] = useState(false)
  const [starter, setStarter] = useState({ product_name: '', price: '', regular_price: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const specRef = useRef(null)
  specRef.current = spec

  useEffect(() => {
    (async () => {
      try {
        const [o, p, l, t] = await Promise.all([
          labelStudioApi.options(),
          labelStudioApi.products().catch(() => ({ data: [] })),
          labelStudioApi.list(),
          labelStudioApi.templates().catch(() => ({ data: [] })),
        ])
        const arr = (v) => (Array.isArray(v) ? v : [])
        setOptions(o.data)
        setProducts(arr(p.data))
        setLabels(arr(l.data))
        setTemplates(arr(t.data))
        setSpec(o.data.blank)
      } catch (e) {
        setError(e.response?.data?.detail ?? e.message ?? 'Could not load Label Studio.')
      } finally { setLoading(false) }
    })()
  }, [])

  const renderPreview = useCallback(async (s) => {
    if (!s) return
    setRendering(true)
    try {
      const { data } = await labelStudioApi.preview(s)
      setPreview({ image: data.image, boxes: data.boxes || [] })
    } catch { /* keep the last good frame */ }
    finally { setRendering(false) }
  }, [])

  useEffect(() => {
    if (!spec) return
    const t = setTimeout(() => renderPreview(spec), DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [spec, renderPreview])

  const elements = spec?.elements ?? []
  const selectedEl = elements.find((e) => e.id === selectedId) || null

  const pushHistory = () => setHistory((h) => [...h.slice(-HISTORY_MAX), specRef.current])

  const setSpecTracked = (next) => { pushHistory(); setSpec(next) }

  const patchEl = (id, patch, track = false) => {
    if (track) pushHistory()
    setSpec((s) => ({
      ...s, elements: s.elements.map((e) => (e.id === id ? { ...e, ...patch } : e)),
    }))
  }

  const handleMove = (id, x, y) => patchEl(id, { x, y }, true)

  const addElement = (el) => {
    const id = `el-${Date.now().toString(36)}`
    setSpecTracked({ ...spec, elements: [...elements, { ...options.element_defaults, ...el, id }] })
    setSelectedId(id)
  }

  const duplicateEl = (id = selectedId) => {
    const src = elements.find((e) => e.id === id)
    if (!src) return
    const newId = `el-${Date.now().toString(36)}`
    setSpecTracked({
      ...spec,
      elements: [...elements, { ...src, id: newId, x: src.x + 0.04, y: src.y + 0.04 }],
    })
    setSelectedId(newId)
  }

  const deleteEl = (id = selectedId) => {
    if (!id) return
    setSpecTracked({ ...spec, elements: elements.filter((e) => e.id !== id) })
    setSelectedId(null)
  }

  const reorderEl = (dir) => {
    if (!selectedEl) return
    const i = elements.findIndex((e) => e.id === selectedId)
    const j = dir === 'up' ? i + 1 : i - 1
    if (j < 0 || j >= elements.length) return
    const next = [...elements]
    ;[next[i], next[j]] = [next[j], next[i]]
    setSpecTracked({ ...spec, elements: next })
  }

  const undo = () => setHistory((h) => {
    if (!h.length) return h
    setSpec(h[h.length - 1])
    setSelectedId(null)
    return h.slice(0, -1)
  })

  // Delete key removes the selected piece — but never while typing in a field
  useEffect(() => {
    const onKey = (e) => {
      const tag = e.target.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId) {
        e.preventDefault(); deleteEl()
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); undo() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const applyStyle = async (styleKey) => {
    setBusy(true); setError('')
    try {
      const { data } = await labelStudioApi.fromStyle(styleKey, starter, {
        size: spec.size, font: spec.font, accent: spec.accent, show_border: spec.show_border,
      })
      setSpecTracked(data.spec); setSelectedId(null)
    } catch (e) {
      setError(e.response?.data?.detail ?? 'Could not build that style.')
    } finally { setBusy(false) }
  }

  const handleSave = async () => {
    setBusy(true); setError('')
    try {
      const { data } = current
        ? await labelStudioApi.save(current.id, spec)
        : await labelStudioApi.create(spec)
      setCurrent(data); setSpec(data.design_json)
      setLabels((ls) => [data, ...ls.filter((l) => l.id !== data.id)])
    } catch (e) { setError(e.response?.data?.detail ?? 'Could not save.') }
    finally { setBusy(false) }
  }

  const handleExport = async () => {
    if (!current) { await handleSave(); return }
    setBusy(true)
    try {
      const { data } = await labelStudioApi.exportPng(current.id)
      setCurrent(data)
      setLabels((ls) => ls.map((l) => (l.id === data.id ? data : l)))
      window.open(assetUrl(data.final_image_url), '_blank', 'noopener')
    } catch (e) { setError(e.response?.data?.detail ?? 'Could not export.') }
    finally { setBusy(false) }
  }

  const handleSaveStyle = async () => {
    const name = window.prompt('Name this style (e.g. "Staff pick")')
    if (!name) return
    setBusy(true)
    try {
      const { data } = await labelStudioApi.saveTemplate(spec, name)
      setTemplates((t) => [data, ...t])
    } catch (e) { setError(e.response?.data?.detail ?? 'Could not save the style.') }
    finally { setBusy(false) }
  }

  const handleUseStyle = async (tpl) => {
    setBusy(true)
    try {
      const { data } = await labelStudioApi.applyTemplate(tpl.id, spec)
      setSpecTracked(data.spec); setSelectedId(null)
    } catch (e) { setError(e.response?.data?.detail ?? 'Could not apply.') }
    finally { setBusy(false) }
  }

  const handleDeleteStyle = async (tpl) => {
    if (!window.confirm(`Delete the style "${tpl.name}"?`)) return
    try {
      await labelStudioApi.deleteTemplate(tpl.id)
      setTemplates((t) => t.filter((x) => x.id !== tpl.id))
    } catch (e) { setError(e.response?.data?.detail ?? 'Could not delete.') }
  }

  const handleDelete = async (row) => {
    if (!window.confirm(`Delete "${row.name}"?`)) return
    try {
      await labelStudioApi.remove(row.id)
      setLabels((ls) => ls.filter((l) => l.id !== row.id))
      setSelected((s) => s.filter((id) => id !== row.id))
    } catch (e) { setError(e.response?.data?.detail ?? 'Could not delete.') }
  }

  const handlePrint = async () => {
    setBusy(true)
    try { await labelStudioApi.printSheet(selected) }
    catch (e) { setError(e.response?.data?.detail ?? 'Could not build the sheet.') }
    finally { setBusy(false) }
  }

  const filteredProducts = useMemo(() => {
    const q = productQuery.trim().toLowerCase()
    if (!q) return []
    return products.filter((p) => p.product_name.toLowerCase().includes(q)).slice(0, 5)
  }, [products, productQuery])

  const sizeInfo = options?.sizes?.find((s) => s.key === spec?.size)
  const aspect = sizeInfo ? sizeInfo.inches[0] / sizeInfo.inches[1] : 4 / 3

  if (loading) return <Layout><p className="text-sm text-gray-400">Loading Label Studio…</p></Layout>
  if (!options || !spec) {
    return <Layout><div className="max-w-xl bg-red-50 text-red-600 rounded-xl p-4 text-sm">
      {error || 'Label Studio is unavailable.'}</div></Layout>
  }

  const field = 'w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500'
  const lbl = 'block text-[11px] font-semibold text-gray-500 mb-1.5'
  const chip = 'flex items-center gap-1 text-[11px] font-medium px-2.5 py-1.5 rounded-lg border border-gray-200 hover:border-brand-400 hover:text-brand-600 whitespace-nowrap'

  return (
    <Layout>
      <div className="max-w-6xl mx-auto">
        <div className="flex items-start justify-between gap-4 flex-wrap mb-5">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 mb-1 flex items-center gap-2">
              <Tag size={20} className="text-brand-500" /> Label Studio
            </h1>
            <p className="text-sm text-gray-500">
              Click a piece to edit it · drag to move · Delete key removes it
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={undo} disabled={!history.length} title="Undo (⌘Z)"
              className="p-2 rounded-lg border border-gray-200 disabled:opacity-40"><Undo2 size={15} /></button>
            <button onClick={() => setShowGrid(!showGrid)} title="Grid"
              className={`p-2 rounded-lg border ${showGrid ? 'bg-brand-50 border-brand-300 text-brand-600' : 'border-gray-200 text-gray-500'}`}><Grid3x3 size={15} /></button>
            <button onClick={() => setSnapEnabled(!snapEnabled)} title="Snap to guides"
              className={`p-2 rounded-lg border ${snapEnabled ? 'bg-brand-50 border-brand-300 text-brand-600' : 'border-gray-200 text-gray-500'}`}><Magnet size={15} /></button>
          </div>
        </div>

        {error && <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{error}</div>}

        {/* Explicit grid: the right column can never be squeezed to nothing */}
        <div className="grid grid-cols-1 lg:grid-cols-[420px_minmax(0,1fr)] gap-6 items-start">

          {/* ── Left: the label ── */}
          <div>
            <div className="bg-gray-100 rounded-2xl p-4 relative">
              <LabelCanvas
                image={preview.image}
                boxes={preview.boxes}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onMove={handleMove}
                onDelete={deleteEl}
                onDuplicate={duplicateEl}
                width={CANVAS_W - 32}
                aspect={aspect}
                snapEnabled={snapEnabled}
                showGrid={showGrid}
              />
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

            <div className="flex items-center gap-2 mt-4">
              <button onClick={handleSave} disabled={busy}
                className="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold px-3 py-2.5 rounded-xl bg-brand-500 text-white disabled:opacity-60">
                <Save size={14} /> {current ? 'Save changes' : 'Save label'}
              </button>
              <button onClick={handleExport} disabled={busy} title="Download a PNG"
                className="flex items-center gap-1.5 text-xs font-semibold px-3 py-2.5 rounded-xl border border-gray-200">
                <Download size={14} /> PNG
              </button>
            </div>
            <button onClick={handleSaveStyle} disabled={busy}
              className="w-full mt-2 flex items-center justify-center gap-1.5 text-xs font-medium px-3 py-2 rounded-xl border border-dashed border-gray-300 text-gray-500 hover:border-brand-300 hover:text-brand-600">
              <Bookmark size={13} /> Save this look as a style
            </button>
          </div>

          {/* ── Right: editing ── */}
          <div className="min-w-0 space-y-5">

            {/* Selected piece — the most important panel, so it's first */}
            <div className="bg-white rounded-xl border border-gray-200 p-3.5">
              {selectedEl ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-bold text-gray-700 capitalize">
                      {selectedEl.kind === 'art'
                        ? (options.art.find((a) => a.key === selectedEl.art)?.label ?? 'Art')
                        : `${selectedEl.kind} selected`}
                    </p>
                    <div className="flex items-center gap-0.5">
                      <button onClick={() => reorderEl('up')} title="Bring forward" className="p-1.5 text-gray-400 hover:text-gray-800"><ArrowUp size={14} /></button>
                      <button onClick={() => reorderEl('down')} title="Send back" className="p-1.5 text-gray-400 hover:text-gray-800"><ArrowDown size={14} /></button>
                      <button onClick={() => duplicateEl()} title="Duplicate" className="p-1.5 text-gray-400 hover:text-gray-800"><Copy size={14} /></button>
                      <button onClick={() => deleteEl()} title="Delete"
                        className="flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-lg text-red-600 hover:bg-red-50">
                        <Trash2 size={13} /> Delete
                      </button>
                    </div>
                  </div>

                  {selectedEl.kind !== 'art' && selectedEl.kind !== 'line' && (
                    <div>
                      <label className={lbl}>Text</label>
                      <input value={selectedEl.text} autoFocus
                        onChange={(e) => patchEl(selectedEl.id, { text: e.target.value })}
                        placeholder="Type here…" className={`${field} font-semibold`} />
                    </div>
                  )}

                  {selectedEl.kind === 'art' && (
                    <div>
                      <label className={lbl}>Art</label>
                      <select value={selectedEl.art} className={field}
                        onChange={(e) => patchEl(selectedEl.id, { art: e.target.value }, true)}>
                        {options.art.map((a) => <option key={a.key} value={a.key}>{a.label}</option>)}
                      </select>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {[['Size', 'size', 0.01, 0.45, 0.005],
                      ['Width', 'w', 0.05, 1.0, 0.01],
                      ['Rotate', 'rotation', -180, 180, 1]].map(([label, key, min, max, step]) => (
                      <label key={key} className="text-[11px] text-gray-500">
                        <span className="block mb-1">{label}
                          <span className="float-right tabular-nums text-gray-400">
                            {key === 'rotation' ? `${Math.round(selectedEl[key])}°` : (selectedEl[key] ?? 0).toFixed(2)}
                          </span>
                        </span>
                        <input type="range" min={min} max={max} step={step} className="w-full"
                          value={selectedEl[key] ?? 0}
                          onChange={(e) => patchEl(selectedEl.id, { [key]: Number(e.target.value) })}
                          onMouseUp={pushHistory} />
                      </label>
                    ))}
                  </div>

                  <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] text-gray-600">
                    <label className="flex items-center gap-1.5">Colour
                      <select value={selectedEl.color} className="border border-gray-200 rounded px-1.5 py-1"
                        onChange={(e) => patchEl(selectedEl.id, { color: e.target.value }, true)}>
                        {options.colors.map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                    </label>
                    {selectedEl.kind !== 'art' && selectedEl.kind !== 'line' && (
                      <>
                        <label className="flex items-center gap-1.5">Align
                          <select value={selectedEl.align} className="border border-gray-200 rounded px-1.5 py-1"
                            onChange={(e) => patchEl(selectedEl.id, { align: e.target.value }, true)}>
                            <option value="left">Left</option><option value="center">Center</option><option value="right">Right</option>
                          </select>
                        </label>
                        <label className="flex items-center gap-1.5">
                          <input type="checkbox" checked={selectedEl.bold}
                            onChange={(e) => patchEl(selectedEl.id, { bold: e.target.checked }, true)} /> Bold
                        </label>
                        <label className="flex items-center gap-1.5">Lines
                          <input type="number" min={1} max={4} value={selectedEl.lines}
                            className="w-12 border border-gray-200 rounded px-1.5 py-1"
                            onChange={(e) => patchEl(selectedEl.id, { lines: Number(e.target.value) }, true)} />
                        </label>
                      </>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-gray-400 py-1">
                  Click any piece on the label to edit or delete it. Nothing is locked.
                </p>
              )}
            </div>

            {/* Add */}
            <div>
              <p className={lbl}>Add to the label</p>
              <div className="flex flex-wrap gap-1.5 mb-2">
                <button className={chip} onClick={() => addElement({ kind: 'text', text: 'New text', x: 0.1, y: 0.45, w: 0.5, size: 0.08 })}>
                  <Type size={12} /> Text
                </button>
                <button className={chip} onClick={() => addElement({ kind: 'price', text: '$0.00', x: 0.1, y: 0.45, w: 0.6, size: 0.2 })}>
                  <span className="font-bold">$</span> Price
                </button>
                <button className={chip} onClick={() => addElement({ kind: 'starburst', text: 'Sale', x: 0.1, y: 0.4, w: 0.2, size: 0.055, color: 'paper', align: 'center' })}>
                  <Star size={12} /> Starburst
                </button>
                <button className={chip} onClick={() => addElement({ kind: 'line', text: '', x: 0.1, y: 0.5, w: 0.8, size: 0.008 })}>
                  <Minus size={12} /> Line
                </button>
              </div>
              <p className="text-[11px] text-gray-400 mb-1.5">Art — add as many as you like</p>
              <div className="flex flex-wrap gap-1.5">
                {options.art.map((a) => (
                  <button key={a.key} className={chip}
                    onClick={() => addElement({ kind: 'art', art: a.key, x: 0.42, y: 0.55, w: 0.14 })}>
                    <ImageIcon size={11} /> {a.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Layers */}
            {elements.length > 0 && (
              <div>
                <p className={lbl}>Layers <span className="font-normal text-gray-300">(bottom = front)</span></p>
                <div className="space-y-1 max-h-44 overflow-y-auto pr-1">
                  {elements.map((el) => (
                    <div key={el.id}
                      className={`group flex items-center gap-2 px-2 py-1.5 rounded-lg text-[11px] border ${
                        el.id === selectedId ? 'border-brand-400 bg-brand-50' : 'border-gray-100 hover:bg-gray-50'}`}>
                      <button onClick={() => setSelectedId(el.id)} className="flex items-center gap-2 flex-1 min-w-0 text-left">
                        <span className="uppercase text-[9px] tracking-wide text-gray-400 w-12 shrink-0">{el.kind}</span>
                        <span className="truncate text-gray-700">
                          {el.kind === 'art'
                            ? (options.art.find((a) => a.key === el.art)?.label ?? el.art)
                            : (el.text || '—')}
                        </span>
                      </button>
                      <button onClick={() => deleteEl(el.id)} title="Delete"
                        className="p-1 text-gray-300 hover:text-red-500 shrink-0">
                        <Trash2 size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Whole-label look */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <label className={lbl}>Print size</label>
                <select value={spec.size} className={field}
                  onChange={(e) => setSpecTracked({ ...spec, size: e.target.value })}>
                  {options.sizes.map((s) => (
                    <option key={s.key} value={s.key}>{s.label} · {s.inches[0]}×{s.inches[1]}″</option>
                  ))}
                </select>
              </div>
              <div>
                <label className={lbl}>Font</label>
                <select value={spec.font} className={field}
                  onChange={(e) => setSpecTracked({ ...spec, font: e.target.value })}>
                  {options.fonts.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
                </select>
              </div>
              <div>
                <label className={lbl}>Accent</label>
                <select value={spec.accent} className={field}
                  onChange={(e) => setSpecTracked({ ...spec, accent: e.target.value })}>
                  {options.accents.map((a) => <option key={a.key} value={a.key}>{a.label}</option>)}
                </select>
              </div>
              <label className="flex items-end gap-1.5 text-xs text-gray-600 pb-2">
                <input type="checkbox" checked={spec.show_border}
                  onChange={(e) => setSpecTracked({ ...spec, show_border: e.target.checked })} />
                Border
              </label>
            </div>

            {/* Saved styles */}
            {templates.length > 0 && (
              <div>
                <p className={lbl}>Your saved styles</p>
                <div className="flex flex-wrap gap-1.5">
                  {templates.map((t) => (
                    <span key={t.id} className="group inline-flex items-center gap-1 text-[11px] font-medium pl-3 pr-1.5 py-1.5 rounded-lg border border-gray-200 hover:border-brand-400">
                      <button onClick={() => handleUseStyle(t)} className="hover:text-brand-600">{t.name}</button>
                      <button onClick={() => handleDeleteStyle(t)}
                        className="text-gray-300 hover:text-red-500"><Trash2 size={11} /></button>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Start over from a layout — collapsed, since it wipes the label */}
            <div className="border-t border-gray-100 pt-4">
              <button onClick={() => setShowStart(!showStart)}
                className="text-xs font-medium text-gray-400 hover:text-gray-600 flex items-center gap-1">
                <Plus size={13} /> Start from a ready-made layout
              </button>
              {showStart && (
                <div className="mt-3 space-y-2">
                  {products.length > 0 && (
                    <div className="relative">
                      <Search size={14} className="absolute left-3 top-2.5 text-gray-300" />
                      <input value={productQuery} onChange={(e) => setProductQuery(e.target.value)}
                        placeholder="Search your products…" className={`${field} pl-9`} />
                      {filteredProducts.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {filteredProducts.map((p) => (
                            <button key={p.product_name}
                              onClick={() => { setStarter((s) => ({ ...s, product_name: p.product_name, price: p.price || s.price })); setProductQuery('') }}
                              className="text-[11px] px-2.5 py-1 rounded-full border border-gray-200 hover:border-brand-400 truncate max-w-[240px]">
                              {p.product_name}{p.price ? ` · ${p.price}` : ''}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <input value={starter.product_name} placeholder="Bottle name" className={field}
                      onChange={(e) => setStarter((s) => ({ ...s, product_name: e.target.value }))} />
                    <input value={starter.price} placeholder="$32.99" className={field}
                      onChange={(e) => setStarter((s) => ({ ...s, price: e.target.value }))} />
                    <input value={starter.regular_price} placeholder="Regular $36.99" className={field}
                      onChange={(e) => setStarter((s) => ({ ...s, regular_price: e.target.value }))} />
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {options.styles.map((s) => (
                      <button key={s.key} onClick={() => applyStyle(s.key)} disabled={busy}
                        className="text-left px-3 py-2 rounded-xl border border-gray-200 hover:border-brand-400 disabled:opacity-50">
                        <p className="text-xs font-semibold text-gray-700 flex items-center gap-1">
                          <Wand2 size={11} className="text-brand-400" />{s.label}
                        </p>
                        <p className="text-[10px] text-gray-400 leading-snug mt-0.5">{s.note}</p>
                      </button>
                    ))}
                  </div>
                  <p className="text-[10px] text-gray-400">
                    This replaces what&rsquo;s on the label — undo is one click away.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Saved labels ── */}
        <div className="mt-10">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
              Saved labels {labels.length > 0 && `(${labels.length})`}
            </p>
            <button onClick={handlePrint} disabled={busy || selected.length === 0}
              className="flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-xl bg-gray-900 text-white disabled:opacity-40">
              <Printer size={14} />
              {selected.length ? `Print ${selected.length}` : 'Tick labels to print'}
            </button>
          </div>

          {labels.length === 0 ? (
            <p className="text-sm text-gray-500">None yet — design one above and hit Save.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {labels.map((row) => {
                const isSel = selected.includes(row.id)
                return (
                  <div key={row.id}
                    className={`group relative bg-white rounded-xl border p-3 ${
                      current?.id === row.id ? 'border-brand-400' : 'border-gray-100'}`}>
                    <button title="Include in print sheet"
                      onClick={() => setSelected((s) => (isSel ? s.filter((x) => x !== row.id) : [...s, row.id]))}
                      className={`absolute top-2 right-2 w-5 h-5 rounded-md border flex items-center justify-center ${
                        isSel ? 'bg-brand-500 border-brand-500 text-white' : 'border-gray-300 bg-white'}`}>
                      {isSel && <Check size={12} />}
                    </button>
                    <button onClick={() => { setCurrent(row); setSpec(row.design_json); setSelectedId(null) }}
                      className="text-left w-full pr-6">
                      <p className="text-xs font-semibold text-gray-800 truncate">{row.name}</p>
                      <p className="text-[10px] text-gray-400 mt-1">
                        {(row.design_json?.elements?.length ?? 0)} pieces
                      </p>
                    </button>
                    <button onClick={() => handleDelete(row)}
                      className="absolute bottom-2 right-2 p-1 text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100">
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
