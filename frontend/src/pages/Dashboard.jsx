/**
 * Dashboard.jsx — Main analytics view
 *
 * Shows: KPI summary cards, top products bar chart, category breakdown pie chart
 * All data comes from the analytics API endpoints built in Phase 6.
 */

import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, AreaChart, Area, CartesianGrid,
} from 'recharts'
import { Link } from 'react-router-dom'
import {
  DollarSign, ShoppingCart, Package, TrendingUp,
  Boxes, AlertTriangle, RotateCw, Layers, ArrowRight, CheckCircle2, Sparkles,
} from 'lucide-react'
import { analyticsApi } from '../api/client'
import Layout from '../components/Layout'
import StatCard from '../components/StatCard'

const COLORS = ['#e8a020', '#f5c55a', '#f9dfa0', '#3b82f6', '#6366f1', '#10b981']

const fmt = (n) =>
  n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${Number(n).toFixed(2)}`
const money0 = (n) => `$${Math.round(Number(n)).toLocaleString()}`

const ACTION_ICON = { reorder: RotateCw, dead: AlertTriangle, overstock: Layers }

export default function Dashboard() {
  const [summary, setSummary]     = useState(null)
  const [topProds, setTopProds]   = useState([])
  const [categories, setCategories] = useState([])
  const [inv, setInv]             = useState(null)
  const [trend, setTrend]         = useState([])
  const [campaign, setCampaign]   = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        const [s, t, c, i] = await Promise.all([
          analyticsApi.summary(),
          analyticsApi.topProducts(8),
          analyticsApi.categoryPerformance(),
          analyticsApi.inventory(),
        ])
        setSummary(s.data)
        setTopProds(t.data)
        setCategories(c.data)
        setInv(i.data)
        // Non-critical extras — don't fail the whole dashboard if they error
        analyticsApi.trend().then((r) => setTrend(r.data)).catch(() => {})
        analyticsApi.campaignSummary().then((r) => setCampaign(r.data)).catch(() => {})
      } catch (err) {
        setError('Failed to load analytics. Make sure you have uploaded and parsed a report.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  return (
    <Layout>
      <div className="max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Dashboard</h1>
        <p className="text-sm text-gray-500 mb-8">
          {summary
            ? `Data from ${summary.date_from ?? '—'} to ${summary.date_to ?? '—'}`
            : 'Upload and parse a report to see your analytics'}
        </p>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-amber-50 text-amber-700 text-sm">{error}</div>
        )}

        {loading ? (
          <div className="text-gray-400 text-sm">Loading…</div>
        ) : summary ? (
          <>
            {/* ── KPI cards ── */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <StatCard
                title="Total Revenue"
                value={fmt(summary.total_revenue)}
                subtitle={`${summary.total_orders} transactions`}
                icon={DollarSign}
              />
              <StatCard
                title="Total Orders"
                value={summary.total_orders.toLocaleString()}
                icon={ShoppingCart}
              />
              <StatCard
                title="Units Sold"
                value={summary.total_units.toLocaleString()}
                icon={Package}
              />
              <StatCard
                title="Avg Order Value"
                value={`$${summary.average_order_value}`}
                subtitle={`Top channel: ${summary.top_channel ?? 'N/A'}`}
                icon={TrendingUp}
              />
            </div>

            {/* ── Last campaign ROI (Phase 18) ── */}
            {campaign && campaign.status !== 'no_baseline' && (campaign.total_units_lift_pct !== null || campaign.total_revenue_lift !== null) && (
              <Link to="/ai" className="block mb-8">
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex items-center justify-between hover:border-brand-200 transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-brand-50 flex items-center justify-center shrink-0">
                      <Sparkles size={18} className="text-brand-500" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold">
                        {campaign.status === 'complete' ? 'Last campaign' : `Campaign · day ${campaign.days_elapsed} of ${campaign.campaign_window_days}`}
                      </p>
                      <p className="text-sm font-semibold text-gray-800 truncate">{campaign.strategy_title}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 shrink-0">
                    {campaign.total_units_lift_pct !== null && (
                      <span className={`text-lg font-bold ${campaign.total_units_lift_pct >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                        {campaign.total_units_lift_pct > 0 ? '▲' : '▼'} {Math.abs(campaign.total_units_lift_pct)}% units
                      </span>
                    )}
                    {campaign.total_revenue_lift !== null && (
                      <span className={`text-lg font-bold ${campaign.total_revenue_lift >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                        {campaign.total_revenue_lift >= 0 ? '+' : '−'}${Math.abs(campaign.total_revenue_lift).toFixed(0)}
                      </span>
                    )}
                    <ArrowRight size={16} className="text-gray-300" />
                  </div>
                </div>
              </Link>
            )}

            {/* ── Action Center + Inventory Intelligence (Phase 17) ── */}
            {inv?.has_stock_data && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                {/* Do these today */}
                <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-lg">✅</span>
                    <h2 className="text-sm font-semibold text-gray-700">Do these today</h2>
                  </div>
                  {inv.actions.length === 0 ? (
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <CheckCircle2 size={16} className="text-green-500" />
                      Inventory looks healthy — nothing urgent.
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {inv.actions.map((a, i) => {
                        const Icon = ACTION_ICON[a.type] ?? AlertTriangle
                        return (
                          <div key={i} className={`flex items-start justify-between gap-3 p-3 rounded-xl ${
                            a.severity === 'high' ? 'bg-red-50' : 'bg-amber-50'
                          }`}>
                            <div className="flex items-start gap-3 min-w-0">
                              <Icon size={16} className={a.severity === 'high' ? 'text-red-500 mt-0.5' : 'text-amber-500 mt-0.5'} />
                              <div className="min-w-0">
                                <p className="text-sm font-semibold text-gray-800">{a.title}</p>
                                <p className="text-xs text-gray-500 truncate">{a.detail}</p>
                              </div>
                            </div>
                            {a.cta && a.link && (
                              <Link to={a.link} className="shrink-0 inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:underline whitespace-nowrap">
                                {a.cta} <ArrowRight size={12} />
                              </Link>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>

                {/* Inventory value hero */}
                <div className="bg-gradient-to-br from-brand-500 to-brand-600 rounded-2xl shadow-sm p-6 text-white flex flex-col justify-center">
                  <div className="flex items-center gap-2 mb-1 text-white/80">
                    <Boxes size={16} />
                    <p className="text-xs font-semibold uppercase tracking-wide">Inventory on shelves</p>
                  </div>
                  <p className="text-3xl font-bold">{money0(inv.inventory_value)}</p>
                  <p className="text-xs text-white/70 mt-1">{inv.products_in_stock.toLocaleString()} products in stock</p>
                  {inv.dead_stock.value > 0 && (
                    <p className="text-xs text-white/90 mt-3 bg-white/10 rounded-lg px-2 py-1.5">
                      {money0(inv.dead_stock.value)} frozen in dead stock
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Inventory breakdown lists */}
            {inv?.has_stock_data && (inv.dead_stock.count > 0 || inv.reorder_soon.count > 0 || inv.overstocked.count > 0) && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <InvList title="Reorder soon" tone="red" icon={RotateCw}
                  items={inv.reorder_soon.items} field={(x) => `${x.weeks_supply ?? '—'} wks left`} />
                <InvList title="Dead stock" tone="amber" icon={AlertTriangle}
                  items={inv.dead_stock.items} field={(x) => money0(x.value)} />
                <InvList title="Overstocked" tone="blue" icon={Layers}
                  items={inv.overstocked.items} field={(x) => `${x.weeks_supply ?? '—'} wks`} />
              </div>
            )}

            {/* ── Sales trend over time (Phase 18) ── */}
            {trend.length > 0 && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold text-gray-700">Revenue over time</h2>
                  {trend.length === 1 && (
                    <span className="text-[11px] text-gray-400">Upload weekly reports to see the trend build</span>
                  )}
                </div>
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={trend} margin={{ left: 8, right: 16, top: 8 }}>
                    <defs>
                      <linearGradient id="rev" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#e8a020" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="#e8a020" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                    <XAxis dataKey="period" tick={{ fontSize: 11 }} tickFormatter={(v) => v?.slice(5)} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`} />
                    <Tooltip formatter={(v, n) => [n === 'revenue' ? `$${Number(v).toLocaleString()}` : v, n === 'revenue' ? 'Revenue' : 'Units']} />
                    <Area type="monotone" dataKey="revenue" stroke="#e8a020" strokeWidth={2} fill="url(#rev)" dot={{ r: 3, fill: '#e8a020' }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* ── Charts row ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Top products bar chart */}
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
                <h2 className="text-sm font-semibold text-gray-700 mb-4">Top Products by Revenue</h2>
                {topProds.length === 0 ? (
                  <p className="text-gray-400 text-sm">No product data yet.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={topProds} layout="vertical" margin={{ left: 8, right: 16 }}>
                      <XAxis type="number" tickFormatter={(v) => `$${v}`} tick={{ fontSize: 11 }} />
                      <YAxis
                        type="category"
                        dataKey="product_name"
                        width={120}
                        tick={{ fontSize: 11 }}
                        tickFormatter={(v) => v.length > 16 ? v.slice(0, 16) + '…' : v}
                      />
                      <Tooltip formatter={(v) => [`$${v}`, 'Revenue']} />
                      <Bar dataKey="total_revenue" fill="#e8a020" radius={[0, 6, 6, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* Category pie chart */}
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
                <h2 className="text-sm font-semibold text-gray-700 mb-4">Revenue by Category</h2>
                {categories.length === 0 ? (
                  <p className="text-gray-400 text-sm">No category data yet.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={260}>
                    <PieChart>
                      <Pie
                        data={categories}
                        dataKey="total_revenue"
                        nameKey="category"
                        cx="50%"
                        cy="50%"
                        outerRadius={90}
                        label={({ category, revenue_percentage }) =>
                          `${category} ${revenue_percentage}%`
                        }
                        labelLine={false}
                      >
                        {categories.map((_, i) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v) => [`$${v}`, 'Revenue']} />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="bg-white rounded-2xl border border-gray-100 p-12 text-center">
            <p className="text-4xl mb-4">📊</p>
            <p className="text-gray-600 font-medium">No data yet</p>
            <p className="text-gray-400 text-sm mt-1">
              Go to <strong>Uploads</strong> to upload your first sales report.
            </p>
          </div>
        )}
      </div>
    </Layout>
  )
}

// ── Inventory breakdown list (Phase 17) ──────────────────────────────────────
function InvList({ title, tone, icon: Icon, items, field }) {
  const tones = {
    red: 'text-red-500', amber: 'text-amber-500', blue: 'text-blue-500',
  }
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-3">
        <Icon size={16} className={tones[tone]} />
        <h2 className="text-sm font-semibold text-gray-700">{title}</h2>
        <span className="text-xs text-gray-400">({items.length})</span>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-gray-400">None 🎉</p>
      ) : (
        <div className="space-y-1.5">
          {items.slice(0, 6).map((x, i) => (
            <div key={i} className="flex items-center justify-between text-xs">
              <span className="text-gray-700 truncate mr-2">{x.product_name}</span>
              <span className={`font-semibold shrink-0 ${tones[tone]}`}>{field(x)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
