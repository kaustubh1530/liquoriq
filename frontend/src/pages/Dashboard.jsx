/**
 * Dashboard.jsx — Main analytics view
 *
 * Shows: KPI summary cards, top products bar chart, category breakdown pie chart
 * All data comes from the analytics API endpoints built in Phase 6.
 */

import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { DollarSign, ShoppingCart, Package, TrendingUp } from 'lucide-react'
import { analyticsApi } from '../api/client'
import Layout from '../components/Layout'
import StatCard from '../components/StatCard'

const COLORS = ['#e8a020', '#f5c55a', '#f9dfa0', '#3b82f6', '#6366f1', '#10b981']

const fmt = (n) =>
  n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${Number(n).toFixed(2)}`

export default function Dashboard() {
  const [summary, setSummary]     = useState(null)
  const [topProds, setTopProds]   = useState([])
  const [categories, setCategories] = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        const [s, t, c] = await Promise.all([
          analyticsApi.summary(),
          analyticsApi.topProducts(8),
          analyticsApi.categoryPerformance(),
        ])
        setSummary(s.data)
        setTopProds(t.data)
        setCategories(c.data)
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
