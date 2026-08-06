/**
 * InventoryIntelligence.jsx — the drill-down behind the dashboard's bands.
 *
 * NOTHING WAS DELETED FROM THE DASHBOARD. It was moved here.
 *
 * The dashboard answers "what should I do today". This page answers "show me
 * the products", which is a different job with a different pace: the owner
 * arrives with a specific question ("which 115 are sold out?") and wants a
 * list he can work through, not a summary.
 *
 * Arriving from a band pre-selects that filter, so the click that got him here
 * is already applied — a filter he has to re-apply is a filter that wasted his
 * click.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Search } from 'lucide-react'
import { intelligenceApi } from '../api/client'
import Layout from '../components/Layout'
import ActionCard from './dashboard/ActionCard'
import InventoryBands from './dashboard/InventoryBands'
import { CLASS_META, TONE } from './dashboard/inventoryClasses'

const money = (n) => `$${Math.round(Number(n) || 0).toLocaleString()}`

export default function InventoryIntelligence() {
  const [params, setParams] = useSearchParams()
  const selected = params.get('class') || ''

  const [bi, setBi] = useState(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const { data } = await intelligenceApi.all()
      setBi(data)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const products = useMemo(() => {
    let rows = bi?.products ?? []
    if (selected) rows = rows.filter((p) => p.stock_class === selected)
    if (query.trim()) {
      const q = query.trim().toLowerCase()
      rows = rows.filter((p) => (p.product_name ?? '').toLowerCase().includes(q))
    }
    return rows
  }, [bi, selected, query])

  if (loading) {
    return <Layout><div className="max-w-5xl mx-auto h-64 bg-slate-100 rounded-3xl animate-pulse" /></Layout>
  }

  const summary = bi?.summary ?? {}
  const actions = bi?.actions ?? []
  const meta = selected ? CLASS_META[selected] : null

  return (
    <Layout>
      <div className="max-w-5xl mx-auto space-y-5 pb-10">
        <div>
          <Link to="/dashboard"
            className="inline-flex items-center gap-1.5 text-[12px] font-medium text-slate-500 hover:text-slate-900 mb-3">
            <ArrowLeft size={13} /> Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-slate-900">Inventory intelligence</h1>
          <p className="text-[13px] text-slate-500 mt-1">
            Every product, placed by how long its stock will last
          </p>
        </div>

        <section className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-6">
          <InventoryBands summary={summary}
            onSelect={(cls) => setParams(cls === selected ? {} : { class: cls })} />
        </section>

        {/* All recommendations live here — the dashboard shows only the top 3. */}
        {actions.length > 0 && (
          <section>
            <h2 className="text-[15px] font-bold text-slate-900 mb-1">
              All {actions.length} recommendations
            </h2>
            <p className="text-[12px] text-slate-500 mb-4">
              Ranked by money at stake × how confident we are in the number
            </p>
            <div className="space-y-3">
              {actions.map((a) => <ActionCard key={a.id} action={a} />)}
            </div>
          </section>
        )}

        <section className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-6">
          <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
            <div>
              <h2 className="text-[15px] font-bold text-slate-900">
                {meta ? meta.label : 'All products'}
                <span className="ml-2 text-[12px] font-medium text-slate-400">
                  {products.length.toLocaleString()}
                </span>
              </h2>
              {meta && <p className="text-[12px] text-slate-500">{meta.note}</p>}
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {selected && (
                <button onClick={() => setParams({})}
                  className="text-[11px] font-semibold px-2.5 py-1.5 rounded-lg bg-slate-100 text-slate-600">
                  Clear filter
                </button>
              )}
              <div className="relative">
                <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input value={query} onChange={(e) => setQuery(e.target.value)}
                  placeholder="Find a product"
                  className="w-52 text-[12px] pl-8 pr-3 py-1.5 rounded-xl ring-1 ring-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-900" />
              </div>
            </div>
          </div>

          <div className="overflow-x-auto -mx-2">
            <table className="w-full text-[12px] min-w-[640px]">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-slate-400 border-b border-slate-100">
                  <th className="text-left font-medium py-2 px-2">Product</th>
                  <th className="text-left font-medium py-2 px-2">Status</th>
                  <th className="text-right font-medium py-2 px-2">On hand</th>
                  <th className="text-right font-medium py-2 px-2">Sold</th>
                  <th className="text-right font-medium py-2 px-2">Weeks left</th>
                  <th className="text-right font-medium py-2 px-2">Retail value</th>
                </tr>
              </thead>
              <tbody>
                {products.slice(0, 200).map((p, i) => {
                  const m = CLASS_META[p.stock_class] ?? {}
                  return (
                    <tr key={`${p.sku}-${i}`} className="border-b border-slate-50 hover:bg-slate-50/70">
                      <td className="py-2 px-2">
                        <p className="font-semibold text-slate-800 truncate max-w-xs">{p.product_name}</p>
                        <p className="text-[10px] text-slate-400">{p.category}</p>
                      </td>
                      <td className="py-2 px-2">
                        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                          TONE[m.tone]?.chip ?? 'bg-slate-100 text-slate-600'}`}>
                          {m.label ?? p.stock_class}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-right tabular-nums text-slate-600">{p.stock}</td>
                      <td className="py-2 px-2 text-right tabular-nums text-slate-600">{p.units_sold}</td>
                      <td className="py-2 px-2 text-right tabular-nums text-slate-600">
                        {p.weeks_of_supply ?? '—'}
                      </td>
                      <td className="py-2 px-2 text-right tabular-nums font-semibold text-slate-900">
                        {money(p.inventory_value)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {products.length > 200 && (
              <p className="text-[11px] text-slate-400 text-center pt-3">
                Showing the first 200 of {products.length.toLocaleString()} — search to narrow it down.
              </p>
            )}
            {products.length === 0 && (
              <p className="text-[12px] text-slate-400 text-center py-8">
                No products match.
              </p>
            )}
          </div>
        </section>
      </div>
    </Layout>
  )
}
