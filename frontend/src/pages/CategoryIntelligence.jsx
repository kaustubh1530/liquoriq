/**
 * CategoryIntelligence.jsx — every category, not just the top six.
 *
 * The dashboard shows six categories because six is what fits before the page
 * stops being scannable. The rest live here, along with how the categories
 * were resolved in the first place — a shop owner who sees "Wine" against a
 * bottle he considers Champagne needs to know where that judgement came from
 * and that he can overrule it.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Sparkles } from 'lucide-react'
import { intelligenceApi } from '../api/client'
import Layout from '../components/Layout'
import CategoryPanel from './dashboard/CategoryPanel'

const money = (n) => `$${Math.round(Number(n) || 0).toLocaleString()}`

const SOURCE_LABEL = {
  manual: 'You corrected these',
  cache: 'Remembered from a previous upload',
  brand: 'Matched a known brand',
  dictionary: 'Matched a keyword or varietal',
  ai: 'Resolved by AI',
  fallback: 'Could not be resolved',
}

export default function CategoryIntelligence() {
  const [bi, setBi] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const { data } = await intelligenceApi.all()
      setBi(data)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) {
    return <Layout><div className="max-w-4xl mx-auto h-64 bg-slate-100 rounded-3xl animate-pulse" /></Layout>
  }

  const categories = bi?.categories ?? []
  const coverage = bi?.coverage ?? {}
  const totalFrozen = categories.reduce((s, c) => s + (c.cash_frozen ?? 0), 0)
  const totalValue = categories.reduce((s, c) => s + (c.inventory_value ?? 0), 0)

  return (
    <Layout>
      <div className="max-w-4xl mx-auto space-y-5 pb-10">
        <div>
          <Link to="/dashboard"
            className="inline-flex items-center gap-1.5 text-[12px] font-medium text-slate-500 hover:text-slate-900 mb-3">
            <ArrowLeft size={13} /> Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-slate-900">Category intelligence</h1>
          <p className="text-[13px] text-slate-500 mt-1">
            Which part of the shop is holding your money
          </p>
        </div>

        <div className="grid sm:grid-cols-3 gap-4">
          {[
            ['Categories', categories.length, null],
            ['Inventory value (retail)', money(totalValue), null],
            ['Money stuck', money(totalFrozen),
             totalValue ? `${Math.round((totalFrozen / totalValue) * 100)}% of stock` : null],
          ].map(([label, value, sub]) => (
            <div key={label} className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-5">
              <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wide">{label}</p>
              <p className="text-2xl font-bold text-slate-900 tabular-nums mt-1">{value}</p>
              {sub && <p className="text-[11px] text-slate-400">{sub}</p>}
            </div>
          ))}
        </div>

        <section className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-6">
          <h2 className="text-[15px] font-bold text-slate-900 mb-1">All categories</h2>
          <p className="text-[12px] text-slate-500 mb-4">
            Health is the share of a category&rsquo;s value that is still moving.
            Tap a row for the detail.
          </p>
          <CategoryPanel categories={categories} />
        </section>

        <section className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-6">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles size={14} className="text-slate-400" />
            <h2 className="text-[15px] font-bold text-slate-900">How these were worked out</h2>
          </div>
          <p className="text-[12px] text-slate-500 mb-4">
            Your POS export has no category column, so LiquorIQ resolves each one
            — your corrections always win, and are remembered permanently.
          </p>

          <div className="flex items-baseline gap-2 mb-4">
            <span className="text-3xl font-bold text-slate-900 tabular-nums">
              {coverage.resolved_pct}%
            </span>
            <span className="text-[12px] text-slate-500">
              of {coverage.total?.toLocaleString()} products categorised automatically
            </span>
          </div>

          <div className="space-y-2">
            {Object.entries(coverage.by_source ?? {})
              .sort((a, b) => b[1] - a[1])
              .map(([source, count]) => (
                <div key={source} className="flex items-center gap-3">
                  <span className="w-56 shrink-0 text-[12px] text-slate-600">
                    {SOURCE_LABEL[source] ?? source}
                  </span>
                  <span className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <span className="block h-full bg-blue-500 rounded-full"
                      style={{ width: `${(count / (coverage.total || 1)) * 100}%` }} />
                  </span>
                  <span className="w-14 text-right text-[12px] font-semibold text-slate-800 tabular-nums">
                    {count.toLocaleString()}
                  </span>
                </div>
              ))}
          </div>
        </section>
      </div>
    </Layout>
  )
}
