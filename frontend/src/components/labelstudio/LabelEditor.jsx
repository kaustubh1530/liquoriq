/**
 * components/labelstudio/LabelEditor.jsx — PHASE 23.8
 *
 * The canvas and its editing panels, rendered from a `useLabelStudio` hook the
 * caller owns. One editor: the standalone page and the campaign section pass
 * the same object and differ only in `compact`, which stacks the two columns
 * instead of placing them side by side.
 *
 * LAYOUT NOTE (kept from the page): the full rendering is a two-column CSS GRID
 * with an explicit left width and minmax(0,1fr) on the right. An earlier flex
 * version let a wide row of art chips blow the left column out, which squeezed
 * the editing panel down to one word per line and made delete/edit unreachable.
 * The grid can't do that.
 */

import { useState } from 'react'
import {
  ArrowDown, ArrowUp, Bookmark, Copy, Download, Grid3x3, Image as ImageIcon,
  Loader2, Magnet, Minus, Plus, Save, Search, Star, Trash2, Type, Undo2, Wand2,
} from 'lucide-react'
import LabelCanvas from '../../pages/labelstudio/LabelCanvas'

const CANVAS_W = 420
const FIELD = 'w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500'
const LBL = 'block text-[11px] font-semibold text-gray-500 mb-1.5'
const CHIP = 'flex items-center gap-1 text-[11px] font-medium px-2.5 py-1.5 rounded-lg border border-gray-200 hover:border-brand-400 hover:text-brand-600 whitespace-nowrap'

export function EditorTools({ studio }) {
  const { undo, history, showGrid, setShowGrid, snapEnabled, setSnapEnabled } = studio
  return (
    <div className="flex items-center gap-2">
      <button onClick={undo} disabled={!history.length} title="Undo (⌘Z)"
        className="p-2 rounded-lg border border-gray-200 disabled:opacity-40"><Undo2 size={15} /></button>
      <button onClick={() => setShowGrid(!showGrid)} title="Grid"
        className={`p-2 rounded-lg border ${showGrid ? 'bg-brand-50 border-brand-300 text-brand-600' : 'border-gray-200 text-gray-500'}`}><Grid3x3 size={15} /></button>
      <button onClick={() => setSnapEnabled(!snapEnabled)} title="Snap to guides"
        className={`p-2 rounded-lg border ${snapEnabled ? 'bg-brand-50 border-brand-300 text-brand-600' : 'border-gray-200 text-gray-500'}`}><Magnet size={15} /></button>
    </div>
  )
}

export default function LabelEditor({ studio, compact = false }) {
  const {
    options, spec, preview, elements, selectedEl, selectedId, setSelectedId,
    current, rendering, busy, sizeInfo, aspect, snapEnabled, showGrid,
    handleMove, deleteEl, duplicateEl, reorderEl, patchEl, pushHistory,
    addElement, setSpecTracked, templates, applySavedStyle, deleteStyle, applyStyle,
    starter, setStarter, productQuery, setProductQuery, filteredProducts,
    products, save, exportPng, saveStyle,
  } = studio

  const [showStart, setShowStart] = useState(false)
  if (!options || !spec) return null

  return (
    <div className={compact
      ? 'space-y-6'
      : 'grid grid-cols-1 lg:grid-cols-[420px_minmax(0,1fr)] gap-6 items-start'}>

      {/* ── The label ── */}
      <div className={compact ? 'max-w-[420px]' : ''}>
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
          <button onClick={save} disabled={busy}
            className="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold px-3 py-2.5 rounded-xl bg-brand-500 text-white disabled:opacity-60">
            <Save size={14} /> {current ? 'Save changes' : 'Save label'}
          </button>
          <button onClick={exportPng} disabled={busy} title="Download a PNG"
            className="flex items-center gap-1.5 text-xs font-semibold px-3 py-2.5 rounded-xl border border-gray-200">
            <Download size={14} /> PNG
          </button>
        </div>
        <button onClick={saveStyle} disabled={busy}
          className="w-full mt-2 flex items-center justify-center gap-1.5 text-xs font-medium px-3 py-2 rounded-xl border border-dashed border-gray-300 text-gray-500 hover:border-brand-300 hover:text-brand-600">
          <Bookmark size={13} /> Save this look as a style
        </button>
      </div>

      {/* ── Editing ── */}
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
                  <label className={LBL}>Text</label>
                  <input value={selectedEl.text} autoFocus
                    onChange={(e) => patchEl(selectedEl.id, { text: e.target.value })}
                    placeholder="Type here…" className={`${FIELD} font-semibold`} />
                </div>
              )}

              {selectedEl.kind === 'art' && (
                <div>
                  <label className={LBL}>Art</label>
                  <select value={selectedEl.art} className={FIELD}
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
          <p className={LBL}>Add to the label</p>
          <div className="flex flex-wrap gap-1.5 mb-2">
            <button className={CHIP} onClick={() => addElement({ kind: 'text', text: 'New text', x: 0.1, y: 0.45, w: 0.5, size: 0.08 })}>
              <Type size={12} /> Text
            </button>
            <button className={CHIP} onClick={() => addElement({ kind: 'price', text: '$0.00', x: 0.1, y: 0.45, w: 0.6, size: 0.2 })}>
              <span className="font-bold">$</span> Price
            </button>
            <button className={CHIP} onClick={() => addElement({ kind: 'starburst', text: 'Sale', x: 0.1, y: 0.4, w: 0.2, size: 0.055, color: 'paper', align: 'center' })}>
              <Star size={12} /> Starburst
            </button>
            <button className={CHIP} onClick={() => addElement({ kind: 'line', text: '', x: 0.1, y: 0.5, w: 0.8, size: 0.008 })}>
              <Minus size={12} /> Line
            </button>
          </div>
          <p className="text-[11px] text-gray-400 mb-1.5">Art — add as many as you like</p>
          <div className="flex flex-wrap gap-1.5">
            {options.art.map((a) => (
              <button key={a.key} className={CHIP}
                onClick={() => addElement({ kind: 'art', art: a.key, x: 0.42, y: 0.55, w: 0.14 })}>
                <ImageIcon size={11} /> {a.label}
              </button>
            ))}
          </div>
        </div>

        {/* Layers */}
        {elements.length > 0 && (
          <div>
            <p className={LBL}>Layers <span className="font-normal text-gray-300">(bottom = front)</span></p>
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
            <label className={LBL}>Print size</label>
            <select value={spec.size} className={FIELD}
              onChange={(e) => setSpecTracked({ ...spec, size: e.target.value })}>
              {options.sizes.map((s) => (
                <option key={s.key} value={s.key}>{s.label} · {s.inches[0]}×{s.inches[1]}″</option>
              ))}
            </select>
          </div>
          <div>
            <label className={LBL}>Font</label>
            <select value={spec.font} className={FIELD}
              onChange={(e) => setSpecTracked({ ...spec, font: e.target.value })}>
              {options.fonts.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
            </select>
          </div>
          <div>
            <label className={LBL}>Accent</label>
            <select value={spec.accent} className={FIELD}
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
            <p className={LBL}>Your saved styles</p>
            <div className="flex flex-wrap gap-1.5">
              {templates.map((t) => (
                <span key={t.id} className="group inline-flex items-center gap-1 text-[11px] font-medium pl-3 pr-1.5 py-1.5 rounded-lg border border-gray-200 hover:border-brand-400">
                  <button onClick={() => applySavedStyle(t)} className="hover:text-brand-600">{t.name}</button>
                  <button onClick={() => deleteStyle(t)}
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
                    placeholder="Search your products…" className={`${FIELD} pl-9`} />
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
                <input value={starter.product_name} placeholder="Bottle name" className={FIELD}
                  onChange={(e) => setStarter((s) => ({ ...s, product_name: e.target.value }))} />
                <input value={starter.price} placeholder="$32.99" className={FIELD}
                  onChange={(e) => setStarter((s) => ({ ...s, price: e.target.value }))} />
                <input value={starter.regular_price} placeholder="Regular $36.99" className={FIELD}
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
  )
}
