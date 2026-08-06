/**
 * InventoryBands.jsx — where the money is sitting, by how long stock will last.
 *
 * DESIGN NOTES
 *
 * Colour carries meaning and nothing else. Green is healthy, amber needs
 * attention, red is losing money today, slate is money asleep. The previous
 * version used nine distinct colours including three near-identical browns,
 * which meant the palette encoded ORDER rather than SEVERITY — the eye had to
 * decode a legend instead of reading the chart.
 *
 * Bands are clickable. A number the owner can't interrogate is a number he has
 * to take on faith, and "115 sold out" invites exactly one question: which ones?
 */

import { ChevronRight } from 'lucide-react'
import { CLASS_ORDER, CLASS_META, TONE, compact } from './inventoryClasses'

export default function InventoryBands({ summary, onSelect, dense = false }) {
  const bands = CLASS_ORDER
    .filter((k) => summary?.by_class?.[k])
    .map((k) => ({ key: k, ...CLASS_META[k], ...summary.by_class[k] }))

  const maxValue = Math.max(...bands.map((b) => b.value || 0), 1)
  const totalProducts = bands.reduce((sum, b) => sum + b.count, 0) || 1

  if (!bands.length) {
    return <p className="text-sm text-slate-400 py-6 text-center">No inventory data yet.</p>
  }

  return (
    <div className={dense ? 'space-y-1' : 'space-y-1.5'}>
      {bands.map((b) => {
        const tone = TONE[b.tone]
        const share = ((b.count / totalProducts) * 100).toFixed(1)
        return (
          <button
            key={b.key}
            onClick={() => onSelect?.(b.key)}
            title={`${b.count} products · ${compact(b.value)} at retail · ${share}% of your range · ${b.note}`}
            className="w-full group flex items-center gap-3 rounded-xl px-3 py-2.5 hover:bg-slate-50 transition-colors text-left"
          >
            <span className="w-32 shrink-0">
              <span className="block text-[13px] font-semibold text-slate-800">{b.label}</span>
              <span className="block text-[11px] text-slate-400">{b.note}</span>
            </span>

            <span className="flex-1 h-2.5 bg-slate-100 rounded-full overflow-hidden">
              <span
                className={`block h-full rounded-full ${tone.bar} transition-all duration-500`}
                style={{ width: `${Math.max((b.value / maxValue) * 100, 2)}%` }}
              />
            </span>

            <span className="w-20 shrink-0 text-right text-[13px] font-semibold text-slate-900 tabular-nums">
              {compact(b.value)}
            </span>
            <span className={`w-24 shrink-0 text-right text-[12px] font-medium tabular-nums ${tone.text}`}>
              {b.count.toLocaleString()} item{b.count === 1 ? '' : 's'}
            </span>
            {onSelect && (
              <ChevronRight size={15}
                className="shrink-0 text-slate-300 group-hover:text-slate-500 transition-colors" />
            )}
          </button>
        )
      })}
    </div>
  )
}
