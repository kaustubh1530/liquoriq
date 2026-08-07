/**
 * CampaignWorkspace.jsx — PHASE 23.7: a campaign as a project.
 *
 * The tools were never the problem. The Ad Creator, Label Studio, the copy and
 * the ROI report all worked; what was missing was any sense of WHERE YOU ARE.
 * The owner had to hold the pipeline in his head and navigate it from a
 * sidebar, which is why it felt like six products rather than one.
 *
 * This page is the spine: one campaign, its progress, its schedule, and a way
 * into each tool that carries the campaign with it.
 *
 * PROGRESS IS COMPUTED SERVER-SIDE from the real assets, never stored as flags
 * — see services/campaign_workspace.py. This page renders what it is told and
 * derives nothing, so it can never disagree with the tools that made the work.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft, ArrowRight, Check, Clock, Loader2, Sparkles, Calendar,
  Copy as CopyIcon, CheckCircle2, Package,
} from 'lucide-react'
import { workspaceApi } from '../api/client'
import Layout from '../components/Layout'
import CampaignAdSection from './campaign/CampaignAdSection'
import CampaignLabelsSection from './campaign/CampaignLabelsSection'

/**
 * PHASE 23.8 — steps that live ON this page rather than behind a link.
 *
 * The server still owns the pipeline and still hands every step its route; this
 * map only says which of those routes the workspace now renders itself. A step
 * listed here scrolls; anything else keeps linking out exactly as before, so
 * adding a step server-side never leaves a dead square on the rail.
 */
const EMBEDDED = { ad: 'section-ad', labels: 'section-labels' }

const STATUS_TONE = {
  draft: 'bg-slate-100 text-slate-600',
  ready: 'bg-blue-50 text-blue-700',
  scheduled: 'bg-amber-50 text-amber-700',
  launched: 'bg-emerald-50 text-emerald-700',
  completed: 'bg-emerald-50 text-emerald-700',
  cancelled: 'bg-red-50 text-red-700',
}

function CopyBox({ label, text, channel, onSave }) {
  const [value, setValue] = useState(text ?? '')
  const [copied, setCopied] = useState(false)
  const [saving, setSaving] = useState(false)
  const dirty = value !== (text ?? '')

  useEffect(() => { setValue(text ?? '') }, [text])
  if (!text && !value) return null

  return (
    <div className="rounded-2xl ring-1 ring-slate-200 p-4">
      <div className="flex items-center justify-between gap-2 mb-2">
        <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
          {label}
        </p>
        <div className="flex items-center gap-1.5">
          {dirty && (
            <button
              onClick={async () => {
                setSaving(true)
                await onSave(channel, value)
                setSaving(false)
              }}
              className="text-[11px] font-semibold px-2.5 py-1 rounded-lg bg-slate-900 text-white">
              {saving ? 'Saving…' : 'Save edit'}
            </button>
          )}
          <button
            onClick={() => {
              navigator.clipboard.writeText(value)
              setCopied(true)
              setTimeout(() => setCopied(false), 1500)
            }}
            className="text-[11px] font-medium px-2 py-1 rounded-lg text-slate-500 hover:bg-slate-100">
            {copied ? <Check size={12} /> : <CopyIcon size={12} />}
          </button>
        </div>
      </div>
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={Math.min(6, Math.max(2, Math.ceil(value.length / 60)))}
        className="w-full text-[13px] text-slate-700 leading-relaxed bg-transparent resize-none focus:outline-none"
      />
      {channel === 'sms' && (
        <p className="text-[10px] text-slate-400 mt-1">
          {value.length} characters · {Math.ceil(value.length / 160) || 1} SMS segment(s)
        </p>
      )}
    </div>
  )
}

export default function CampaignWorkspace() {
  const { strategyId } = useParams()
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [savingSchedule, setSavingSchedule] = useState('')

  const load = useCallback(async () => {
    try {
      const { data } = await workspaceApi.get(strategyId)
      setState(data)
      setError('')
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Could not open this campaign.')
    } finally { setLoading(false) }
  }, [strategyId])

  useEffect(() => { load() }, [load])

  const schedule = async (preset) => {
    setSavingSchedule(preset)
    try {
      await workspaceApi.setSchedule(strategyId, { preset })
      await load()
    } catch { /* the button simply doesn't take */ }
    finally { setSavingSchedule('') }
  }

  /**
   * PHASE 23.8 — the campaign package.
   *
   * Downloadable at any point, not just when the bar reads 100%. Half a
   * campaign is still the owner's work, and the README names what is missing
   * rather than the button refusing to do anything.
   */
  const [packaging, setPackaging] = useState(false)
  const [packageError, setPackageError] = useState('')
  const downloadPackage = async () => {
    setPackaging(true)
    setPackageError('')
    try {
      await workspaceApi.downloadPackage(strategyId)
    } catch {
      // Kept local: a failed download must not replace the page the owner is
      // working on with an error screen.
      setPackageError('Could not build the package. Try again in a moment.')
    } finally { setPackaging(false) }
  }

  const saveCopy = async (channel, text) => {
    try {
      await workspaceApi.setCopy(strategyId, { channel, text })
      await load()
    } catch { /* keep the edit on screen rather than losing it */ }
  }

  if (loading) {
    return <Layout><div className="max-w-4xl mx-auto h-72 bg-slate-100 rounded-3xl animate-pulse" /></Layout>
  }
  if (error) {
    return (
      <Layout>
        <div className="max-w-lg mx-auto bg-red-50 ring-1 ring-red-100 rounded-3xl p-6 text-center">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      </Layout>
    )
  }

  const { context, steps, progress, schedule: sched, copy, status } = state
  const summary = context.summary

  return (
    <Layout>
      <div className="max-w-4xl mx-auto space-y-5 pb-12">

        <div>
          <Link to="/ai"
            className="inline-flex items-center gap-1.5 text-[12px] font-medium text-slate-500 hover:text-slate-900 mb-3">
            <ArrowLeft size={13} /> Campaigns
          </Link>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="min-w-0">
              <h1 className="text-2xl font-bold text-slate-900">{summary.campaign}</h1>
              {summary.occasion && (
                <p className="text-[13px] text-slate-500 mt-1">{summary.occasion}</p>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button onClick={downloadPackage} disabled={packaging}
                title="The ad, the labels, every piece of copy and a summary PDF"
                className="flex items-center gap-1.5 text-[12px] font-semibold px-3 py-1.5 rounded-xl ring-1 ring-slate-200 text-slate-700 hover:ring-slate-900 disabled:opacity-60">
                {packaging ? <Loader2 size={13} className="animate-spin" />
                           : <Package size={13} />}
                {packaging ? 'Packaging…' : 'Download campaign'}
              </button>
              <span className={`text-[11px] font-bold px-3 py-1.5 rounded-full capitalize ${
                STATUS_TONE[status] ?? STATUS_TONE.draft}`}>
                {status}
              </span>
            </div>
          </div>
          {packageError && (
            <p className="text-[12px] text-red-600 mt-2">{packageError}</p>
          )}
        </div>

        {/* Coach line — assembled from the strategy, not a model call. */}
        {state.coach && (
          <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-6">
            <div className="flex items-start gap-3">
              <Sparkles size={16} className="text-white/70 mt-0.5 shrink-0" />
              <p className="text-[14px] leading-relaxed text-slate-100">{state.coach}</p>
            </div>
          </div>
        )}

        {/* Progress — the thing that was missing. */}
        <section className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-6">
          <div className="flex items-end justify-between gap-4 mb-4 flex-wrap">
            <div>
              <h2 className="text-[15px] font-bold text-slate-900">Campaign progress</h2>
              <p className="text-[12px] text-slate-500 mt-0.5">
                {progress.complete} of {progress.total} steps
                {progress.next && ` · next: ${progress.next.label}`}
              </p>
            </div>
            <span className="text-2xl font-bold text-slate-900 tabular-nums">
              {progress.pct}%
            </span>
          </div>

          <div className="h-2 bg-slate-100 rounded-full overflow-hidden mb-5">
            <div className="h-full bg-emerald-500 rounded-full transition-all duration-700"
              style={{ width: `${progress.pct}%` }} />
          </div>

          <div className="space-y-1">
            {steps.map((step) => {
              const body = (
                <>
                  <span className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${
                    step.done ? 'bg-emerald-500' : 'bg-slate-200'}`}>
                    {step.done ? <Check size={12} className="text-white" />
                               : <Clock size={11} className="text-slate-400" />}
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className={`block text-[13px] font-semibold ${
                      step.done ? 'text-slate-900' : 'text-slate-500'}`}>
                      {step.label}
                    </span>
                    {step.detail && (
                      <span className="block text-[11px] text-slate-400">{step.detail}</span>
                    )}
                  </span>
                  {step.route && (
                    <ArrowRight size={14} className="text-slate-300 shrink-0" />
                  )}
                </>
              )
              const className = 'w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors'

              // Embedded steps scroll to their section; the rest still link out
              // with the campaign attached, so the tool opens on it.
              const anchor = EMBEDDED[step.key]
              if (anchor) {
                return (
                  <button key={step.key}
                    onClick={() => document.getElementById(anchor)
                      ?.scrollIntoView({ behavior: 'smooth' })}
                    className={`${className} hover:bg-slate-50`}>
                    {body}
                  </button>
                )
              }

              return step.route ? (
                <Link key={step.key}
                  to={`${step.route}?strategy=${state.strategy_id}`}
                  className={`${className} hover:bg-slate-50`}>
                  {body}
                </Link>
              ) : (
                <div key={step.key} className={className}>{body}</div>
              )
            })}
          </div>
        </section>

        {/* Overview */}
        <section className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-6">
          <h2 className="text-[15px] font-bold text-slate-900 mb-4">Campaign overview</h2>
          <div className="grid sm:grid-cols-2 gap-x-6 gap-y-3">
            {[
              ['Business goal', summary.goal],
              ['Target audience', summary.audience],
              ['Recommended offer', summary.offer],
              ['Primary product', summary.primary_product],
              ['Expected impact', summary.expected_outcome],
              ['Products', (summary.products ?? []).slice(0, 4).join(' · ')],
            ].filter(([, v]) => v).map(([label, value]) => (
              <div key={label} className="min-w-0">
                <p className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</p>
                <p className="text-[13px] text-slate-800 leading-snug">{value}</p>
              </div>
            ))}
          </div>
        </section>

        {/* The advertisement, generated here. Same hook, same form, same
            payload as the standalone Ad Creator — see CampaignAdSection. */}
        <CampaignAdSection strategyId={strategyId} onGenerated={load} />

        {/* The shelf labels for this campaign — the same editor as the Label
            Studio page, scoped by the strategy_id the migration added. */}
        <CampaignLabelsSection strategyId={strategyId} onSaved={load} />

        {/* Copy — every channel, editable, saved as overrides. */}
        <section className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-6">
          <h2 className="text-[15px] font-bold text-slate-900 mb-1">Campaign copy</h2>
          <p className="text-[12px] text-slate-500 mb-4">
            Written when the strategy was generated. Edit anything — your version
            is kept alongside the original.
          </p>
          <div className="space-y-3">
            <CopyBox label="Social" text={copy.social} channel="social" onSave={saveCopy} />
            <CopyBox label="Email subject" text={copy.email_subject}
              channel="email_subject" onSave={saveCopy} />
            <CopyBox label="Email body" text={copy.email} channel="email" onSave={saveCopy} />
            <CopyBox label="SMS" text={copy.sms} channel="sms" onSave={saveCopy} />
          </div>
        </section>

        {/* Scheduler — preparation, and honest about it. */}
        <section className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-6">
          <div className="flex items-center gap-2 mb-1">
            <Calendar size={15} className="text-slate-400" />
            <h2 className="text-[15px] font-bold text-slate-900">When should this go out?</h2>
          </div>
          <p className="text-[12px] text-slate-500 mb-4">
            This records your plan. Sending is not automated yet — you will still
            launch it yourself.
          </p>

          {sched.scheduled_for && (
            <p className="flex items-center gap-2 text-[13px] font-semibold text-emerald-700 bg-emerald-50 rounded-xl px-3 py-2 mb-3">
              <CheckCircle2 size={14} />
              Planned for {new Date(sched.scheduled_for).toLocaleString()}
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            {sched.options.filter((o) => o.preset !== 'custom').map((o) => (
              <button key={o.preset} onClick={() => schedule(o.preset)}
                title={o.why}
                className={`text-[12px] font-medium px-3.5 py-2 rounded-xl ring-1 transition-all ${
                  sched.preset === o.preset
                    ? 'bg-slate-900 text-white ring-slate-900'
                    : 'bg-white text-slate-700 ring-slate-200 hover:ring-slate-900'}`}>
                {savingSchedule === o.preset ? <Loader2 size={12} className="animate-spin" />
                                             : o.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-slate-400 mt-3">
            {sched.options.find((o) => o.preset === sched.preset)?.why ??
             'Hover an option to see why that window works.'}
          </p>
        </section>
      </div>
    </Layout>
  )
}
