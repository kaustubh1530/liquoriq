/**
 * AIStrategy.jsx — Generate AI promotion strategies + view history
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { aiApi } from '../api/client'
import Layout from '../components/Layout'
import { Sparkles, ChevronDown, ChevronUp, Megaphone, TrendingUp, TrendingDown } from 'lucide-react'

// ── Phase 12: campaign ROI section (lazy-loaded when a card is expanded) ──────
function CampaignPerformance({ strategyId }) {
  const [perf, setPerf] = useState(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    (async () => {
      try {
        const { data } = await aiApi.performance(strategyId)
        setPerf(data)
      } catch {
        setFailed(true)
      }
    })()
  }, [strategyId])

  if (failed) return null
  if (!perf) return <p className="text-xs text-gray-400">Loading campaign performance…</p>

  if (perf.status === 'no_baseline') {
    return (
      <p className="text-xs text-gray-400">
        Not enough sales history before this campaign to measure lift. Upload more
        reports covering earlier dates, or check back on your next campaign.
      </p>
    )
  }

  const up = (perf.total_units_lift_pct ?? 0) >= 0
  const Arrow = up ? TrendingUp : TrendingDown

  return (
    <div>
      {/* Status + headline numbers */}
      <div className="flex items-center gap-3 flex-wrap mb-3">
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
          perf.status === 'complete' ? 'bg-gray-100 text-gray-600' : 'bg-blue-50 text-blue-600'
        }`}>
          {perf.status === 'complete'
            ? 'Campaign complete'
            : `Measuring — day ${perf.days_elapsed} of ${perf.campaign_window_days}`}
        </span>
        {perf.status === 'measuring' && perf.days_elapsed <= 3 && (
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-50 text-amber-600">
            early estimate — few days of data
          </span>
        )}
        {perf.total_units_lift_pct !== null && (
          <span className={`flex items-center gap-1.5 text-sm font-bold ${up ? 'text-green-600' : 'text-red-500'}`}>
            <Arrow size={16} />
            {perf.total_units_lift_pct > 0 ? '+' : ''}{perf.total_units_lift_pct}% units
          </span>
        )}
        {perf.total_revenue_lift !== null && (
          <span className={`text-sm font-bold ${perf.total_revenue_lift >= 0 ? 'text-green-600' : 'text-red-500'}`}>
            {perf.total_revenue_lift >= 0 ? '+' : '−'}${Math.abs(perf.total_revenue_lift).toFixed(2)} revenue
          </span>
        )}
      </div>

      {/* Per-product rows */}
      <div className="space-y-1.5">
        {perf.products.map((p) => (
          <div key={p.product_name} className="flex items-center justify-between text-xs bg-gray-50 rounded-lg px-3 py-2">
            <span className="text-gray-700 truncate mr-3">{p.product_name}</span>
            <span className="flex items-center gap-3 shrink-0">
              <span className="text-gray-400">
                {p.baseline_weekly_units}/wk → {p.campaign_weekly_units}/wk
              </span>
              {p.units_lift_pct !== null ? (
                <span className={`font-semibold ${p.units_lift_pct >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                  {p.units_lift_pct > 0 ? '+' : ''}{p.units_lift_pct}%
                </span>
              ) : (
                <span className="text-gray-300">no baseline</span>
              )}
            </span>
          </div>
        ))}
      </div>

      <p className="text-[10px] text-gray-300 mt-2">
        Weekly sales rate during the campaign vs the {perf.baseline_window_days}-day baseline
        before it. Updates as you upload new reports.
      </p>
    </div>
  )
}

function StrategyCard({ s, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      {/* Header — always visible */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors"
      >
        <div className="text-left">
          <p className="font-semibold text-gray-900">{s.strategy_title}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {new Date(s.created_at).toLocaleString()} · {s.model_used}
          </p>
        </div>
        {open ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
      </button>

      {/* Expanded detail */}
      {open && (
        <div className="px-6 pb-6 space-y-5 border-t border-gray-100 pt-5">
          <Section title="Products to promote">
            <div className="flex flex-wrap gap-2">
              {s.products_to_promote.map((p, i) => (
                <span key={i} className="bg-brand-50 text-brand-700 text-xs font-medium px-3 py-1 rounded-full">{p}</span>
              ))}
            </div>
          </Section>

          <Section title="Why">
            <p className="text-sm text-gray-700">{s.reason}</p>
          </Section>

          <Section title="Target customer">
            <p className="text-sm text-gray-700">{s.target_customer_segment}</p>
          </Section>

          <Section title="Recommended offer">
            <p className="text-sm font-medium text-gray-900 bg-green-50 p-3 rounded-xl">{s.recommended_offer}</p>
          </Section>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <CopyBox label="📱 SMS" text={s.sms_copy} />
            <CopyBox label="✉️ Email subject" text={s.email_subject} />
            <CopyBox label="📸 Social caption" text={s.social_caption} />
          </div>

          <Section title="Email body">
            <p className="text-sm text-gray-700 bg-gray-50 p-4 rounded-xl">{s.email_body}</p>
          </Section>

          <Section title="Expected impact">
            <p className="text-sm text-gray-700">{s.expected_impact}</p>
          </Section>

          {/* Phase 12 — measured campaign ROI (the proof) */}
          <Section title="Campaign performance">
            <CampaignPerformance strategyId={s.id} />
          </Section>

          {/* Phase 10 — jump to Ad Creative studio with this strategy pre-selected */}
          <Link
            to={`/creative?strategy=${s.id}`}
            className="inline-flex items-center gap-2 bg-brand-50 hover:bg-brand-100 text-brand-600 font-semibold px-4 py-2.5 rounded-xl text-sm transition-colors"
          >
            <Megaphone size={15} />
            Create ad creative →
          </Link>
        </div>
      )}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div>
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">{title}</p>
      {children}
    </div>
  )
}

function CopyBox({ label, text }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div className="bg-gray-50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-gray-500">{label}</p>
        <button onClick={copy} className="text-xs text-brand-500 hover:underline">{copied ? 'Copied!' : 'Copy'}</button>
      </div>
      <p className="text-sm text-gray-700 leading-relaxed">{text}</p>
    </div>
  )
}

export default function AIStrategy() {
  const [strategies, setStrategies] = useState([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [limit, setLimit] = useState(5)

  const load = async () => {
    try {
      const { data } = await aiApi.list()
      setStrategies(data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleGenerate = async () => {
    setError('')
    setGenerating(true)
    try {
      await aiApi.generate(limit)
      await load()
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Failed to generate strategy.')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <Layout>
      <div className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">AI Strategy</h1>
        <p className="text-sm text-gray-500 mb-8">
          Generate AI-powered promotion campaigns based on your slowest-selling products
        </p>

        {/* Generate panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-8">
          <div className="flex items-center gap-3 mb-4">
            <Sparkles size={20} className="text-brand-500" />
            <h2 className="text-sm font-semibold text-gray-700">Generate new strategy</h2>
          </div>
          {error && <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{error}</div>}
          <div className="flex items-center gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Products to analyze</label>
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                {[3, 5, 8, 10].map((n) => <option key={n} value={n}>{n} slowest products</option>)}
              </select>
            </div>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-2 bg-brand-500 hover:bg-brand-600 text-white font-semibold px-5 py-2.5 rounded-xl text-sm transition-colors disabled:opacity-60 mt-4"
            >
              <Sparkles size={16} />
              {generating ? 'Generating… (5-10s)' : 'Generate strategy'}
            </button>
          </div>
        </div>

        {/* Strategy history */}
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Past strategies</h2>
        {loading ? (
          <p className="text-gray-400 text-sm">Loading…</p>
        ) : strategies.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center">
            <p className="text-3xl mb-3">🤖</p>
            <p className="text-gray-600 font-medium">No strategies yet</p>
            <p className="text-gray-400 text-sm mt-1">Click Generate above to create your first promotion campaign.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {strategies.map((s, i) => (
              <StrategyCard key={s.id} s={s} defaultOpen={i === 0} />
            ))}
          </div>
        )}
      </div>
    </Layout>
  )
}
