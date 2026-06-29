/**
 * StatCard — Reusable KPI card for the dashboard
 * Props: title, value, subtitle, icon (optional lucide component)
 */
export default function StatCard({ title, value, subtitle, icon: Icon }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 flex items-start gap-4">
      {Icon && (
        <div className="p-3 rounded-xl bg-brand-50 text-brand-500">
          <Icon size={22} />
        </div>
      )}
      <div>
        <p className="text-sm text-gray-500 font-medium">{title}</p>
        <p className="text-2xl font-bold text-gray-900 mt-0.5">{value}</p>
        {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
      </div>
    </div>
  )
}
