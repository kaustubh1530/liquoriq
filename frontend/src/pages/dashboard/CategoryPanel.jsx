/**
 * CategoryPanel.jsx — which part of the shop is holding the money.
 *
 * DESIGN NOTES
 *
 * The old version was an eight-column table with every value right-aligned and
 * grey. Everything looked equally important, which means nothing was. A shop
 * owner does not read a table; he scans for the row that's wrong.
 *
 * So: one traffic light per category, sized numbers, and the detail folded
 * away until asked for. Health is derived from figures the server already
 * returned (frozen share) — nothing new is computed here.
 *
 * Sortable because "which category holds the most money" and "which is
 * healthiest" are different questions and the owner asks both.
 */

import { useMemo, useState } from 'react'
import { ChevronDown, ChevronUp, ArrowUpDown } from 'lucide-react'

const compact = (n) => {
  const v = Number(n) || 0
  return v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(0)}`
}

/**
 * Health = the inverse of the frozen share, which the server computed.
 * A category with 80% of its value frozen is 20% healthy. Presentation of an
 * existing figure, not a new metric.
 */
function healthOf(category) {
  return Math.max(0, Math.round(100 - (category.frozen_pct ?? 0)))
}

function light(health) {
  if (health >= 60) return { dot: 'bg-emerald-500', text: 'text-emerald-700',
                             chip: 'bg-emerald-50', label: 'Healthy' }
  if (health >= 35) return { dot: 'bg-amber-500', text: 'text-amber-700',
                             chip: 'bg-amber-50', label: 'Needs attention' }
  return { dot: 'bg-red-500', text: 'text-red-700', chip: 'bg-red-50', label: 'Critical' }
}

const SORTS = {
  frozen: { label: 'Money stuck', get: (c) => -(c.cash_frozen ?? 0) },
  health: { label: 'Health', get: (c) => healthOf(c) },
  value: { label: 'Inventory value', get: (c) => -(c.inventory_value ?? 0) },
  revenue: { label: 'Revenue', get: (c) => -(c.revenue ?? 0) },
}

export default function CategoryPanel({ categories = [], limit = null }) {
  const [sort, setSort] = useState('frozen')
  const [openRow, setOpenRow] = useState(null)

  const rows = useMemo(() => {
    const sorted = [...categories].sort((a, b) => SORTS[sort].get(a) - SORTS[sort].get(b))
    return limit ? sorted.slice(0, limit) : sorted
  }, [categories, sort, limit])

  if (!rows.length) {
    return <p className="text-sm text-slate-400 py-6 text-center">No categories yet.</p>
  }

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-3 flex-wrap">
        <ArrowUpDown size={12} className="text-slate-400" />
        {Object.entries(SORTS).map(([key, s]) => (
          <button
            key={key}
            onClick={() => setSort(key)}
            className={`text-[11px] font-medium px-2.5 py-1 rounded-lg transition-colors ${
              sort === key
                ? 'bg-slate-900 text-white'
                : 'text-slate-500 hover:bg-slate-100'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="divide-y divide-slate-100">
        {rows.map((c) => {
          const health = healthOf(c)
          const tone = light(health)
          const open = openRow === c.category

          return (
            <div key={c.category}>
              <button
                onClick={() => setOpenRow(open ? null : c.category)}
                className="w-full flex items-center gap-3 py-3 hover:bg-slate-50/70 rounded-xl px-2 -mx-2 transition-colors text-left"
              >
                <span className={`w-2 h-2 rounded-full shrink-0 ${tone.dot}`} />

                <span className="w-28 shrink-0 text-[13px] font-semibold text-slate-900 truncate">
                  {c.category}
                </span>

                {/* Health bar — the one thing worth scanning across rows */}
                <span className="flex-1 min-w-0">
                  <span className="flex items-center gap-2">
                    <span className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <span className={`block h-full rounded-full ${tone.dot} transition-all duration-500`}
                        style={{ width: `${health}%` }} />
                    </span>
                    <span className={`text-[11px] font-semibold tabular-nums w-9 ${tone.text}`}>
                      {health}%
                    </span>
                  </span>
                </span>

                <span className="w-20 shrink-0 text-right">
                  <span className="block text-[13px] font-semibold text-slate-900 tabular-nums">
                    {compact(c.cash_frozen)}
                  </span>
                  <span className="block text-[10px] text-slate-400">stuck</span>
                </span>

                {open ? <ChevronUp size={15} className="text-slate-400 shrink-0" />
                      : <ChevronDown size={15} className="text-slate-300 shrink-0" />}
              </button>

              {open && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pb-4 pt-1 px-4">
                  {[
                    ['Inventory value', compact(c.inventory_value)],
                    ['Revenue this period', compact(c.revenue)],
                    ['Fast movers', c.fast_movers],
                    ['Slow movers', c.slow_movers],
                    ['Sold out', c.sold_out],
                    ['Products', c.products],
                    ['Money stuck', compact(c.cash_frozen)],
                    ['Status', tone.label],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <p className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</p>
                      <p className="text-[13px] font-semibold text-slate-800 tabular-nums">{value}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
