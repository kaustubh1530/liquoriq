/**
 * AIStrategy.jsx — Generate AI promotion strategies + view history
 */

import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { aiApi, dealApi, customerApi, campaignApi } from '../api/client'
import Layout from '../components/Layout'
import FromActionBanner from '../components/FromActionBanner'
import { Sparkles, ChevronDown, ChevronUp, Megaphone, TrendingUp, TrendingDown, Tag, Trash2, Users, AlertTriangle, Send, MessageSquare, Mail } from 'lucide-react'

// ── Send campaign (Phase 21): preview → confirm → send, to opted-in customers ──
function SendCampaign({ strategyId }) {
  const [channel, setChannel] = useState(null)   // 'sms' | 'email' | null
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)

  const openChannel = async (ch) => {
    setChannel(ch); setResult(null); setPreview(null); setBusy(true)
    try { setPreview((await campaignApi.preview(strategyId, ch)).data) }
    catch (e) { setPreview({ error: e.response?.data?.detail ?? 'Preview failed' }) }
    finally { setBusy(false) }
  }

  const send = async () => {
    const live = preview?.live
    const msg = live
      ? `Send this ${channel.toUpperCase()} to ${preview.recipient_count} opted-in customers now? This sends real messages.`
      : `Run a DRY RUN for ${preview.recipient_count} recipients? (Twilio not configured — nothing is actually sent.)`
    if (!window.confirm(msg)) return
    setBusy(true)
    try { setResult((await campaignApi.send(strategyId, channel)).data) }
    catch (e) { setResult({ error: e.response?.data?.detail ?? 'Send failed' }) }
    finally { setBusy(false) }
  }

  return (
    <div className="border-t border-gray-100 pt-4">
      <div className="flex items-center gap-2 mb-2">
        <Send size={14} className="text-brand-500" />
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Send to customers</span>
      </div>
      <div className="flex gap-2 mb-2">
        <button onClick={() => openChannel('sms')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border ${channel === 'sms' ? 'bg-brand-500 text-white border-brand-500' : 'bg-white text-gray-600 border-gray-200'}`}>
          <MessageSquare size={12} /> SMS
        </button>
        <button onClick={() => openChannel('email')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border ${channel === 'email' ? 'bg-brand-500 text-white border-brand-500' : 'bg-white text-gray-600 border-gray-200'}`}>
          <Mail size={12} /> Email
        </button>
      </div>

      {busy && !result && <p className="text-xs text-gray-400">Working…</p>}

      {preview && !result && !preview.error && (
        <div className="bg-gray-50 rounded-xl p-3">
          <p className="text-sm text-gray-700">
            <b>{preview.recipient_count}</b> opted-in {channel} recipient{preview.recipient_count !== 1 ? 's' : ''}
            {preview.target_segment && <> in <b>{preview.target_segment}</b></>}
          </p>
          {preview.warnings?.map((w, i) => (
            <p key={i} className="flex items-center gap-1.5 text-[11px] text-amber-600 mt-1"><AlertTriangle size={11} /> {w}</p>
          ))}
          <p className="text-[11px] text-gray-400 mt-2 whitespace-pre-wrap bg-white rounded-lg p-2 border border-gray-100">{preview.sample_message}</p>
          <button onClick={send} disabled={busy || preview.recipient_count === 0}
            className="mt-2 bg-brand-500 hover:bg-brand-600 text-white font-semibold px-4 py-1.5 rounded-lg text-xs disabled:opacity-60">
            {preview.live ? `Send to ${preview.recipient_count}` : `Dry run (${preview.recipient_count})`}
          </button>
        </div>
      )}
      {preview?.error && <p className="text-xs text-red-500">{preview.error}</p>}

      {result && !result.error && (
        <div className="bg-green-50 rounded-xl p-3 text-sm text-green-700">
          {result.status === 'dry_run' ? 'Dry run complete' : 'Campaign sent'} — {result.sent_count} {result.status === 'dry_run' ? 'simulated' : 'sent'}
          {result.failed_count > 0 && `, ${result.failed_count} failed`}.
        </div>
      )}
      {result?.error && <p className="text-xs text-red-500">{result.error}</p>}
    </div>
  )
}

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

function StrategyCard({ s: listItem, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  const [full, setFull] = useState(null)

  // The /ai/strategies LIST is lightweight (no sms_copy/email_subject/etc.).
  // Fetch the FULL strategy on first expand so the copy fields aren't undefined.
  useEffect(() => {
    if (open && !full) {
      aiApi.get(listItem.id).then(({ data }) => setFull(data)).catch(() => {})
    }
  }, [open, full, listItem.id])

  const s = full ?? listItem   // render from full detail once loaded

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      {/* Header — always visible */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors"
      >
        <div className="text-left">
          <div className="flex items-center gap-2 flex-wrap">
            {s.occasion && (
              <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full ${
                s.strategy_type === 'deal' ? 'bg-green-100 text-green-700'
                : s.strategy_type === 'holiday' ? 'bg-purple-100 text-purple-700'
                : 'bg-gray-100 text-gray-600'
              }`}>{s.occasion}</span>
            )}
            {s.target_segment && (
              <span className="text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                🎯 {s.target_segment}
              </span>
            )}
            <p className="font-semibold text-gray-900">{s.strategy_title}</p>
          </div>
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

          {/* Phase 15: offline-first execution + online plan */}
          {s.offline_plan && (
            <Section title="🏪 In-store plan (offline)">
              <p className="text-sm text-gray-700 bg-amber-50 p-3 rounded-xl whitespace-pre-wrap">{s.offline_plan}</p>
            </Section>
          )}
          {s.online_plan && (
            <Section title="🌐 Online plan">
              <p className="text-sm text-gray-700 bg-blue-50 p-3 rounded-xl whitespace-pre-wrap">{s.online_plan}</p>
            </Section>
          )}
          {s.vivino_listing && (
            <CopyBox label="🍷 Vivino / online listing" text={s.vivino_listing} />
          )}

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

          {/* Phase 21 — send this campaign to opted-in customers */}
          <SendCampaign strategyId={s.id} />
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div>
      <p className="text-sm font-bold text-gray-800">{value}</p>
      <p className="text-[10px] text-gray-400 uppercase tracking-wide">{label}</p>
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
  const hasText = typeof text === 'string' && text.trim().length > 0
  const copy = () => {
    if (!hasText) return
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div className="bg-gray-50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-gray-500">{label}</p>
        <button onClick={copy} disabled={!hasText}
          className="text-xs text-brand-500 hover:underline disabled:text-gray-300 disabled:no-underline">
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <p className="text-sm text-gray-700 leading-relaxed">{hasText ? text : '…'}</p>
    </div>
  )
}

// ── Deal Buys manager (Phase 15) ──────────────────────────────────────────────
function DealBuys({ deals, onChange }) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ product_name: '', cost_price: '', normal_price: '', quantity: '' })
  const [saving, setSaving] = useState(false)

  const add = async () => {
    if (!form.product_name.trim() || !form.cost_price) return
    setSaving(true)
    try {
      await dealApi.create({
        product_name: form.product_name.trim(),
        cost_price: Number(form.cost_price),
        normal_price: form.normal_price ? Number(form.normal_price) : null,
        quantity: form.quantity ? Number(form.quantity) : null,
      })
      setForm({ product_name: '', cost_price: '', normal_price: '', quantity: '' })
      onChange()
    } finally { setSaving(false) }
  }
  const remove = async (id) => { await dealApi.remove(id); onChange() }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Tag size={18} className="text-green-500" />
          <h2 className="text-sm font-semibold text-gray-700">
            Deal buys <span className="text-gray-400 font-normal">({deals.length})</span>
          </h2>
        </div>
        <span className="text-xs text-brand-500">{open ? 'Hide' : 'Manage'}</span>
      </button>
      <p className="text-xs text-gray-400 mt-1">
        Closeout stock you bought cheap — the AI builds high-margin campaigns to move it.
      </p>

      {open && (
        <div className="mt-4">
          <div className="flex gap-2 flex-wrap mb-3">
            <input type="text" placeholder="Product" value={form.product_name}
              onChange={(e) => setForm({ ...form, product_name: e.target.value })}
              className="flex-1 min-w-40 border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            <input type="number" placeholder="Cost $" value={form.cost_price} min="0" step="0.01"
              onChange={(e) => setForm({ ...form, cost_price: e.target.value })}
              className="w-24 border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            <input type="number" placeholder="Normal $" value={form.normal_price} min="0" step="0.01"
              onChange={(e) => setForm({ ...form, normal_price: e.target.value })}
              className="w-24 border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            <input type="number" placeholder="Qty" value={form.quantity} min="0"
              onChange={(e) => setForm({ ...form, quantity: e.target.value })}
              className="w-20 border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            <button onClick={add} disabled={saving || !form.product_name.trim() || !form.cost_price}
              className="bg-green-500 hover:bg-green-600 text-white font-semibold px-4 py-2 rounded-xl text-sm disabled:opacity-60">
              Add
            </button>
          </div>
          {deals.length > 0 && (
            <div className="space-y-1.5">
              {deals.map((d) => (
                <div key={d.id} className="flex items-center justify-between text-xs bg-gray-50 rounded-lg px-3 py-2">
                  <span className="text-gray-700">
                    {d.product_name} · cost ${Number(d.cost_price).toFixed(2)}
                    {d.normal_price && <span className="text-green-600"> · sells ${Number(d.normal_price).toFixed(2)}</span>}
                    {d.quantity && <span className="text-gray-400"> · {Number(d.quantity)} units</span>}
                  </span>
                  <button onClick={() => remove(d.id)} className="text-gray-300 hover:text-red-400"><Trash2 size={13} /></button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function AIStrategy() {
  const [strategies, setStrategies] = useState([])
  const [deals, setDeals] = useState([])
  const [holidays, setHolidays] = useState([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [focus, setFocus] = useState('auto')     // 'auto' | 'all' | deal id
  const [occasion, setOccasion] = useState('')   // '' = auto; holiday name; or custom
  const [brief, setBrief] = useState('')         // free-text instructions
  const [segments, setSegments] = useState([])   // segment summary buckets
  const [targetSegment, setTargetSegment] = useState('')  // '' = all customers
  const [audience, setAudience] = useState(null) // aggregate preview for selected segment
  const [audienceLoading, setAudienceLoading] = useState(false)
  const [incoming, setIncoming] = useState(null)  // the dashboard action we came from

  /**
   * Arriving from a dashboard recommendation: pre-fill the form from it.
   *
   * The ref guards against re-applying on every render — without it, typing in
   * the brief would be overwritten on the next state change, which reads as
   * the page fighting you. The brief is only pre-filled when EMPTY, so
   * anything already typed always wins.
   */
  const location = useLocation()
  const applied = useRef(false)

  useEffect(() => {
    const from = location.state?.fromAction
    if (!from || applied.current) return
    applied.current = true
    setIncoming(from)

    const names = (from.products ?? []).slice(0, 15)
    const lines = [
      from.suggestion,
      names.length ? `Focus on these products: ${names.join(', ')}` : '',
    ].filter(Boolean)
    setBrief((current) => current || lines.join('\n'))

    if (from.type === 'seasonal' && from.evidence?.holiday) {
      setOccasion(from.evidence.holiday)
    }
    if (from.type === 'winback') {
      const segment = Object.keys(from.evidence?.segments ?? {})[0]
      if (segment) setTargetSegment(segment)
    }
  }, [location.state])

  const load = async () => {
    try {
      const [s, d, h] = await Promise.all([aiApi.list(), dealApi.list(), aiApi.holidays()])
      setStrategies(s.data)
      setDeals(d.data)
      setHolidays(h.data)
      customerApi.segments().then((r) => setSegments(r.data.segments || [])).catch(() => {})
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  // Load the aggregate audience preview when a target segment is chosen
  useEffect(() => {
    if (!targetSegment) { setAudience(null); return }
    setAudienceLoading(true)
    customerApi.audience(targetSegment)
      .then((r) => setAudience(r.data))
      .catch(() => setAudience(null))
      .finally(() => setAudienceLoading(false))
  }, [targetSegment])
  const loadDeals = async () => { try { setDeals((await dealApi.list()).data) } catch { /* noop */ } }

  useEffect(() => { load() }, [])

  const handleGenerate = async () => {
    setError('')
    setGenerating(true)
    try {
      const dealIds =
        focus === 'auto' ? null
        : focus === 'all' ? deals.map((d) => d.id)
        : [focus]
      await aiApi.generate({
        dealIds,
        occasion: occasion.trim() || null,
        instructions: brief.trim() || null,
        targetSegment: targetSegment || null,
      })
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
        <p className="text-sm text-gray-500 mb-6">
          Growth campaigns built around upcoming US holidays, your deal buys, and what already sells —
          with in-store and online plans
        </p>

        <FromActionBanner action={incoming} onDismiss={() => setIncoming(null)} />

        <DealBuys deals={deals} onChange={loadDeals} />

        {/* Generate panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-8">
          <div className="flex items-center gap-3 mb-4">
            <Sparkles size={20} className="text-brand-500" />
            <h2 className="text-sm font-semibold text-gray-700">Generate new campaign</h2>
          </div>
          {error && <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{error}</div>}
          <div className="space-y-4">
            <div className="flex gap-4 flex-wrap">
              <div className="flex-1 min-w-56">
                <label className="block text-xs text-gray-500 mb-1">Build the campaign around…</label>
                <select
                  value={focus}
                  onChange={(e) => setFocus(e.target.value)}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option value="auto">Auto — best opportunity</option>
                  {deals.length > 1 && <option value="all">All deal buys — bundled closeout campaign (BOGO / mixed case)</option>}
                  {deals.length > 0 && <optgroup label="A single deal buy">
                    {deals.map((d) => <option key={d.id} value={d.id}>Deal: {d.product_name}</option>)}
                  </optgroup>}
                </select>
              </div>
              <div className="flex-1 min-w-56">
                <label className="block text-xs text-gray-500 mb-1">Event / occasion <span className="text-gray-300">(optional)</span></label>
                <input
                  list="occasion-list"
                  value={occasion}
                  onChange={(e) => setOccasion(e.target.value)}
                  placeholder="Auto · or pick / type an event"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                <datalist id="occasion-list">
                  {holidays.map((h) => <option key={h.key} value={h.name}>{`${h.name} (${h.days_away}d)`}</option>)}
                </datalist>
              </div>
            </div>

            {/* Phase 20: target a customer segment */}
            {segments.length > 0 && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">
                  Target audience <span className="text-gray-300">(optional — a customer segment)</span>
                </label>
                <select
                  value={targetSegment}
                  onChange={(e) => setTargetSegment(e.target.value)}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option value="">All customers (no specific segment)</option>
                  {segments.filter((s) => s.count > 0).map((s) => (
                    <option key={s.segment} value={s.segment}>{s.segment} · {s.count} customers</option>
                  ))}
                </select>

                {/* Audience preview */}
                {targetSegment && (
                  audienceLoading ? (
                    <p className="text-xs text-gray-400 mt-2">Loading audience…</p>
                  ) : audience ? (
                    <div className="mt-2 p-3 rounded-xl bg-gray-50 border border-gray-100">
                      <div className="flex items-center gap-2 mb-2">
                        <Users size={14} className="text-brand-500" />
                        <span className="text-xs font-semibold text-gray-700">{audience.segment} audience</span>
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center">
                        <Stat label="Customers" value={audience.size} />
                        <Stat label="Avg spend" value={`$${Math.round(audience.avg_spend)}`} />
                        <Stat label="Avg visits" value={audience.avg_visits} />
                        <Stat label="SMS ✓" value={audience.sms_opted_in} />
                        <Stat label="Email ✓" value={audience.email_opted_in} />
                      </div>
                      {audience.warnings?.length > 0 && (
                        <div className="mt-2 space-y-1">
                          {audience.warnings.map((w, i) => (
                            <p key={i} className="flex items-center gap-1.5 text-[11px] text-amber-600">
                              <AlertTriangle size={11} /> {w}
                            </p>
                          ))}
                        </div>
                      )}
                      <p className="text-[10px] text-gray-400 mt-2">
                        Only these aggregate numbers are sent to the AI — never customer names, emails, or phone numbers.
                      </p>
                    </div>
                  ) : null
                )}
              </div>
            )}

            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Anything specific? <span className="text-gray-300">(optional brief — new release, a set offer/price, target audience…)</span>
              </label>
              <textarea
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                rows={2}
                placeholder="e.g. We just got the new Blanton's release — push it. Run a BOGO on the closeout wines at $12. Target wedding-season buyers."
                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
              />
            </div>

            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-2 bg-brand-500 hover:bg-brand-600 text-white font-semibold px-5 py-2.5 rounded-xl text-sm transition-colors disabled:opacity-60"
            >
              <Sparkles size={16} />
              {generating ? 'Generating… (5-10s)' : 'Generate campaign'}
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
