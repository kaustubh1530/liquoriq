/**
 * ActionCard.jsx — PHASE 22: one executive recommendation.
 *
 * Shows the seven required fields: priority, business impact, confidence,
 * evidence, recommended action, estimated impact, and a one-click button.
 *
 * The evidence is visible by default rather than hidden behind a tooltip —
 * that's what makes the recommendation checkable instead of a black box. The
 * AI explanation is opt-in per card, because it costs money and latency for
 * prose the owner may not need.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { intelligenceApi } from '../../api/client'
import ReorderPanel from './ReorderPanel'
import {
  ArrowRight, Sparkles, ChevronDown, ChevronUp, Loader2, Info, CalendarClock,
} from 'lucide-react'

const PRIORITY = {
  P1: { chip: 'bg-red-100 text-red-700', bar: 'bg-red-500' },
  P2: { chip: 'bg-amber-100 text-amber-700', bar: 'bg-amber-500' },
  P3: { chip: 'bg-gray-100 text-gray-600', bar: 'bg-gray-300' },
}

const CONFIDENCE = {
  high: 'bg-green-50 text-green-700 border-green-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  low: 'bg-gray-50 text-gray-600 border-gray-200',
}

// The one-click action label per opportunity type.
const CTA = {
  reorder: 'Reorder products',
  clearance: 'Launch clearance',
  seasonal: 'Generate campaign',
  bundle: 'Create bundle',
  premium_upsell: 'Create upsell tags',
  winback: 'Win back customers',
  campaign_repeat: 'Repeat campaign',
}

const money = (n) => `$${Math.round(Number(n) || 0).toLocaleString()}`

const LABELS = {
  cash_frozen: 'Cash frozen', cash_frozen_retail: 'Slow stock (retail)',
  products: 'Products',
  // Assumed rates are labelled as assumed wherever they appear.
  assumed_recovery_rate: 'Assumed recovery rate',
  assumed_uplift_rate: 'Assumed uplift rate',
  realistic_months_to_clear: 'Realistic months to clear',
  monthly_clearance_capacity: 'Monthly clearance capacity',
  products_in_scope: 'Relevant products',
  their_sales_last_period: 'Their sales last period',
  stock_available: 'Stock available',
  why_these_products: 'Why these products',
  relevant_categories: 'Categories',
  sleeping_over_a_year: 'Over a year of stock', sleeping_cash: 'Sleeping cash',
  products_out_of_stock: 'Out of stock', products_running_low: 'Running low',
  weekly_sales_at_risk: 'Weekly sales at risk', horizon_weeks: 'Horizon (weeks)',
  recovery_rate: 'Recovery rate', holiday: 'Holiday', days_away: 'Days away',
  stock_value_in_scope: 'Stock in scope', uplift_rate: 'Uplift rate',
  total_customers: 'Customers', response_rate: 'Response rate',
  measured_lift: 'Measured lift', days_since_it_ran: 'Days since it ran',
  attach_rate: 'Attach rate', conversion_rate: 'Conversion rate',
}

function evidenceRows(evidence) {
  return Object.entries(evidence || {})
    .filter(([, v]) => typeof v === 'number' || typeof v === 'string')
    .slice(0, 6)
    .map(([k, v]) => {
      const label = LABELS[k] || k.replace(/_/g, ' ')
      let value = v
      if (typeof v === 'number') {
        if (k.endsWith('_rate')) value = `${Math.round(v * 100)}%`
        else if (k.includes('cash') || k.includes('value') || k.includes('lift')
                 || k.includes('sales')) value = money(v)
        else value = v.toLocaleString()
      }
      return { key: k, label, value }
    })
}

export default function ActionCard({ action }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [explanation, setExplanation] = useState(null)
  const [loading, setLoading] = useState(false)
  const [reorderOpen, setReorderOpen] = useState(false)

  const priority = PRIORITY[action.priority] ?? PRIORITY.P3
  const rows = evidenceRows(action.evidence)

  /**
   * The one-click action.
   *
   * Reorder opens a panel rather than navigating: its route was
   * "/dashboard?focus=reorder", which is the page the button is already on, so
   * clicking it did nothing at all. There is also nowhere sensible to send
   * him — what he needs is the list itself.
   *
   * Every other action navigates AND CARRIES ITS PRODUCTS in router state.
   * Previously the destination page opened blank and the owner had to
   * remember which products the recommendation named, which is most of the
   * work the recommendation was supposed to save him. Router state is used in
   * preference to the query string because these lists run to 20 names.
   */
  const takeAction = () => {
    if (action.type === 'reorder') { setReorderOpen(true); return }
    navigate(action.action.route, {
      state: {
        fromAction: {
          type: action.type,
          title: action.title,
          products: action.products ?? [],
          suggestion: action.suggested_action,
          evidence: action.evidence,
        },
      },
    })
  }

  const askAdvisor = async () => {
    if (explanation) { setOpen(!open); return }
    setLoading(true); setOpen(true)
    try {
      const { data } = await intelligenceApi.explain(action)
      setExplanation(data.explanation)
    } catch {
      setExplanation({
        why_it_exists: action.title,
        why_it_matters: action.expected_outcome,
        expected_outcome: action.expected_outcome,
        limitations: action.confidence_reason,
        next_action: action.suggested_action,
        source: 'deterministic',
      })
    } finally { setLoading(false) }
  }

  return (
    <article className="relative bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${priority.bar}`} />

      <div className="p-5 pl-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1.5">
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${priority.chip}`}>
                {action.priority} · {action.priority_label}
              </span>
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${CONFIDENCE[action.confidence]}`}>
                {action.confidence} confidence
              </span>
            </div>
            <h3 className="text-base font-bold text-gray-900 leading-snug">{action.title}</h3>
            <p className="text-sm text-gray-500 mt-1">{action.expected_outcome}</p>

            {/* When, and why then. A recommendation without a timeframe is a
                wish — "$132,396, do this now" was two months of total revenue. */}
            {action.timeline && (
              <p className="flex items-start gap-1.5 text-[11px] text-gray-500 mt-2">
                <CalendarClock size={12} className="mt-0.5 shrink-0 text-gray-400" />
                <span>
                  <b className="text-gray-700">{action.timeline}</b>
                  {action.timeline_reason && ` — ${action.timeline_reason}`}
                </span>
              </p>
            )}
          </div>

          {/* The money line the owner reads first */}
          <div className="text-right shrink-0">
            <p className="text-2xl font-bold text-gray-900 tabular-nums">
              {action.business_impact_label}
            </p>
            <p className="text-[10px] text-gray-400 uppercase tracking-wide">
              {action.estimated === false ? 'measured' : 'estimated impact'}
            </p>
          </div>
        </div>

        {/* Disclosed, not silent: products counted elsewhere. */}
        {action.allocation_note && (
          <p className="text-[11px] text-gray-400 mt-2 italic">{action.allocation_note}</p>
        )}

        {/* A clearance too big for one go, broken into phases the shop can absorb. */}
        {action.plan?.phases?.length > 0 && (
          <div className="mt-3 rounded-xl border border-gray-200 overflow-hidden">
            <p className="text-[11px] font-semibold text-gray-700 px-3 py-2 bg-gray-50">
              Phased plan — about {action.plan.months_to_clear} months at your sales rate
            </p>
            {action.plan.phases.map((p) => (
              <div key={p.phase} className="flex items-start gap-3 px-3 py-2 border-t border-gray-100">
                <span className="text-[10px] font-bold text-gray-400 w-12 shrink-0 pt-0.5">
                  {p.phase}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-semibold text-gray-800">
                    {p.timeline} · {p.products} products · {money(p.estimated_recovery)}
                  </p>
                  <p className="text-[10px] text-gray-500">{p.description}</p>
                </div>
              </div>
            ))}
            <p className="text-[10px] text-gray-400 px-3 py-1.5 bg-gray-50 border-t border-gray-100">
              {action.plan.basis}
            </p>
          </div>
        )}

        {/* Evidence — visible, not buried */}
        {rows.length > 0 && (
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-x-5 gap-y-1.5 bg-gray-50 rounded-xl p-3">
            {rows.map((r) => (
              <div key={r.key} className="min-w-0">
                <p className="text-[10px] text-gray-400 uppercase tracking-wide truncate">{r.label}</p>
                <p className="text-xs font-semibold text-gray-800 tabular-nums truncate">{r.value}</p>
              </div>
            ))}
          </div>
        )}

        {action.products?.length > 0 && (
          <p className="text-[11px] text-gray-400 mt-2 truncate">
            {action.products.slice(0, 3).join(' · ')}
            {action.products.length > 3 && ` +${action.products.length - 3} more`}
          </p>
        )}

        <div className="flex items-center gap-2 mt-4 flex-wrap">
          <button
            onClick={takeAction}
            className="flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-xl bg-brand-500 text-white hover:bg-brand-600 transition-colors"
          >
            {CTA[action.type] || 'Take action'} <ArrowRight size={13} />
          </button>
          <button
            onClick={askAdvisor}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-xl border border-gray-200 text-gray-600 hover:border-brand-300 hover:text-brand-600"
          >
            <Sparkles size={13} /> Why?
            {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
        </div>

        {/* AI Advisor — explains the numbers, never produces them */}
        {open && (
          <div className="mt-3 rounded-xl border border-brand-100 bg-brand-50/40 p-3.5">
            {loading ? (
              <p className="flex items-center gap-2 text-xs text-gray-500">
                <Loader2 size={13} className="animate-spin" /> Preparing the explanation…
              </p>
            ) : explanation && (
              <div className="space-y-2 text-xs text-gray-700">
                {[
                  ['Why this exists', explanation.why_it_exists],
                  ['Why it matters', explanation.why_it_matters],
                  ['Expected outcome', explanation.expected_outcome],
                  ['Limitations', explanation.limitations],
                  ['Next step', explanation.next_action],
                ].filter(([, v]) => v).map(([label, value]) => (
                  <p key={label}>
                    <span className="font-semibold text-gray-900">{label}: </span>{value}
                  </p>
                ))}
                <p className="flex items-center gap-1 text-[10px] text-gray-400 pt-1 border-t border-brand-100">
                  <Info size={10} />
                  {explanation.source === 'ai'
                    ? 'Written by AI from the figures above — it cannot change them.'
                    : 'Written from the figures above without AI.'}
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {reorderOpen && <ReorderPanel onClose={() => setReorderOpen(false)} />}
    </article>
  )
}
