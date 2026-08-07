/**
 * components/labelstudio/LabelLibrary.jsx — PHASE 23.8
 *
 * The saved labels and the print sheet. Shared by the Label Studio page and the
 * campaign section; what differs is only which labels the hook was asked for —
 * everything, or this campaign's.
 *
 * The sheet preview is a real server render of page 1: the arrangement is
 * checked before paper is spent, and the preview and the print come out of the
 * same renderer, so they cannot disagree.
 */

import { Check, Loader2, Printer, Trash2 } from 'lucide-react'

const LBL = 'block text-[11px] font-semibold text-gray-500 mb-1.5'

export default function LabelLibrary({ studio, title = 'Saved labels', emptyHint }) {
  const {
    options, labels, current, selected, toggleSelected, openLabel, removeLabel,
    perPage, setPerPage, page, setPage, orientation, setOrientation,
    repeat, setRepeat, cutMarks, setCutMarks, printSheet, cellFor,
    sheetImg, sheetBusy, busy,
  } = studio

  return (
    <div>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
          {title} {labels.length > 0 && `(${labels.length})`}
        </p>
        <p className="text-[11px] text-gray-400">Tick the ones you want on the sheet</p>
      </div>

      {labels.length === 0 ? (
        <p className="text-sm text-gray-500">
          {emptyHint ?? 'None yet — design one above and hit Save.'}
        </p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {labels.map((row) => {
            const isSel = selected.includes(row.id)
            return (
              <div key={row.id}
                className={`group relative bg-white rounded-xl border p-3 ${
                  current?.id === row.id ? 'border-brand-400' : 'border-gray-100'}`}>
                <button title="Include in print sheet" onClick={() => toggleSelected(row.id)}
                  className={`absolute top-2 right-2 w-5 h-5 rounded-md border flex items-center justify-center ${
                    isSel ? 'bg-brand-500 border-brand-500 text-white' : 'border-gray-300 bg-white'}`}>
                  {isSel && <Check size={12} />}
                </button>
                <button onClick={() => openLabel(row)} className="text-left w-full pr-6">
                  <p className="text-xs font-semibold text-gray-800 truncate">{row.name}</p>
                  <p className="text-[10px] text-gray-400 mt-1">
                    {(row.design_json?.elements?.length ?? 0)} pieces
                  </p>
                </button>
                <button onClick={() => removeLabel(row)}
                  className="absolute bottom-2 right-2 p-1 text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100">
                  <Trash2 size={13} />
                </button>
              </div>
            )
          })}
        </div>
      )}

      {selected.length > 0 && (
        <div className="mt-6 bg-white rounded-2xl border border-gray-200 p-4">
          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_300px] gap-6 items-start">
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <Printer size={16} className="text-brand-500" />
                <h2 className="text-sm font-bold text-gray-800">
                  Print sheet — {selected.length} label{selected.length === 1 ? '' : 's'} selected
                </h2>
              </div>

              <div>
                <p className={LBL}>How many per page</p>
                <div className="flex flex-wrap gap-2">
                  {(options?.sheet_layouts ?? []).map((l) => {
                    const cell = l.cells?.[`${page}_${orientation}`] ?? []
                    const grid = l.grids?.[orientation] ?? []
                    const on = perPage === l.per_page
                    return (
                      <button key={l.per_page} onClick={() => setPerPage(l.per_page)}
                        className={`px-3 py-2 rounded-xl border text-left transition-colors ${
                          on ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-gray-300'}`}>
                        <p className={`text-sm font-bold ${on ? 'text-brand-700' : 'text-gray-700'}`}>
                          {l.per_page}
                        </p>
                        <p className="text-[10px] text-gray-400 whitespace-nowrap">
                          {grid[0]}×{grid[1]} · {cell[0]}×{cell[1]}″
                        </p>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-gray-600">
                <label className="flex items-center gap-1.5">Paper
                  <select value={page} onChange={(e) => setPage(e.target.value)}
                    className="border border-gray-200 rounded-lg px-2 py-1">
                    {(options?.pages ?? []).map((p) => (
                      <option key={p.key} value={p.key}>{p.label}</option>
                    ))}
                  </select>
                </label>
                <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden text-[11px] font-semibold">
                  {[['landscape', 'Landscape'], ['portrait', 'Portrait']].map(([v, t]) => (
                    <button key={v} onClick={() => setOrientation(v)}
                      className={`px-2.5 py-1 transition-colors ${
                        orientation === v ? 'bg-brand-500 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'}`}>
                      {t}
                    </button>
                  ))}
                </div>
                <label className="flex items-center gap-1.5">
                  <input type="checkbox" checked={repeat}
                    onChange={(e) => setRepeat(e.target.checked)} />
                  Fill the page by repeating
                </label>
                <label className="flex items-center gap-1.5">
                  <input type="checkbox" checked={cutMarks}
                    onChange={(e) => setCutMarks(e.target.checked)} />
                  Cut guides
                </label>
              </div>

              <p className="text-[11px] text-gray-400">
                {repeat
                  ? `Repeats your ${selected.length} selected label${selected.length === 1 ? '' : 's'} to fill one page — good for printing many of the same tag.`
                  : `${Math.ceil(selected.length / perPage)} page${Math.ceil(selected.length / perPage) === 1 ? '' : 's'}. Each label prints at ${cellFor(perPage)?.join('″ × ')}″ — cut along the guides.`}
              </p>

              <button onClick={printSheet} disabled={busy}
                className="flex items-center gap-1.5 text-xs font-semibold px-4 py-2.5 rounded-xl bg-gray-900 text-white disabled:opacity-40">
                <Printer size={14} /> Download printable PDF
              </button>
            </div>

            <div className="relative">
              <p className={LBL}>Page 1 preview</p>
              {sheetImg ? (
                <img src={sheetImg} alt="Sheet preview"
                  className="w-full rounded-lg border border-gray-200 bg-white" />
              ) : (
                <div className="w-full aspect-[1/1.414] rounded-lg border border-dashed border-gray-200 flex items-center justify-center text-xs text-gray-400">
                  {sheetBusy ? 'Building…' : 'Select labels to preview'}
                </div>
              )}
              {sheetBusy && sheetImg && (
                <span className="absolute top-7 right-2 text-gray-400">
                  <Loader2 size={14} className="animate-spin" />
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
