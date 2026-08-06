/**
 * BusinessIntelligence.jsx — PHASE 22.5: the analytics workspace.
 *
 * WHY THIS PAGE EXISTS
 *
 * A dashboard that is also an analytics tool is neither. Deciding and
 * exploring are different modes: deciding happens in thirty seconds standing
 * at the till, exploring happens for twenty minutes at a desk with a coffee.
 * A single page serving both forces the owner to do the sorting himself, which
 * is the work the product is supposed to do for him.
 *
 * So the Dashboard answers "what do I do today", and everything that answers
 * "why, and what else is going on" lives here. NOTHING WAS DELETED — every
 * panel removed from the Dashboard is on this page, with more room than it had
 * before.
 *
 * Sections, in the order an owner actually asks them:
 *   1. Executive metrics      — the numbers that judge the shop
 *   2. Revenue trends         — is it moving?
 *   3. Inventory intelligence — where is the money sitting?
 *   4. Category intelligence  — which part of the shop?
 *   5. Growth opportunities   — everything ranked, not just the top 3
 *   6. Historical performance — did past campaigns work?
 *   7. Business assumptions   — what did you assume?
 *   8. Confidence indicators  — how much should I trust this?
 *
 * NO CALCULATION HAPPENS HERE. Every figure comes from the same deterministic
 * /intelligence payload the Dashboard uses.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import {
  BarChart3, LineChart, Boxes, PieChart, TrendingUp, History, Info,
  ShieldCheck, Upload, Sparkles, ArrowRight, CheckCircle2, AlertTriangle,
} from 'lucide-react'
import { analyticsApi, intelligenceApi } from '../api/client'
import Layout from '../components/Layout'
import ActionCard from './dashboard/ActionCard'
import InventoryBands from './dashboard/InventoryBands'
import CategoryPanel from './dashboard/CategoryPanel'
import { money } from './dashboard/summary'

// Four periods is where a line stops being two dots and a guess.
const TREND_MINIMUM_PERIODS = 4

const SECTIONS = [
  { id: 'metrics', label: 'Executive metrics', icon: BarChart3 },
  { id: 'trends', label: 'Revenue trends', icon: LineChart },
  { id: 'inventory', label: 'Inventory', icon: Boxes },
  { id: 'categories', label: 'Categories', icon: PieChart },
  { id: 'opportunities', label: 'Opportunities', icon: TrendingUp },
  { id: 'history', label: 'Historical', icon: History },
  { id: 'assumptions', label: 'Assumptions', icon: Info },
  { id: 'confidence', label: 'Confidence', icon: ShieldCheck },
]

function Panel({ id, icon: Icon, title, subtitle, action, children }) {
  return (
    <section id={id} className="scroll-mt-6">
      <div className="flex items-end justify-between gap-4 flex-wrap mb-3">
        <div className="flex items-start gap-2.5">
          <Icon size={16} className="text-slate-400 mt-0.5 shrink-0" />
          <div>
            <h2 className="text-[15px] font-bold text-slate-900">{title}</h2>
            {subtitle && <p className="text-[12px] text-slate-500 mt-0.5">{subtitle}</p>}
          </div>
        </div>
        {action}
      </div>
      <div className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-6">{children}</div>
    </section>
  )
}

const CONFIDENCE_TONE = {
  high: { chip: 'bg-emerald-50 text-emerald-700', icon: CheckCircle2, dot: 'bg-emerald-500' },
  medium: { chip: 'bg-amber-50 text-amber-700', icon: AlertTriangle, dot: 'bg-amber-500' },
  low: { chip: 'bg-slate-100 text-slate-600', icon: AlertTriangle, dot: 'bg-slate-400' },
}

export default function BusinessIntelligence() {
  const navigate = useNavigate()
  const [bi, setBi] = useState(null)
  const [trend, setTrend] = useState([])
  const [campaign, setCampaign] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const { data } = await intelligenceApi.all()
      setBi(data)
    } finally { setLoading(false) }
    analyticsApi.trend().then((r) => setTrend(r.data)).catch(() => {})
    analyticsApi.campaignSummary().then((r) => setCampaign(r.data)).catch(() => {})
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) {
    return (
      <Layout>
        <div className="max-w-5xl mx-auto space-y-5 animate-pulse">
          <div className="h-28 bg-slate-100 rounded-3xl" />
          <div className="h-64 bg-slate-100 rounded-3xl" />
        </div>
      </Layout>
    )
  }

  if (bi?.empty) {
    return (
      <Layout>
        <div className="max-w-lg mx-auto text-center py-20">
          <Upload size={30} className="mx-auto text-slate-300 mb-4" />
          <h1 className="text-xl font-bold text-slate-900">No data to analyse yet</h1>
          <p className="text-sm text-slate-500 mt-2 mb-6">
            Upload a POS report and this page fills with your numbers.
          </p>
          <Link to="/uploads"
            className="inline-flex items-center gap-2 text-sm font-semibold px-5 py-2.5 rounded-2xl bg-slate-900 text-white">
            Upload a report <ArrowRight size={15} />
          </Link>
        </div>
      </Layout>
    )
  }

  const { headline, business_health: health, actions = [], opportunities = [],
          summary = {}, categories = [], period = {}, coverage = {},
          valuation = {} } = bi

  const periodsCollected = period.periods ?? 0
  const hasTrend = periodsCollected >= TREND_MINIMUM_PERIODS
                   && trend.length >= TREND_MINIMUM_PERIODS

  return (
    <Layout>
      <div className="max-w-5xl mx-auto pb-12">

        <header className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900">Business Intelligence</h1>
          <p className="text-[13px] text-slate-500 mt-1">
            Based on your report for {period.start} to {period.end} ({period.days} days)
            {periodsCollected > 1 && ` · ${periodsCollected} periods on file`}
          </p>
        </header>

        {/* Jump bar — a long analytical page needs a table of contents. */}
        <nav className="flex flex-wrap gap-1.5 mb-7 sticky top-0 bg-slate-50/95 backdrop-blur py-2 z-10 -mx-1 px-1">
          {SECTIONS.map((s) => (
            <a key={s.id} href={`#${s.id}`}
              className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1.5 rounded-lg text-slate-500 hover:bg-white hover:text-slate-900 ring-1 ring-transparent hover:ring-slate-200 transition-all">
              <s.icon size={12} /> {s.label}
            </a>
          ))}
        </nav>

        <div className="space-y-8">

          {/* ═══ 1 · EXECUTIVE METRICS ════════════════════════════════════ */}
          <Panel id="metrics" icon={BarChart3} title="Executive metrics"
            subtitle="The five components behind your health score, and how each is calculated">
            <div className="flex items-center gap-5 pb-5 mb-5 border-b border-slate-100 flex-wrap">
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-bold text-slate-900 tabular-nums">
                  {Math.round(health.score)}
                </span>
                <span className="text-[13px] text-slate-400">/ 100</span>
              </div>
              <div>
                <p className="text-[14px] font-semibold text-slate-900 capitalize">{health.band}</p>
                <p className="text-[12px] text-slate-500">{health.verdict}</p>
              </div>
            </div>

            <div className="space-y-4">
              {(health.components ?? []).map((c) => (
                <div key={c.key}>
                  <div className="flex items-baseline justify-between gap-3 mb-1 flex-wrap">
                    <p className="text-[13px] font-semibold text-slate-800">
                      {c.label}
                      <span className="ml-2 text-[11px] font-normal text-slate-400">
                        weight {Math.round((c.weight ?? 0) * 100)}%
                      </span>
                    </p>
                    <p className="text-[13px] font-bold text-slate-900 tabular-nums">
                      {c.value}{c.key === 'turnover' ? '×' : '%'}
                      <span className="ml-2 text-[11px] font-normal text-slate-400">
                        target {c.target}
                      </span>
                    </p>
                  </div>
                  <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mb-1.5">
                    <div className="h-full rounded-full bg-slate-900 transition-all duration-500"
                      style={{ width: `${Math.min(c.score ?? 0, 100)}%` }} />
                  </div>
                  <p className="text-[11px] text-slate-400">
                    <code className="text-slate-500">{c.formula}</code>
                    {c.benchmark && ' · target is an industry benchmark, not your history'}
                  </p>
                  {c.caveat && <p className="text-[11px] text-amber-600 mt-0.5">{c.caveat}</p>}
                  {c.detail && <p className="text-[11px] text-slate-400 mt-0.5">{c.detail}</p>}
                </div>
              ))}
            </div>

            {health.basis && (
              <p className="text-[11px] text-slate-400 mt-5 pt-4 border-t border-slate-100">
                {health.basis}
              </p>
            )}
          </Panel>

          {/* ═══ 2 · REVENUE TRENDS ══════════════════════════════════════ */}
          <Panel id="trends" icon={LineChart} title="Revenue trends"
            subtitle={hasTrend ? `${periodsCollected} reporting periods`
                               : 'Unlocks once you have four reports'}>
            {hasTrend ? (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={trend} margin={{ top: 4, right: 8, left: -14, bottom: 0 }}>
                  <defs>
                    <linearGradient id="biRev" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#94a3b8' }}
                    axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false}
                    tickFormatter={(v) => `$${Math.round(v / 1000)}k`} />
                  <Tooltip formatter={(v) => money(v)}
                    contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 12 }} />
                  <Area type="monotone" dataKey="revenue" stroke="#10b981"
                    strokeWidth={2} fill="url(#biRev)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              /* An empty chart reads as broken data. A progress bar reads as a
                 feature being earned, which is what's actually happening. */
              <div className="text-center py-8">
                <LineChart size={26} className="mx-auto text-slate-300 mb-3" />
                <h3 className="text-[15px] font-bold text-slate-900">
                  Upload weekly reports to unlock trend analysis
                </h3>
                <p className="text-[12px] text-slate-500 mt-1.5 max-w-sm mx-auto">
                  With four periods LiquorIQ can show you whether sales are moving
                  up or down, instead of a single snapshot.
                </p>
                <div className="max-w-[260px] mx-auto mt-6">
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1.5">
                    <span>{periodsCollected} of {TREND_MINIMUM_PERIODS} reports collected</span>
                    <span>{Math.round((periodsCollected / TREND_MINIMUM_PERIODS) * 100)}%</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 rounded-full transition-all duration-700"
                      style={{ width: `${Math.min((periodsCollected / TREND_MINIMUM_PERIODS) * 100, 100)}%` }} />
                  </div>
                </div>
                <Link to="/uploads"
                  className="inline-flex items-center gap-2 text-[12px] font-semibold px-4 py-2 rounded-xl bg-slate-900 text-white mt-6">
                  <Upload size={13} /> Upload a report
                </Link>
              </div>
            )}
          </Panel>

          {/* ═══ 3 · INVENTORY INTELLIGENCE ══════════════════════════════ */}
          <Panel id="inventory" icon={Boxes} title="Inventory intelligence"
            subtitle="Every product placed by how long its stock will last — click a band for the products"
            action={(
              <Link to="/inventory"
                className="text-[12px] font-semibold text-slate-500 hover:text-slate-900">
                Product-level view →
              </Link>
            )}>
            <div className="grid sm:grid-cols-3 gap-4 pb-5 mb-5 border-b border-slate-100">
              {[
                [valuation.inventory_label ?? 'Inventory value',
                 money(valuation.inventory_headline ?? headline.inventory_value),
                 `${summary.products?.toLocaleString()} products`],
                [valuation.frozen_label ?? 'Cash frozen',
                 money(valuation.frozen_headline ?? headline.cash_frozen),
                 `${headline.frozen_pct}% of stock`],
                ['Sell-through rate',
                 `${Math.round((summary.sell_through_rate ?? 0) * 100)}%`,
                 'units sold ÷ (sold + on hand)'],
              ].map(([label, value, sub]) => (
                <div key={label}>
                  <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wide">{label}</p>
                  <p className="text-xl font-bold text-slate-900 tabular-nums mt-0.5">{value}</p>
                  <p className="text-[11px] text-slate-400">{sub}</p>
                </div>
              ))}
            </div>

            <InventoryBands summary={summary}
              onSelect={(cls) => navigate(`/inventory?class=${cls}`)} />

            {valuation.note && (
              <p className="text-[11px] text-slate-400 mt-4 pt-4 border-t border-slate-100">
                {valuation.note}
              </p>
            )}
          </Panel>

          {/* ═══ 4 · CATEGORY INTELLIGENCE ═══════════════════════════════ */}
          <Panel id="categories" icon={PieChart} title="Category intelligence"
            subtitle="Which part of the shop is holding your money — tap a row for detail"
            action={(
              <Link to="/categories"
                className="text-[12px] font-semibold text-slate-500 hover:text-slate-900">
                Full breakdown →
              </Link>
            )}>
            <CategoryPanel categories={categories} />
            <p className="text-[11px] text-slate-400 mt-4 pt-4 border-t border-slate-100">
              {coverage.resolved_pct}% of {coverage.total?.toLocaleString()} products were
              categorised automatically. Your corrections always win and are remembered.
            </p>
          </Panel>

          {/* ═══ 5 · GROWTH OPPORTUNITIES ════════════════════════════════ */}
          <Panel id="opportunities" icon={TrendingUp} title="Growth opportunities"
            subtitle={`All ${actions.length} recommendations, ranked by money at stake × confidence`}>
            <div className="flex items-baseline gap-6 pb-5 mb-5 border-b border-slate-100 flex-wrap">
              <div>
                <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wide">
                  On the table
                </p>
                <p className="text-2xl font-bold text-slate-900 tabular-nums">
                  {money(headline.opportunity_value)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wide">
                  Confidence-adjusted
                </p>
                <p className="text-2xl font-bold text-emerald-600 tabular-nums">
                  {money(headline.opportunity_value_adjusted)}
                </p>
              </div>
            </div>

            {headline.opportunity_basis && (
              <p className="text-[11px] text-slate-400 mb-5">{headline.opportunity_basis}</p>
            )}

            <div className="space-y-3 -mx-2">
              {actions.map((a) => <ActionCard key={a.id} action={a} />)}
            </div>
            {actions.length === 0 && (
              <p className="text-sm text-slate-400 text-center py-6">
                Nothing urgent — your stock levels look balanced.
              </p>
            )}
          </Panel>

          {/* ═══ 6 · HISTORICAL PERFORMANCE ══════════════════════════════ */}
          <Panel id="history" icon={History} title="Historical performance"
            subtitle="Measured lift from campaigns you have already run">
            {campaign?.campaigns?.length ? (
              <div className="space-y-3">
                {campaign.campaigns.map((c) => (
                  <div key={c.strategy_id}
                    className="flex items-center justify-between gap-4 py-3 border-b border-slate-50 last:border-0 flex-wrap">
                    <div className="min-w-0">
                      <p className="text-[13px] font-semibold text-slate-800 truncate">{c.title}</p>
                      <p className="text-[11px] text-slate-400">{c.status ?? 'measured'}</p>
                    </div>
                    <p className={`text-lg font-bold tabular-nums ${
                      (c.revenue_lift ?? 0) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {(c.revenue_lift ?? 0) >= 0 ? '+' : ''}{money(c.revenue_lift)}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Sparkles size={24} className="mx-auto text-slate-300 mb-3" />
                <h3 className="text-[15px] font-bold text-slate-900">
                  Generate your first campaign to start measuring ROI
                </h3>
                <p className="text-[12px] text-slate-500 mt-1.5 max-w-sm mx-auto">
                  Once a campaign has run, LiquorIQ compares the weeks after it
                  against the weeks before and shows you what it actually earned.
                </p>
                <Link to="/ai"
                  className="inline-flex items-center gap-2 text-[12px] font-semibold px-4 py-2 rounded-xl bg-slate-900 text-white mt-6">
                  <Sparkles size={13} /> Generate campaign
                </Link>
              </div>
            )}
          </Panel>

          {/* ═══ 7 · BUSINESS ASSUMPTIONS ════════════════════════════════ */}
          <Panel id="assumptions" icon={Info} title="Business assumptions"
            subtitle="Everything else on this page is measured from your own report. These are not.">
            <div className="grid sm:grid-cols-2 gap-x-8 gap-y-4">
              {(bi.assumptions ?? []).map((a) => (
                <div key={a.key}>
                  <p className="text-[13px] font-semibold text-slate-800">
                    {a.label}: <span className="font-normal text-slate-600">{a.value}</span>
                  </p>
                  {a.why && <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">{a.why}</p>}
                </div>
              ))}
            </div>
          </Panel>

          {/* ═══ 8 · CONFIDENCE INDICATORS ═══════════════════════════════ */}
          <Panel id="confidence" icon={ShieldCheck} title="Confidence indicators"
            subtitle="How much weight each recommendation carries, and why">
            <div className="space-y-3">
              {opportunities.map((o) => {
                const tone = CONFIDENCE_TONE[o.confidence] ?? CONFIDENCE_TONE.low
                return (
                  <div key={o.type}
                    className="flex items-start gap-3 py-3 border-b border-slate-50 last:border-0">
                    <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${tone.dot}`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-3 flex-wrap">
                        <p className="text-[13px] font-semibold text-slate-800">{o.title}</p>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${tone.chip}`}>
                          {o.confidence} · weight {o.confidence_weight}
                        </span>
                      </div>
                      <p className="text-[12px] text-slate-500 mt-0.5">{o.confidence_reason}</p>
                      <p className="text-[11px] text-slate-400 mt-1 tabular-nums">
                        {money(o.value_score)} raw → {money(o.ranked_value)} after
                        confidence weighting
                        {o.estimated === false ? ' · measured' : ' · estimate'}
                      </p>
                      {o.allocation_note && (
                        <p className="text-[11px] text-slate-400 italic mt-0.5">{o.allocation_note}</p>
                      )}
                    </div>
                  </div>
                )
              })}
              {opportunities.length === 0 && (
                <p className="text-sm text-slate-400 text-center py-6">
                  No opportunities detected in this period.
                </p>
              )}
            </div>

            <div className="mt-5 pt-4 border-t border-slate-100 space-y-1.5">
              <p className="text-[11px] text-slate-500">
                <b>High</b> — measured directly from your own stock and sales.
              </p>
              <p className="text-[11px] text-slate-500">
                <b>Medium</b> — your figures, combined with an industry rate.
              </p>
              <p className="text-[11px] text-slate-500">
                <b>Low</b> — the pattern is real but the rate has no basis in your data yet.
              </p>
            </div>
          </Panel>
        </div>
      </div>
    </Layout>
  )
}
