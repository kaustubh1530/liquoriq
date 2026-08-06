/**
 * summary.js — the executive summary, composed from figures already computed.
 *
 * WHY THIS IS NOT AN AI CALL.
 *
 * The summary sits at the very top of the page and is the first thing the
 * owner reads. An API round-trip would put a spinner in that slot for a second
 * or two on every load, cost money on every page view, and — on a slow network
 * or an expired OpenAI balance — leave the most prominent element on the
 * dashboard empty.
 *
 * Every sentence here is assembled from numbers the deterministic engine has
 * ALREADY returned in the same payload. Nothing is calculated: values are
 * selected, ranked and phrased. That means the headline can never disagree
 * with the cards beneath it, which an independently-generated summary
 * eventually would.
 *
 * The AI Advisor still exists per-action ("Why?"), where the latency is opt-in
 * and the explanation is checked against the figures it was given.
 */

const money = (n) => `$${Math.round(Number(n) || 0).toLocaleString()}`
const compact = (n) => {
  const v = Math.abs(Number(n) || 0)
  if (v >= 1000) return `$${Math.round(v / 1000)}k`
  return `$${Math.round(v)}`
}

export function greeting(date = new Date()) {
  const h = date.getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

/**
 * The headline number: what acting on the top recommendations is worth.
 *
 * Deliberately the CONFIDENCE-ADJUSTED total, not the raw one. The raw figure
 * is bigger and more flattering, but it treats a low-confidence industry
 * assumption as equal to a measurement of this shop. The bigger number is the
 * one that gets the owner to stop trusting the dashboard.
 */
export function opportunityHeadline(bi) {
  const headline = bi?.headline ?? {}
  return {
    value: headline.opportunity_value_adjusted ?? 0,
    raw: headline.opportunity_value ?? 0,
    basis: headline.opportunity_basis ?? '',
  }
}

/**
 * Three short bullets naming WHY the number is what it is — drawn straight
 * from the evidence on the top actions, so each one is checkable below.
 */
export function reasons(bi) {
  const out = []
  const byType = Object.fromEntries((bi?.actions ?? []).map((a) => [a.type, a]))

  const reorder = byType.reorder
  if (reorder?.evidence?.products_out_of_stock) {
    out.push({
      tone: 'critical',
      text: `${reorder.evidence.products_out_of_stock} products are sold out right now`,
    })
  }

  const seasonal = byType.seasonal
  if (seasonal?.evidence?.holiday) {
    out.push({
      tone: 'info',
      text: `${seasonal.evidence.holiday} is ${seasonal.evidence.days_away} days away`,
    })
  }

  const clearance = byType.clearance
  if (clearance?.evidence?.cash_frozen_retail) {
    out.push({
      tone: 'warning',
      text: `${compact(clearance.evidence.cash_frozen_retail)} of inventory is sleeping on the shelves`,
    })
  }

  return out.slice(0, 3)
}

/**
 * Two to three sentences of plain business English.
 *
 * Structure is fixed on purpose: state the position, name the single biggest
 * problem, then name this week's priority. An owner reading it every Monday
 * should find the same shape with different numbers.
 */
export function executiveSummary(bi) {
  if (!bi || bi.empty) return ''

  const summary = bi.summary ?? {}
  const valuation = bi.valuation ?? {}
  const actions = bi.actions ?? []
  const sentences = []

  // 1. Where the business stands, in the owner's terms rather than a score.
  const turnover = summary.turnover
  if (turnover) {
    sentences.push(
      turnover >= 4
        ? `Your stock is turning over ${turnover}× a year, which is healthy.`
        : `Your stock is turning over ${turnover}× a year against a healthy 4–6×, so cash is moving slowly.`
    )
  }

  // 2. The single biggest problem, named — not a list.
  const frozenPct = bi.headline?.frozen_pct
  if (frozenPct >= 50) {
    const label = valuation.basis === 'cost' ? 'cash' : 'stock value at retail'
    sentences.push(
      `${frozenPct}% of your ${label} is tied up in products that are barely selling — ` +
      `that is your biggest problem, not a shortage of customers.`
    )
  }

  // 3. This week's priority, taken from the top-ranked action.
  const top = actions[0]
  if (top) {
    const when = top.timeline ? top.timeline.toLowerCase() : 'this week'
    sentences.push(
      `Your highest-value move ${when === 'today' ? 'today' : `for ${when}`} is ` +
      `${top.suggested_action.charAt(0).toLowerCase()}${top.suggested_action.slice(1)}, ` +
      `worth about ${money(top.business_impact)}.`
    )
  }

  return sentences.slice(0, 3).join(' ')
}

/**
 * The AI Business Coach: biggest problem → why it matters → what to do.
 *
 * NO NEW GPT CALL. The card reads like a person talking, but every clause is
 * selected from figures the deterministic engine already returned. That is a
 * deliberate trade: a real model call in this slot would add a spinner to the
 * second-most prominent element on the page, cost money on every visit, and
 * risk contradicting the cards underneath it.
 *
 * Per-action AI explanation still exists behind the "Why?" button, where the
 * latency is opt-in and the output is validated against the supplied figures.
 */
export function coach(bi) {
  if (!bi || bi.empty) return null

  const top = (bi.actions ?? [])[0]
  if (!top) return null

  const summary = bi.summary ?? {}
  const valuation = bi.valuation ?? {}
  const frozenPct = bi.headline?.frozen_pct ?? 0
  const basisWord = valuation.basis === 'cost' ? 'cash' : 'stock value'

  // The biggest problem is whichever of the two structural ones is worse —
  // not simply the top action, which is the biggest OPPORTUNITY.
  const slowStock = frozenPct >= 50
  const problem = slowStock
    ? `${frozenPct}% of your ${basisWord} is sitting in products that are barely selling`
    : `${top.evidence?.products_out_of_stock ?? 0} products are out of stock while customers are still asking for them`

  const matters = slowStock
    ? `That money can't buy anything else until it sells. Your stock turns over ` +
      `${summary.turnover ?? '—'}× a year against a healthy 4–6×, so it isn't going ` +
      `to clear on its own.`
    : `Every day a seller is off the shelf is a sale that doesn't come back later — ` +
      `the customer buys it somewhere else.`

  return {
    problem,
    matters,
    action: top.suggested_action,
    timeline: top.timeline,
    timelineReason: top.timeline_reason,
    impact: top.business_impact_label,
    confidence: top.confidence,
    route: top.action?.route,
    type: top.type,
  }
}

/** The three highest-impact actions. Everything else lives behind a link. */
export function topPriorities(bi, n = 3) {
  return (bi?.actions ?? []).slice(0, n)
}

export { money, compact }
