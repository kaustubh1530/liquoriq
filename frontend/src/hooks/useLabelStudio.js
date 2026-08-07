/**
 * hooks/useLabelStudio.js — PHASE 23.8: the label editor's state, owned once.
 *
 * Same discipline as useAdCreator, and for a stronger reason. Label Studio is a
 * canvas editor with a real state machine — a spec, a selection, an undo stack,
 * a debounced server render, a print sheet — and the server draws the preview
 * AND reports the box it drew each element into, which is what keeps the drag
 * handles aligned with the print. A second, "simpler" editor embedded in the
 * workspace would be a second layout engine in all but name, and it would drift
 * from the renderer the first time either side changed.
 *
 * So there is one editor. The page and the campaign section differ in two
 * things and nothing else:
 *
 *   strategyId       — stamped on labels created here (Phase 23.8's migration).
 *   scopeToStrategy  — whether the library lists only that campaign's labels.
 *                      The two are separate on purpose: arriving at the page
 *                      from a campaign should stamp new labels with it while
 *                      still showing the whole drawer, because that page IS the
 *                      store's label drawer. The workspace section is the place
 *                      that shows one campaign's.
 *   onSaved          — called after a label is saved, exported or deleted, so
 *                      the workspace can re-read GET /workspace/{id}. It says
 *                      THAT the labels changed, never that the step is done:
 *                      progress is computed server-side from the real rows.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { labelStudioApi, assetUrl } from '../api/client'

const DEBOUNCE_MS = 260
const HISTORY_MAX = 30

export default function useLabelStudio({ strategyId = null, scopeToStrategy = false,
                                        onSaved } = {}) {
  const listFor = scopeToStrategy ? strategyId : null
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
  const [starter, setStarter] = useState({ product_name: '', price: '', regular_price: '' })
  const [perPage, setPerPage] = useState(4)
  const [page, setPage] = useState('a4')
  const [orientation, setOrientation] = useState('landscape')
  const [repeat, setRepeat] = useState(false)
  const [cutMarks, setCutMarks] = useState(true)
  const [sheetImg, setSheetImg] = useState('')
  const [sheetBusy, setSheetBusy] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const specRef = useRef(null)
  specRef.current = spec

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [o, p, l, t] = await Promise.all([
          labelStudioApi.options(),
          labelStudioApi.products().catch(() => ({ data: [] })),
          labelStudioApi.list(listFor),
          labelStudioApi.templates().catch(() => ({ data: [] })),
        ])
        if (cancelled) return
        const arr = (v) => (Array.isArray(v) ? v : [])
        setOptions(o.data)
        setProducts(arr(p.data))
        setLabels(arr(l.data))
        setTemplates(arr(t.data))
        setSpec(o.data.blank)
      } catch (e) {
        if (!cancelled) {
          setError(e.response?.data?.detail ?? e.message ?? 'Could not load Label Studio.')
        }
      } finally { if (!cancelled) setLoading(false) }
    })()
    return () => { cancelled = true }
  }, [listFor])

  // The SERVER draws the preview and reports where it put each element, so the
  // drag handles line up exactly with what prints. Debounced, because it is a
  // real render on every keystroke otherwise.
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

  const pushHistory = useCallback(
    () => setHistory((h) => [...h.slice(-HISTORY_MAX), specRef.current]), [])

  const setSpecTracked = useCallback((next) => { pushHistory(); setSpec(next) }, [pushHistory])

  const patchEl = useCallback((id, patch, track = false) => {
    if (track) pushHistory()
    setSpec((s) => ({
      ...s, elements: s.elements.map((e) => (e.id === id ? { ...e, ...patch } : e)),
    }))
  }, [pushHistory])

  const handleMove = useCallback((id, x, y) => patchEl(id, { x, y }, true), [patchEl])

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

  const undo = useCallback(() => setHistory((h) => {
    if (!h.length) return h
    setSpec(h[h.length - 1])
    setSelectedId(null)
    return h.slice(0, -1)
  }), [])

  // Delete removes the selected piece — but never while typing in a field.
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

  const save = async () => {
    setBusy(true); setError('')
    try {
      // The campaign is stamped on CREATION only — see the migration note. A
      // label saved from inside a campaign belongs to it; one opened from the
      // library and edited keeps whatever it already had.
      const { data } = current
        ? await labelStudioApi.save(current.id, spec)
        : await labelStudioApi.create(spec, strategyId)
      setCurrent(data); setSpec(data.design_json)
      setLabels((ls) => [data, ...ls.filter((l) => l.id !== data.id)])
      onSaved?.()
      return data
    } catch (e) {
      setError(e.response?.data?.detail ?? 'Could not save.')
      return null
    } finally { setBusy(false) }
  }

  const exportPng = async () => {
    if (!current) { await save(); return }
    setBusy(true)
    try {
      const { data } = await labelStudioApi.exportPng(current.id)
      setCurrent(data)
      setLabels((ls) => ls.map((l) => (l.id === data.id ? data : l)))
      window.open(assetUrl(data.final_image_url), '_blank', 'noopener')
    } catch (e) { setError(e.response?.data?.detail ?? 'Could not export.') }
    finally { setBusy(false) }
  }

  const saveStyle = async () => {
    const name = window.prompt('Name this style (e.g. "Staff pick")')
    if (!name) return
    setBusy(true)
    try {
      const { data } = await labelStudioApi.saveTemplate(spec, name)
      setTemplates((t) => [data, ...t])
    } catch (e) { setError(e.response?.data?.detail ?? 'Could not save the style.') }
    finally { setBusy(false) }
  }

  const applySavedStyle = async (tpl) => {
    setBusy(true)
    try {
      const { data } = await labelStudioApi.applyTemplate(tpl.id, spec)
      setSpecTracked(data.spec); setSelectedId(null)
    } catch (e) { setError(e.response?.data?.detail ?? 'Could not apply.') }
    finally { setBusy(false) }
  }

  const deleteStyle = async (tpl) => {
    if (!window.confirm(`Delete the style "${tpl.name}"?`)) return
    try {
      await labelStudioApi.deleteTemplate(tpl.id)
      setTemplates((t) => t.filter((x) => x.id !== tpl.id))
    } catch (e) { setError(e.response?.data?.detail ?? 'Could not delete.') }
  }

  const openLabel = (row) => {
    setCurrent(row); setSpec(row.design_json); setSelectedId(null)
  }

  const removeLabel = async (row) => {
    if (!window.confirm(`Delete "${row.name}"?`)) return
    try {
      await labelStudioApi.remove(row.id)
      setLabels((ls) => ls.filter((l) => l.id !== row.id))
      setSelected((s) => s.filter((id) => id !== row.id))
      if (current?.id === row.id) setCurrent(null)
      onSaved?.()
    } catch (e) { setError(e.response?.data?.detail ?? 'Could not delete.') }
  }

  const toggleSelected = (id) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  const sheetOpts = useMemo(
    () => ({ perPage, page, repeat, cutMarks, orientation }),
    [perPage, page, repeat, cutMarks, orientation])

  const printSheet = async () => {
    setBusy(true)
    try { await labelStudioApi.printSheet(selected, sheetOpts) }
    catch (e) { setError(e.response?.data?.detail ?? 'Could not build the sheet.') }
    finally { setBusy(false) }
  }

  // Page 1 preview whenever the selection or the sheet settings change, so the
  // arrangement is checked before paper is spent.
  useEffect(() => {
    if (!selected.length) { setSheetImg(''); return }
    const t = setTimeout(async () => {
      setSheetBusy(true)
      try {
        const { data } = await labelStudioApi.sheetPreview(selected, sheetOpts)
        setSheetImg(data.image)
      } catch { setSheetImg('') }
      finally { setSheetBusy(false) }
    }, 300)
    return () => clearTimeout(t)
  }, [selected, sheetOpts])

  const filteredProducts = useMemo(() => {
    const q = productQuery.trim().toLowerCase()
    if (!q) return []
    return products.filter((p) => p.product_name.toLowerCase().includes(q)).slice(0, 5)
  }, [products, productQuery])

  const sizeInfo = options?.sizes?.find((s) => s.key === spec?.size)
  const aspect = sizeInfo ? sizeInfo.inches[0] / sizeInfo.inches[1] : 4 / 3
  // The finished cut size for the current sheet settings
  const cellFor = (n) => options?.sheet_layouts?.find((l) => l.per_page === n)
    ?.cells?.[`${page}_${orientation}`]

  return {
    // data
    options, products, labels, templates, current, spec, preview, elements,
    selectedEl, selectedId, history, selected, filteredProducts, sizeInfo,
    aspect, cellFor, sheetImg,
    // flags
    loading, busy, rendering, sheetBusy, error, setError,
    // editor controls
    setSelectedId, setSpec, setSpecTracked, patchEl, pushHistory, handleMove,
    addElement, duplicateEl, deleteEl, reorderEl, undo,
    snapEnabled, setSnapEnabled, showGrid, setShowGrid,
    // library + styles
    openLabel, removeLabel, toggleSelected, save, exportPng,
    saveStyle, applySavedStyle, deleteStyle, applyStyle,
    starter, setStarter, productQuery, setProductQuery,
    // print sheet
    perPage, setPerPage, page, setPage, orientation, setOrientation,
    repeat, setRepeat, cutMarks, setCutMarks, printSheet,
  }
}
