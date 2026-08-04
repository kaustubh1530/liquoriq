/**
 * MarginPrompt.jsx — turn retail figures into cash figures.
 *
 * The POS export has selling prices only, so every inventory number is at
 * RETAIL. Until the owner tells us his gross margin we say "retail value" and
 * show no cost figure — we don't substitute an industry average, because a
 * number he didn't give us is not his number, and this is the figure he checks
 * first.
 *
 * Shown as a quiet bar, not a modal: it's an improvement, not a blocker.
 */

import { useState } from 'react'
import { intelligenceApi } from '../../api/client'
import { Percent, Check, Loader2, X } from 'lucide-react'

export default function MarginPrompt({ valuation, onSaved }) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState(valuation?.gross_margin_pct ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const save = async () => {
    setSaving(true); setError('')
    try {
      await intelligenceApi.setGrossMargin(value === '' ? null : Number(value))
      setOpen(false)
      onSaved?.()
    } catch {
      setError('Could not save that. Enter a whole number between 1 and 90.')
    } finally {
      setSaving(false)
    }
  }

  // Already set: a quiet line confirming whose number this is.
  if (valuation?.basis === 'cost' && !open) {
    return (
      <button onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 text-[11px] text-gray-400 hover:text-brand-600">
        <Check size={11} className="text-green-500" />
        Cash figures use your {valuation.gross_margin_pct}% gross margin · change
      </button>
    )
  }

  if (!open) {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50/60 px-4 py-3">
        <Percent size={15} className="text-amber-600 mt-0.5 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-gray-900">
            These are retail values, not cash
          </p>
          <p className="text-[11px] text-gray-600 mt-0.5">
            Your POS export has no cost prices, so inventory is valued at what it
            would sell for. Add your gross margin to see what's actually tied up.
          </p>
        </div>
        <button onClick={() => setOpen(true)}
          className="text-[11px] font-semibold px-3 py-1.5 rounded-lg bg-gray-900 text-white hover:bg-gray-700 shrink-0">
          Add margin
        </button>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 flex-wrap">
      <label className="text-xs text-gray-600">Average gross margin</label>
      <div className="flex items-center gap-1">
        <input
          type="number" min="1" max="90" value={value} autoFocus
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && save()}
          className="w-20 border border-gray-200 rounded-lg px-2 py-1.5 text-sm text-right focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <span className="text-sm text-gray-500">%</span>
      </div>
      <button onClick={save} disabled={saving}
        className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg bg-brand-500 text-white hover:bg-brand-600 disabled:opacity-50">
        {saving ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />} Save
      </button>
      <button onClick={() => { setOpen(false); setError('') }}
        className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400">
        <X size={14} />
      </button>
      <p className="text-[11px] text-gray-400 w-full">
        Roughly what he keeps on an average sale. Leave blank to go back to
        showing retail values only.
      </p>
      {error && <p className="text-[11px] text-red-600 w-full">{error}</p>}
    </div>
  )
}
