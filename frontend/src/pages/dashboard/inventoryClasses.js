/**
 * inventoryClasses.js — the nine stock classes, and what colour each one means.
 *
 * Kept out of the component file so both the dashboard band chart and the
 * Inventory Intelligence table read from ONE definition. A status chip that
 * says "Sleeping" in slate on one page and "sleeping" in brown on another
 * makes the owner wonder whether they're the same thing.
 *
 * COLOUR CARRIES SEVERITY, NOT ORDER. The previous palette used nine distinct
 * hues including three near-identical browns, so the eye had to decode a
 * legend instead of reading the chart. Now: red = losing money today,
 * amber = needs attention, green = fine, slate = money asleep, blue = a data
 * problem to fix rather than a business one.
 */

// Worst first: the eye should land on the problem, not the healthy middle.
export const CLASS_ORDER = ['sold_out', 'critical', 'reorder', 'healthy',
                            'heavy', 'overstock', 'sleeping', 'dead', 'negative']

export const CLASS_META = {
  sold_out:  { label: 'Sold out',       note: 'Losing sales today',    tone: 'critical' },
  critical:  { label: 'Critical',       note: 'Under 1 week left',     tone: 'critical' },
  reorder:   { label: 'Reorder soon',   note: 'Under 3 weeks left',    tone: 'warning' },
  healthy:   { label: 'Healthy',        note: '3–12 weeks of stock',   tone: 'healthy' },
  heavy:     { label: 'Heavy',          note: '3–6 months of stock',   tone: 'warning' },
  overstock: { label: 'Overstock',      note: '6–12 months of stock',  tone: 'warning' },
  sleeping:  { label: 'Sleeping',       note: 'Over a year of stock',  tone: 'asleep' },
  dead:      { label: 'Dead',           note: 'Never sold',            tone: 'asleep' },
  negative:  { label: 'Negative count', note: 'Miscounted — fix this', tone: 'info' },
}

export const TONE = {
  critical: { bar: 'bg-red-500',     text: 'text-red-600',     chip: 'bg-red-50 text-red-700' },
  warning:  { bar: 'bg-amber-500',   text: 'text-amber-600',   chip: 'bg-amber-50 text-amber-700' },
  healthy:  { bar: 'bg-emerald-500', text: 'text-emerald-600', chip: 'bg-emerald-50 text-emerald-700' },
  asleep:   { bar: 'bg-slate-400',   text: 'text-slate-600',   chip: 'bg-slate-100 text-slate-600' },
  info:     { bar: 'bg-blue-400',    text: 'text-blue-600',    chip: 'bg-blue-50 text-blue-700' },
}

export const compact = (n) => {
  const v = Number(n) || 0
  return v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(0)}`
}
