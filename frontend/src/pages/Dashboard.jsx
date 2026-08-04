/**
 * Dashboard.jsx — PHASE 22: BUSINESS CONTROL CENTER
 *
 * This is not an analytics page. It answers four questions in order, and the
 * layout is that order:
 *      1. How healthy is my business?      → Business Health Score
 *      2. What is costing me money?        → Executive Summary + Cash Frozen
 *      3. What should I do today?          → Action Center
 *      4. What has the highest ROI?        → Growth Opportunities (ranked)
 * Then the supporting detail: inventory distribution, category intelligence,
 * revenue trend and campaign ROI.
 *
 * EVERY NUMBER ON THIS PAGE IS COMPUTED DETERMINISTICALLY ON THE SERVER.
 * The AI Advisor inside each action card explains those numbers in business
 * English and is incapable of changing one — an invented figure is rejected
 * server-side and replaced with deterministic text.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import {
  Boxes, Snowflake, TrendingUp, Info, ArrowRight,
  Clock, Activity, ChevronDown, ChevronUp,
} from 'lucide-react'
import { analyticsApi, intelligenceApi } from '../api/client'
import Layout from '../components/Layout'
import HealthScore from './dashboard/HealthScore'
import ActionCard from './dashboard/ActionCard'
import MarginPrompt from './dashboard/MarginPrompt'

const money = (n) => `$${Math.round(Number(n) || 0).toLocaleString()}`
const compact = (n) => {
  const v = Number(n) || 0
  return v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(0)}`
}

// Worst → best, so the eye lands on the problem first.
const CLASS_ORDER = ['sold_out', 'dead', 'sleeping', 'overstock', 'heavy',
                     'healthy', 'reorder', 'critical', 'negative']

const CLASS_META = {
  negative:  { label: 'Negative count', color: '#a855f7', note: 'Data to fix' },
  sold_out:  { label: 'Sold out',       color: '#dc2626', note: 'Losing sales' },
  dead:      { label: 'Dead',           color: '#7f1d1d', note: 'Never moved' },
  critical:  { label: 'Critical',       color: '#f97316', note: 'Under 1 week' },
  reorder:   { label: 'Reorder',        color: '#f59e0b', note: 'Under 3 weeks' },
  healthy:   { label: 'Healthy',        color: '#16a34a', note: '3–12 weeks' },
  heavy:     { label: 'Heavy',          color: '#a3a3a3', note: '3–6 months' },
  overstock: { label: 'Overstock',      color: '#78716c', note: '6–12 months' },
  sleeping:  { label: 'Sleeping',       color: '#44403c', note: 'Over a year' },
}

function Stat({ icon: Icon, label, value, sub, tone = 'default' }) {
  const tones = {
    default: 'text-gray-900', bad: 'text-red-600', good: 'text-green-600',
  }
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} className="text-gray-400" />
        <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      </div>
      <p className={`text-2xl font-bold tabular-nums ${tones[tone]}`}>{value}</p>
      {sub && <p className="text-[11px] text-gray-400 mt-0.5">{sub}</p>}
    </div>
  )
}

export default function Dashboard() {
  const [bi, setBi] = useState(null)
  const [trend, setTrend] = useState([])
  const [campaign, setCampaign] = useState(null)
  const [showAssumptions, setShowAssumptions] = useState(false)
  const [showAllActions, setShowAllActions] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Named so it can be re-run after a setting changes — saving a gross margin
  // re-values every figure on the page, and the server owns that arithmetic.
  const load = useCallback(async () => {
    try {
      const { data } = await intelligenceApi.all()
      setBi(data)
      setError('')
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message
        ?? 'Could not load your business intelligence.')
    } finally { setLoading(false) }
    // Supporting panels — never block the control centre if they fail
    analyticsApi.trend().then((r) => setTrend(r.data)).catch(() => {})
    analyticsApi.campaignSummary().then((r) => setCampaign(r.data)).catch(() => {})
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) {
    return <Layout><p className="text-sm text-gray-400">Analysing your business…</p></Layout>
  }
  if (error) {
    return (
      <Layout>
        <div className="max-w-xl bg-red-50 text-red-600 rounded-xl p-4 text-sm">{error}</div>
      </Layout>
    )
  }
  if (!bi || bi.empty) {
    return (
      <Layout>
        <div className="max-w-lg mx-auto text-center py-16">
          <Boxes size={40} className="text-gray-300 mx-auto mb-4" />
          <h1 className="text-xl font-bold text-gray-900 mb-2">No data yet</h1>
          <p className="text-sm text-gray-500 mb-6">
            Upload a POS sales report and LiquorIQ will tell you where your cash is
            sitting and what to do about it.
          </p>
          <Link to="/uploads"
            className="inline-flex items-center gap-2 text-sm font-semibold px-5 py-2.5 rounded-xl bg-brand-500 text-white">
            Upload a report <ArrowRight size={15} />
          </Link>
        </div>
      </Layout>
    )
  }

  const { headline, business_health: health, actions = [], opportunities = [],
          summary = {}, categories = [], period = {}, coverage = {},
          valuation = {} } = bi

  const classes = CLASS_ORDER
    .filter((k) => summary.by_class?.[k])
    .map((k) => ({ key: k, ...CLASS_META[k], ...summary.by_class[k] }))
  const maxClassValue = Math.max(...classes.map((c) => c.value || 0), 1)
  const visibleActions = showAllActions ? actions : actions.slice(0, 4)
  const topCategories = categories.slice(0, 6)
  const maxCatValue = Math.max(...topCategories.map((c) => c.inventory_value || 0), 1)

  return (
    <Layout>
      <div className="max-w-6xl mx-auto space-y-6">

        {/* ── Header ── */}
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Business Control Center</h1>
            <p className="text-sm text-gray-500">
              {period.start && period.end
                ? `Based on ${period.start} to ${period.end} (${period.days} days)`
                : `Based on the last ${period.days} days`}
              {period.estimated && ' · period estimated'}
              {period.uploads > 0 && ` · ${period.uploads} upload${period.uploads === 1 ? '' : 's'}`}
            </p>
          </div>
          <Link to="/uploads" className="text-xs font-semibold text-brand-600 hover:underline">
            Upload newer data →
          </Link>
        </div>

        {/* ── Insufficient-data banner ──
            One upload is enough to see WHERE the cash is, but not enough to
            know whether a product sells reliably. Saying so up front is more
            useful than quietly labelling everything "medium confidence". */}
        {(period.uploads <= 1 || period.estimated) && (
          <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-2xl p-4">
            <Info size={16} className="text-amber-600 mt-0.5 shrink-0" />
            <div className="text-xs text-amber-900">
              <p className="font-semibold mb-0.5">
                {period.uploads <= 1
                  ? 'Working from a single reporting period'
                  : 'This report did not state its date range'}
              </p>
              <p className="text-amber-800">
                {period.uploads <= 1
                  ? 'Stock levels and cash frozen are exact. Sales velocity is based on one period, so reorder timing is an estimate — upload again next week and confidence rises automatically.'
                  : `Velocity is calculated against an assumed ${period.days}-day period. If that's wrong, reorder and overstock verdicts shift with it.`}
              </p>
            </div>
          </div>
        )}

        {/* ── 1. How healthy is my business? ── */}
        <HealthScore health={health} />

        {/* ── 2. What is costing me money? ── */}
        <MarginPrompt valuation={valuation} onSaved={load} />

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Labels come from the server's valuation block, never from here.
              These figures are RETAIL until the owner supplies his margin, and
              "Cash frozen" over a retail number overstated what he had spent by
              his entire margin — $220,661 shown for roughly $154,000 of cash. */}
          <Stat icon={Boxes} label={valuation.inventory_label ?? 'Inventory value'}
            value={money(valuation.inventory_headline ?? headline.inventory_value)}
            sub={`${summary.products?.toLocaleString()} products`} />
          <Stat icon={Snowflake} label={valuation.frozen_label ?? 'Cash frozen'}
            value={money(valuation.frozen_headline ?? headline.cash_frozen)}
            sub={`${headline.frozen_pct}% of inventory`} tone="bad" />
          <Stat icon={Activity} label="Inventory turnover"
            value={headline.turnover ? `${headline.turnover}×` : '—'}
            sub="healthy is 4–6× a year"
            tone={headline.turnover >= 4 ? 'good' : 'bad'} />
          <Stat icon={TrendingUp} label="Opportunity on the table"
            value={money(headline.opportunity_value)}
            sub={`${money(headline.opportunity_value_adjusted)} confidence-adjusted`}
            tone="good" />
        </div>

        {/* ── 3. What should I do today? ── */}
        <section>
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <div>
              <h2 className="text-lg font-bold text-gray-900">Today&rsquo;s Action Center</h2>
              <p className="text-xs text-gray-500">
                Ranked by financial impact × confidence, so a shaky big number
                can&rsquo;t outrank a solid one.
              </p>
            </div>
            <div className="flex items-center gap-1.5 text-[11px]">
              {['P1', 'P2', 'P3'].map((p) => (
                bi.priority_counts?.[p] > 0 && (
                  <span key={p} className="px-2 py-1 rounded-lg bg-gray-100 text-gray-600 font-semibold">
                    {bi.priority_counts[p]} × {p}
                  </span>
                )
              ))}
            </div>
          </div>

          {actions.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center">
              <p className="text-sm text-gray-500">
                Nothing urgent. Your stock levels look balanced.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {visibleActions.map((a) => <ActionCard key={a.id} action={a} />)}
              {actions.length > 4 && (
                <button onClick={() => setShowAllActions(!showAllActions)}
                  className="w-full text-xs font-semibold text-gray-500 hover:text-gray-800 py-2">
                  {showAllActions
                    ? 'Show fewer'
                    : `Show ${actions.length - 4} more recommendation${actions.length - 4 === 1 ? '' : 's'}`}
                </button>
              )}
            </div>
          )}
        </section>

        {/* ── 4. Inventory distribution — where the cash actually sits ── */}
        <section className="bg-white rounded-2xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
            <div>
              <h2 className="text-base font-bold text-gray-900">Inventory health</h2>
              <p className="text-xs text-gray-500">
                Every product placed by how long its stock will last
              </p>
            </div>
            <Link to="/ai?focus=clearance"
              className="text-xs font-semibold text-brand-600 hover:underline">
              Act on the slow movers →
            </Link>
          </div>

          <div className="space-y-2">
            {classes.map((c) => (
              <div key={c.key} className="flex items-center gap-3">
                <span className="w-28 shrink-0 text-xs font-medium text-gray-700">{c.label}</span>
                <div className="flex-1 h-6 bg-gray-50 rounded-md overflow-hidden">
                  <div className="h-full rounded-md transition-all"
                    style={{ width: `${Math.max((c.value / maxClassValue) * 100, 1.5)}%`,
                             backgroundColor: c.color, opacity: 0.85 }} />
                </div>
                <span className="w-16 shrink-0 text-right text-xs font-semibold text-gray-900 tabular-nums">
                  {compact(c.value)}
                </span>
                <span className="w-20 shrink-0 text-right text-[11px] text-gray-400 tabular-nums">
                  {c.count} item{c.count === 1 ? '' : 's'}
                </span>
                <span className="hidden sm:block w-24 shrink-0 text-[10px] text-gray-400">{c.note}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ── 5. Category intelligence ── */}
        <section className="bg-white rounded-2xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
            <h2 className="text-base font-bold text-gray-900">Category intelligence</h2>
            <span className="text-[11px] text-gray-400">
              {coverage.resolved_pct}% of products categorised automatically
            </span>
          </div>
          <p className="text-xs text-gray-500 mb-4">
            Sorted by cash frozen — which part of the shop is holding your money
          </p>

          <div className="overflow-x-auto -mx-1">
            <table className="w-full text-xs min-w-[620px]">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-gray-400 border-b border-gray-100">
                  <th className="text-left font-medium py-2 px-1">Category</th>
                  <th className="text-right font-medium py-2 px-1">Revenue</th>
                  <th className="text-right font-medium py-2 px-1">Inventory</th>
                  <th className="text-right font-medium py-2 px-1">Cash frozen</th>
                  <th className="text-left font-medium py-2 px-2 w-28">Frozen share</th>
                  <th className="text-right font-medium py-2 px-1">Fast</th>
                  <th className="text-right font-medium py-2 px-1">Slow</th>
                  <th className="text-right font-medium py-2 px-1">Out</th>
                </tr>
              </thead>
              <tbody>
                {topCategories.map((c) => (
                  <tr key={c.category} className="border-b border-gray-50 hover:bg-gray-50/60">
                    <td className="py-2 px-1 font-semibold text-gray-800">{c.category}</td>
                    <td className="py-2 px-1 text-right tabular-nums text-gray-700">{compact(c.revenue)}</td>
                    <td className="py-2 px-1 text-right tabular-nums text-gray-700">{compact(c.inventory_value)}</td>
                    <td className="py-2 px-1 text-right tabular-nums font-semibold text-red-600">
                      {compact(c.cash_frozen)}
                    </td>
                    <td className="py-2 px-2">
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-red-400 rounded-full"
                          style={{ width: `${Math.min(c.frozen_pct, 100)}%` }} />
                      </div>
                      <span className="text-[10px] text-gray-400">{c.frozen_pct}%</span>
                    </td>
                    <td className="py-2 px-1 text-right tabular-nums text-green-600">{c.fast_movers}</td>
                    <td className="py-2 px-1 text-right tabular-nums text-gray-500">{c.slow_movers}</td>
                    <td className="py-2 px-1 text-right tabular-nums text-red-500">{c.sold_out}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* ── 6. Growth opportunities (ranked) ── */}
        {opportunities.length > 0 && (
          <section className="bg-white rounded-2xl border border-gray-200 p-5">
            <h2 className="text-base font-bold text-gray-900 mb-1">Growth opportunities</h2>
            <p className="text-xs text-gray-500 mb-4">
              Ranked by estimated value × confidence
            </p>
            <div className="space-y-2">
              {opportunities.map((o) => (
                <div key={o.type}
                  className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                  <span className="w-6 text-xs font-bold text-gray-300 tabular-nums">#{o.rank}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-gray-800 truncate">{o.title}</p>
                    <p className="text-[10px] text-gray-400 truncate">{o.confidence_reason}</p>
                  </div>
                  <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0 ${
                    o.confidence === 'high' ? 'bg-green-50 text-green-700'
                      : o.confidence === 'medium' ? 'bg-amber-50 text-amber-700'
                      : 'bg-gray-100 text-gray-500'}`}>
                    {o.confidence}
                  </span>
                  <span className="w-20 text-right text-sm font-bold text-gray-900 tabular-nums shrink-0">
                    {compact(o.value_score)}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ── 7. Revenue trend + campaign ROI ── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-200 p-5">
            <h2 className="text-base font-bold text-gray-900 mb-3">Revenue trend</h2>
            {trend.length > 1 ? (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                  <XAxis dataKey="period" tick={{ fontSize: 11 }} stroke="#9ca3af" />
                  <YAxis tick={{ fontSize: 11 }} stroke="#9ca3af"
                    tickFormatter={(v) => compact(v)} />
                  <Tooltip formatter={(v) => money(v)} />
                  <Area type="monotone" dataKey="revenue" stroke="#e8a020"
                    fill="#e8a020" fillOpacity={0.15} strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[200px] flex flex-col items-center justify-center text-center">
                <Clock size={24} className="text-gray-300 mb-2" />
                <p className="text-xs text-gray-500 max-w-xs">
                  A single upload gives one data point. Upload weekly and this
                  becomes a real trend — it also sharpens every reorder verdict.
                </p>
              </div>
            )}
          </div>

          <div className="bg-white rounded-2xl border border-gray-200 p-5">
            <h2 className="text-base font-bold text-gray-900 mb-3">Campaign ROI</h2>
            {campaign?.revenue_lift != null ? (
              <>
                <p className="text-3xl font-bold text-green-600 tabular-nums">
                  {money(campaign.revenue_lift)}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  measured lift from {campaign.strategy_title || 'your last campaign'}
                </p>
                {campaign.units_lift_pct != null && (
                  <p className="text-xs text-gray-400 mt-2">
                    {campaign.units_lift_pct > 0 ? '▲' : '▼'} {Math.abs(campaign.units_lift_pct)}% units
                    vs the pre-campaign baseline
                  </p>
                )}
              </>
            ) : (
              <div className="py-6 text-center">
                <p className="text-xs text-gray-500 mb-3">No campaign measured yet.</p>
                <Link to="/ai" className="text-xs font-semibold text-brand-600 hover:underline">
                  Generate a campaign →
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* ── Assumptions — every derived number is traceable ── */}
        <section className="bg-white rounded-2xl border border-gray-200 p-5">
          <button onClick={() => setShowAssumptions(!showAssumptions)}
            className="w-full flex items-center justify-between text-left">
            <span className="flex items-center gap-2">
              <Info size={14} className="text-gray-400" />
              <span className="text-sm font-semibold text-gray-700">
                How these numbers were calculated
              </span>
            </span>
            {showAssumptions ? <ChevronUp size={15} className="text-gray-400" />
              : <ChevronDown size={15} className="text-gray-400" />}
          </button>

          {showAssumptions && (
            <div className="mt-4 space-y-3">
              <p className="text-xs text-gray-500">
                Stock levels, sales rates and inventory values are measured directly
                from your POS export. Your export contains no cost data, so anything
                describing profit or a response rate uses the assumptions below —
                stated openly rather than hidden inside a formula.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5">
                {bi.assumptions?.map((a) => (
                  <div key={a.key} className="flex items-baseline justify-between gap-2 text-xs">
                    <span className="text-gray-500">{a.label}</span>
                    <span className="font-semibold text-gray-800">{a.value}</span>
                  </div>
                ))}
              </div>
              {bi.non_product_lines > 0 && (
                <p className="text-[11px] text-gray-400 pt-2 border-t border-gray-100">
                  {bi.non_product_lines} non-product line{bi.non_product_lines === 1 ? '' : 's'}
                  {' '}(tips, delivery fees, bag tax) were excluded from inventory analysis.
                </p>
              )}
            </div>
          )}
        </section>
      </div>
    </Layout>
  )
}
