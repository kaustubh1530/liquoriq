/**
 * FromActionBanner.jsx — "you arrived here from a recommendation".
 *
 * When the owner clicks an action on the dashboard, the destination page used
 * to open blank: he had to remember which products the recommendation named
 * and re-enter them, which is most of the work the recommendation existed to
 * save. The page now pre-fills from router state, and this banner says so —
 * because a form that silently fills itself in is unnerving, and he needs to
 * know what to change if it guessed wrong.
 */

import { Target, X } from 'lucide-react'

export default function FromActionBanner({ action, onDismiss }) {
  if (!action) return null
  const products = action.products ?? []

  return (
    <div className="flex items-start gap-3 rounded-xl border border-brand-200 bg-brand-50/60 px-4 py-3 mb-4">
      <Target size={16} className="text-brand-600 mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold text-gray-900">
          From your dashboard: {action.title}
        </p>
        {products.length > 0 && (
          <p className="text-[11px] text-gray-600 mt-1">
            {products.length} product{products.length === 1 ? '' : 's'} pre-loaded —{' '}
            <span className="text-gray-500">{products.slice(0, 4).join(' · ')}
              {products.length > 4 && ` +${products.length - 4} more`}</span>
          </p>
        )}
      </div>
      {onDismiss && (
        <button onClick={onDismiss} aria-label="Dismiss"
                className="p-1 rounded-lg hover:bg-brand-100 text-gray-400 shrink-0">
          <X size={14} />
        </button>
      )}
    </div>
  )
}
