/**
 * HealthScore.jsx — PHASE 22: the one number, with its parts visible.
 *
 * A score with no visible components is a horoscope. Every contributing metric
 * is shown next to its target and its weight, so the owner can see WHY the
 * number is what it is and which lever moves it.
 */

const BANDS = {
  strong:            { ring: '#16a34a', tint: 'bg-green-50',  text: 'text-green-700' },
  stable:            { ring: '#65a30d', tint: 'bg-lime-50',   text: 'text-lime-700' },
  'needs attention': { ring: '#ea9a1a', tint: 'bg-amber-50',  text: 'text-amber-700' },
  'at risk':         { ring: '#dc2626', tint: 'bg-red-50',    text: 'text-red-700' },
}

export default function HealthScore({ health }) {
  if (!health) return null
  const band = BANDS[health.band] ?? BANDS.stable
  const circumference = 2 * Math.PI * 52
  const dash = (health.score / 100) * circumference

  return (
    <section className="bg-white rounded-2xl border border-gray-200 p-6">
      <div className="flex flex-col sm:flex-row items-center gap-6">
        {/* The dial */}
        <div className="relative shrink-0" style={{ width: 132, height: 132 }}>
          <svg width="132" height="132" className="-rotate-90">
            <circle cx="66" cy="66" r="52" fill="none" stroke="#f1f1f1" strokeWidth="12" />
            <circle cx="66" cy="66" r="52" fill="none" stroke={band.ring} strokeWidth="12"
              strokeLinecap="round" strokeDasharray={`${dash} ${circumference}`} />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-3xl font-bold text-gray-900 tabular-nums">{health.score}</span>
            <span className="text-[10px] text-gray-400 uppercase tracking-wide">out of 100</span>
          </div>
        </div>

        <div className="flex-1 min-w-0 text-center sm:text-left">
          <div className="flex items-center gap-2 justify-center sm:justify-start mb-1">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
              Business health
            </h2>
            <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${band.tint} ${band.text} capitalize`}>
              {health.band}
            </span>
          </div>
          <p className="text-lg font-semibold text-gray-900 mb-4">{health.verdict}</p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-2">
            {health.components?.map((c) => (
              <div key={c.key} className="flex items-baseline justify-between gap-2 text-xs">
                <span className="text-gray-500 truncate">{c.label}</span>
                <span className="flex items-baseline gap-1.5 shrink-0">
                  <span className="font-semibold text-gray-900 tabular-nums">
                    {c.value ?? '—'}{c.key === 'turnover' ? '×' : '%'}
                  </span>
                  <span className="text-[10px] text-gray-400">target {c.target}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
