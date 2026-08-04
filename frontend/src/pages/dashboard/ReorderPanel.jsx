/**
 * ReorderPanel.jsx — PHASE 22: the reorder list, as something you can hand over.
 *
 * "1,128 products need reordering" is a finding. This is the action: what to
 * buy, how many, and what it's worth — with a CSV the owner can email to his
 * distributor rep.
 *
 * WHY THE CSV IS BUILT IN THE BROWSER: the API is authenticated with a bearer
 * token held in JS. A plain <a download> hits the endpoint without that header
 * and gets a 401, so the file has to come from data we already fetched. It
 * also means the download matches exactly what's on screen, including the
 * horizon the owner picked.
 *
 * The money column says RETAIL throughout. The POS export has no cost price,
 * and letting a shop owner read a retail total as his order cost would
 * overstate the bill by his entire margin.
 */

import { useEffect, useState } from 'react'
import { intelligenceApi } from '../../api/client'
import { X, Download, Loader2, AlertCircle } from 'lucide-react'

const money = (n) => `$${(Number(n) || 0).toLocaleString(undefined, {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
})}`

const HORIZONS = [2, 4, 6, 8]

const URGENCY_STYLE = {
  'Out of stock': 'bg-red-100 text-red-700',
  'Under 1 week': 'bg-orange-100 text-orange-700',
  'Under 3 weeks': 'bg-amber-100 text-amber-700',
}

/** RFC-4180 escaping: product names contain commas and the odd quote. */
function toCsv(columns, rows) {
  const cell = (v) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return [
    columns.map((c) => cell(c.label)).join(','),
    ...rows.map((r) => columns.map((c) => cell(r[c.key])).join(',')),
  ].join('\n')
}

function download(filename, text) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8;' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export default function ReorderPanel({ onClose }) {
  const [data, setData] = useState(null)
  const [horizon, setHorizon] = useState(4)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    intelligenceApi.reorderList(horizon)
      .then(({ data: d }) => { if (!cancelled) { setData(d); setError('') } })
      .catch(() => { if (!cancelled) setError('Could not build the reorder list.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [horizon])

  // Escape closes — a full-screen panel with no keyboard exit is a trap.
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const items = data?.items ?? []
  const totals = data?.totals ?? {}
  const period = data?.period ?? {}

  const handleDownload = () => {
    const stamp = period.end || new Date().toISOString().slice(0, 10)
    download(`reorder-list-${stamp}-${horizon}wk.csv`, toCsv(data.columns, items))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
         onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-5xl max-h-[88vh] flex flex-col overflow-hidden"
           onClick={(e) => e.stopPropagation()}>

        <header className="flex items-start justify-between gap-4 p-5 border-b border-gray-100">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-gray-900">Reorder list</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              {period.start && period.end
                ? `Based on your report for ${period.start} to ${period.end}`
                : 'Based on your most recent report'}
            </p>
          </div>
          <button onClick={onClose} aria-label="Close"
                  className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 shrink-0">
            <X size={18} />
          </button>
        </header>

        <div className="flex items-center gap-4 px-5 py-3 border-b border-gray-100 flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-500">Cover</span>
            {HORIZONS.map((w) => (
              <button
                key={w}
                onClick={() => setHorizon(w)}
                className={`text-xs font-semibold px-2.5 py-1 rounded-lg border transition-colors ${
                  horizon === w
                    ? 'bg-brand-500 text-white border-brand-500'
                    : 'bg-white text-gray-600 border-gray-200 hover:border-brand-300'
                }`}
              >
                {w} wk
              </button>
            ))}
          </div>

          <div className="flex items-center gap-5 text-xs ml-auto flex-wrap">
            <span><b className="text-gray-900">{totals.products ?? 0}</b>
              <span className="text-gray-400"> products</span></span>
            <span><b className="text-gray-900">{(totals.total_units ?? 0).toLocaleString()}</b>
              <span className="text-gray-400"> units</span></span>
            <span><b className="text-gray-900">{money(totals.total_value_at_retail)}</b>
              <span className="text-gray-400"> at retail</span></span>
            <button
              onClick={handleDownload}
              disabled={!items.length}
              className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40"
            >
              <Download size={13} /> CSV
            </button>
          </div>
        </div>

        <div className="overflow-auto flex-1">
          {loading ? (
            <p className="flex items-center gap-2 text-sm text-gray-500 p-8 justify-center">
              <Loader2 size={15} className="animate-spin" /> Building the list…
            </p>
          ) : error ? (
            <p className="flex items-center gap-2 text-sm text-red-600 p-8 justify-center">
              <AlertCircle size={15} /> {error}
            </p>
          ) : !items.length ? (
            <p className="text-sm text-gray-500 p-8 text-center">
              Nothing needs reordering for a {horizon}-week horizon. Try a longer one.
            </p>
          ) : (
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-gray-50 text-gray-500">
                <tr className="text-left">
                  <th className="px-4 py-2 font-semibold">Product</th>
                  <th className="px-3 py-2 font-semibold">Urgency</th>
                  <th className="px-3 py-2 font-semibold text-right">On hand</th>
                  <th className="px-3 py-2 font-semibold text-right">Sold</th>
                  <th className="px-3 py-2 font-semibold text-right">Per week</th>
                  <th className="px-3 py-2 font-semibold text-right">Order</th>
                  <th className="px-3 py-2 font-semibold text-right">Retail</th>
                  <th className="px-4 py-2 font-semibold text-right">Line value</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r, i) => (
                  <tr key={`${r.sku}-${r.product_name}-${i}`}
                      className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-2">
                      <p className="font-medium text-gray-900 truncate max-w-xs">{r.product_name}</p>
                      <p className="text-[10px] text-gray-400">{r.category}{r.sku && ` · ${r.sku}`}</p>
                    </td>
                    <td className="px-3 py-2">
                      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                        URGENCY_STYLE[r.urgency] || 'bg-gray-100 text-gray-600'}`}>
                        {r.urgency}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-gray-600">{r.stock_on_hand}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-gray-600">{r.units_sold_in_period}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-gray-600">{r.weekly_sales_rate}</td>
                    <td className="px-3 py-2 text-right tabular-nums font-bold text-gray-900">{r.suggested_quantity}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-gray-600">{money(r.unit_price)}</td>
                    <td className="px-4 py-2 text-right tabular-nums font-semibold text-gray-900">
                      {money(r.line_value_at_retail)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <footer className="px-5 py-2.5 border-t border-gray-100 bg-gray-50">
          <p className="text-[10px] text-gray-500">{data?.disclaimer}</p>
        </footer>
      </div>
    </div>
  )
}
