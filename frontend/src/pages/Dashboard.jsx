/**
 * Dashboard.jsx — PHASE 22.5
 *
 * THIS PAGE ANSWERS ONE QUESTION: "what should I do today to make more money?"
 *
 * Five sections, in the order the owner needs them:
 *   1. Executive hero    — the number, and the one button
 *   2. AI Business Coach — biggest problem, why it matters, what to do
 *   3. Business health   — am I OK?
 *   4. Top 3 priorities  — the work
 *   5. Quick snapshot    — the four figures worth glancing at
 *
 * EVERYTHING ANALYTICAL MOVED TO /intelligence. Revenue trend, category
 * ranking, the inventory distribution, growth opportunities, assumptions and
 * confidence detail are all still there, in a workspace built for exploring
 * rather than deciding. Nothing was deleted.
 *
 * The reason for the split: a dashboard that is also an analytics tool is
 * neither. Deciding and exploring are different modes — one takes thirty
 * seconds standing at the till, the other takes twenty minutes at a desk — and
 * a page that serves both makes the owner do the sorting himself.
 *
 * NO CALCULATION HAPPENS HERE. Every figure is rendered from the deterministic
 * payload; summary.js selects and phrases values already in it.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight, Sparkles, ListChecks, Upload, Activity, Snowflake, Boxes,
  PackageX, BarChart3, MessageSquareQuote,
} from 'lucide-react'
import { intelligenceApi } from '../api/client'
import Layout from '../components/Layout'
import { useAuth } from '../context/AuthContext'
import ActionCard from './dashboard/ActionCard'
import MarginPrompt from './dashboard/MarginPrompt'
import {
  greeting, executiveSummary, reasons, opportunityHeadline, topPriorities,
  coach, money,
} from './dashboard/summary'

function Card({ children, className = '' }) {
  return (
    <section className={`bg-white rounded-3xl ring-1 ring-slate-200/70 ${className}`}>
      {children}
    </section>
  )
}

/** A snapshot figure. Four of them, and only four — see section 5. */
function Snapshot({ icon: Icon, label, value, sub, tone = 'neutral' }) {
  const tones = {
    neutral: 'text-slate-900', good: 'text-emerald-600',
    warn: 'text-amber-600', bad: 'text-red-600',
  }
  return (
    <Card className="p-5">
      <div className="flex items-center gap-1.5 mb-2">
        <Icon size={13} className="text-slate-400 shrink-0" />
        <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wide truncate">
          {label}
        </p>
      </div>
      <p className={`text-2xl font-bold tabular-nums ${tones[tone]}`}>{value}</p>
      {sub && <p className="text-[11px] text-slate-400 mt-0.5 truncate">{sub}</p>}
    </Card>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const [bi, setBi] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const { data } = await intelligenceApi.all()
      setBi(data)
      setError('')
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message
        ?? 'Could not load your business intelligence.')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) {
    return (
      <Layout>
        <div className="max-w-4xl mx-auto space-y-5 animate-pulse">
          <div className="h-52 bg-slate-100 rounded-3xl" />
          <div className="h-32 bg-slate-100 rounded-3xl" />
          <div className="h-28 bg-slate-100 rounded-3xl" />
        </div>
      </Layout>
    )
  }

  if (error) {
    return (
      <Layout>
        <div className="max-w-lg mx-auto bg-red-50 ring-1 ring-red-100 rounded-3xl p-6 text-center">
          <p className="text-sm text-red-700">{error}</p>
          <button onClick={load}
            className="mt-4 text-xs font-semibold px-4 py-2 rounded-xl bg-red-600 text-white">
            Try again
          </button>
        </div>
      </Layout>
    )
  }

  if (bi?.empty) {
    return (
      <Layout>
        <div className="max-w-lg mx-auto text-center py-20">
          <Upload size={30} className="mx-auto text-slate-300 mb-4" />
          <h1 className="text-xl font-bold text-slate-900">Upload your first report</h1>
          <p className="text-sm text-slate-500 mt-2 mb-6">
            Export a sales summary from your POS and LiquorIQ will tell you what
            to reorder, what to clear, and what to promote.
          </p>
          <Link to="/uploads"
            className="inline-flex items-center gap-2 text-sm font-semibold px-5 py-2.5 rounded-2xl bg-slate-900 text-white">
            Upload a report <ArrowRight size={15} />
          </Link>
        </div>
      </Layout>
    )
  }

  const { headline, business_health: health, actions = [], summary = {},
          valuation = {} } = bi

  const opportunity = opportunityHeadline(bi)
  const priorities = topPriorities(bi, 3)
  const why = reasons(bi)
  const brief = executiveSummary(bi)
  const advice = coach(bi)
  const firstName = (user?.full_name ?? '').trim().split(' ')[0] || 'there'

  const RING = health.score >= 60 ? '#10b981' : health.score >= 40 ? '#f59e0b' : '#ef4444'
  const outOfStock = summary.by_class?.sold_out?.count ?? 0

  return (
    <Layout>
      <div className="max-w-4xl mx-auto space-y-5 pb-12">

        {/* ═══ 1 · EXECUTIVE HERO ══════════════════════════════════════════ */}
        <Card className="p-7 sm:p-9 bg-gradient-to-br from-slate-900 to-slate-800 ring-0">
          <div className="flex items-start justify-between gap-6 flex-wrap">
            <p className="text-[13px] text-slate-300">{greeting()}, {firstName} 👋</p>

            {/* Health lives in the hero too, as a chip — the owner shouldn't
                have to scroll to find out whether anything is on fire. */}
            <span className="inline-flex items-center gap-2 text-[12px] font-semibold px-3 py-1.5 rounded-full bg-white/10 ring-1 ring-white/15">
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: RING }} />
              <span className="text-white">{Math.round(health.score)}/100</span>
              <span className="text-slate-300 font-medium capitalize">{health.band}</span>
            </span>
          </div>

          <p className="text-[13px] text-slate-400 mt-6">
            Acting on this week&rsquo;s recommendations is worth about
          </p>
          <p className="text-5xl sm:text-6xl font-bold text-white tracking-tight tabular-nums mt-1">
            +{money(opportunity.value)}
          </p>

          {why.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-5">
              {why.map((r) => (
                <span key={r.text}
                  className="text-[12px] font-medium px-3 py-1.5 rounded-full bg-white/10 text-slate-100 ring-1 ring-white/10">
                  {r.text}
                </span>
              ))}
            </div>
          )}

          <div className="flex items-center gap-3 mt-7 flex-wrap">
            <Link to="/ai"
              className="inline-flex items-center gap-2 text-[13px] font-semibold px-5 py-2.5 rounded-2xl bg-white text-slate-900 hover:bg-slate-100 transition-colors">
              <Sparkles size={15} /> Generate campaign
            </Link>
            <a href="#priorities"
              className="inline-flex items-center gap-2 text-[13px] font-semibold px-5 py-2.5 rounded-2xl bg-white/10 text-white ring-1 ring-white/15 hover:bg-white/15 transition-colors">
              <ListChecks size={15} /> View action plan
            </a>
          </div>

          {brief && (
            <p className="text-[13px] leading-relaxed text-slate-300 mt-7 pt-6 border-t border-white/10 max-w-3xl">
              {brief}
            </p>
          )}
        </Card>

        <MarginPrompt valuation={valuation} onSaved={load} />

        {/* ═══ 2 · AI BUSINESS COACH ═══════════════════════════════════════ */}
        {advice && (
          <Card className="p-6 ring-brand-200/60 bg-gradient-to-br from-brand-50/40 to-white">
            <div className="flex items-start gap-4">
              <span className="w-9 h-9 rounded-2xl bg-brand-500/10 flex items-center justify-center shrink-0">
                <MessageSquareQuote size={17} className="text-brand-600" />
              </span>

              <div className="min-w-0 flex-1 space-y-3">
                <p className="text-[11px] font-semibold text-brand-700 uppercase tracking-wide">
                  Your business coach
                </p>

                <p className="text-[15px] font-semibold text-slate-900 leading-snug">
                  {advice.problem}.
                </p>
                <p className="text-[13px] text-slate-600 leading-relaxed">
                  {advice.matters}
                </p>
                <p className="text-[13px] text-slate-800 leading-relaxed">
                  <span className="font-semibold">What to do: </span>
                  {advice.action}
                  {advice.timeline && (
                    <span className="text-slate-500"> — {advice.timeline.toLowerCase()}</span>
                  )}
                  <span className="text-slate-500">
                    . Worth about <span className="font-semibold text-slate-800">{advice.impact}</span>,
                    at {advice.confidence} confidence.
                  </span>
                </p>

                <a href="#priorities"
                  className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-brand-700 hover:text-brand-800">
                  See the full plan <ArrowRight size={13} />
                </a>
              </div>
            </div>
          </Card>
        )}

        {/* ═══ 3 · BUSINESS HEALTH ═════════════════════════════════════════ */}
        <Card className="p-6">
          <div className="flex items-center gap-6 flex-wrap">
            <div className="relative w-[88px] h-[88px] shrink-0">
              <svg viewBox="0 0 100 100" className="w-[88px] h-[88px] -rotate-90">
                <circle cx="50" cy="50" r="42" fill="none" stroke="#f1f5f9" strokeWidth="9" />
                <circle cx="50" cy="50" r="42" fill="none" stroke={RING} strokeWidth="9"
                  strokeLinecap="round" strokeDasharray={`${(health.score / 100) * 264} 264`} />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-2xl font-bold text-slate-900 tabular-nums leading-none">
                  {Math.round(health.score)}
                </span>
                <span className="text-[10px] text-slate-400">/ 100</span>
              </div>
            </div>

            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">
                Business health
              </p>
              <p className="text-[15px] font-bold text-slate-900 capitalize">{health.band}</p>
              <p className="text-[13px] text-slate-500 mt-1">{health.verdict}</p>
            </div>

            <Link to="/intelligence"
              className="text-[12px] font-semibold text-slate-500 hover:text-slate-900 shrink-0">
              See what drives this →
            </Link>
          </div>
        </Card>

        {/* ═══ 4 · TOP 3 PRIORITIES ════════════════════════════════════════ */}
        <section id="priorities" className="scroll-mt-6">
          <div className="flex items-end justify-between gap-4 flex-wrap mb-4">
            <div>
              <h2 className="text-[15px] font-bold text-slate-900">Today’s top 3 priorities</h2>
              <p className="text-[12px] text-slate-500 mt-0.5">
                Ranked by money at stake × how confident we are in the number
              </p>
            </div>
            {actions.length > 3 && (
              <Link to="/intelligence#opportunities"
                className="text-[12px] font-semibold text-slate-500 hover:text-slate-900">
                All {actions.length} recommendations →
              </Link>
            )}
          </div>

          {priorities.length === 0 ? (
            <Card className="p-10 text-center">
              <p className="text-sm text-slate-500">
                Nothing urgent — your stock levels look balanced.
              </p>
            </Card>
          ) : (
            <div className="space-y-3">
              {priorities.map((a) => <ActionCard key={a.id} action={a} />)}
            </div>
          )}
        </section>

        {/* ═══ 5 · QUICK SNAPSHOT — four figures, nothing else ═════════════ */}
        <div>
          <div className="flex items-end justify-between gap-4 mb-3">
            <h2 className="text-[15px] font-bold text-slate-900">Quick snapshot</h2>
            <Link to="/intelligence"
              className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-slate-500 hover:text-slate-900">
              <BarChart3 size={13} /> Business Intelligence
            </Link>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Snapshot icon={Boxes} label={valuation.inventory_label ?? 'Inventory value'}
              value={money(valuation.inventory_headline ?? headline.inventory_value)}
              sub={`${summary.products?.toLocaleString()} products`} />
            <Snapshot icon={Snowflake} label={valuation.frozen_label ?? 'Cash frozen'}
              value={money(valuation.frozen_headline ?? headline.cash_frozen)}
              sub={`${headline.frozen_pct}% of stock`}
              tone={headline.frozen_pct >= 50 ? 'bad' : 'warn'} />
            <Snapshot icon={Activity} label="Inventory turnover"
              value={summary.turnover ? `${summary.turnover}×` : '—'}
              sub="healthy is 4–6× a year"
              tone={summary.turnover >= 4 ? 'good' : 'warn'} />
            <Snapshot icon={PackageX} label="Products out of stock"
              value={outOfStock.toLocaleString()}
              sub="losing sales today"
              tone={outOfStock > 0 ? 'bad' : 'good'} />
          </div>
        </div>
      </div>
    </Layout>
  )
}
