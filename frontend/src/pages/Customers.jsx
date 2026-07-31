/**
 * Customers.jsx — Customer list + RFM segmentation (Phase 19)
 *
 * Upload a POS customer report → segment cards (VIP, Loyal, New, At Risk,
 * Inactive, High Value, Regular) each with a marketing recommendation → a
 * searchable, segment-filterable table with recency / frequency / spend.
 * No messages are sent — consent flags are shown for future SMS/email.
 */

import { useEffect, useState } from 'react'
import { customerApi } from '../api/client'
import Layout from '../components/Layout'
import { Users, Upload, Search, MessageSquare, Mail, UserPlus, X } from 'lucide-react'

const money = (n) => `$${Number(n || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`

const SEGMENT_STYLE = {
  'VIP':        'bg-purple-100 text-purple-700',
  'High Value': 'bg-emerald-100 text-emerald-700',
  'Loyal':      'bg-blue-100 text-blue-700',
  'New':        'bg-cyan-100 text-cyan-700',
  'At Risk':    'bg-amber-100 text-amber-700',
  'Inactive':   'bg-gray-200 text-gray-600',
  'Regular':    'bg-gray-100 text-gray-600',
}

function Badge({ segment }) {
  return (
    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${SEGMENT_STYLE[segment] ?? 'bg-gray-100 text-gray-600'}`}>
      {segment}
    </span>
  )
}

export default function Customers() {
  const [summary, setSummary] = useState(null)
  const [rows, setRows] = useState([])
  const [segment, setSegment] = useState(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  // Manual add-customer form
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({
    name: '', email: '', phone: '', total_spent: '', purchase_count: '',
    last_purchase_date: '', sms_opt_in: false, email_opt_in: false,
  })
  const [saving, setSaving] = useState(false)
  const [addError, setAddError] = useState('')

  const loadSummary = async () => {
    try { setSummary((await customerApi.segments()).data) } catch { /* empty */ }
  }
  const loadRows = async () => {
    try { setRows((await customerApi.list(segment, search)).data) } catch { /* empty */ }
  }

  useEffect(() => { (async () => { await Promise.all([loadSummary(), loadRows()]); setLoading(false) })() }, [])
  useEffect(() => { loadRows() }, [segment])

  const onSearch = (e) => { e.preventDefault(); loadRows() }

  const addCustomer = async () => {
    setAddError(''); setSaving(true)
    try {
      await customerApi.create({
        name: form.name.trim() || null,
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        total_spent: form.total_spent ? Number(form.total_spent) : 0,
        purchase_count: form.purchase_count ? Number(form.purchase_count) : 0,
        last_purchase_date: form.last_purchase_date || null,
        sms_opt_in: form.sms_opt_in,
        email_opt_in: form.email_opt_in,
      })
      setForm({ name: '', email: '', phone: '', total_spent: '', purchase_count: '', last_purchase_date: '', sms_opt_in: false, email_opt_in: false })
      setShowAdd(false)
      await Promise.all([loadSummary(), loadRows()])
    } catch (err) {
      setAddError(err.response?.data?.detail?.[0]?.msg ?? err.response?.data?.detail ?? 'Could not add customer.')
    } finally { setSaving(false) }
  }

  const onUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true); setError('')
    try {
      await customerApi.upload(file)
      await Promise.all([loadSummary(), loadRows()])
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Could not import that file.')
    } finally { setUploading(false) }
  }

  const activeSegments = (summary?.segments ?? []).filter((s) => s.count > 0)

  return (
    <Layout>
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-1 gap-2 flex-wrap">
          <h1 className="text-2xl font-bold text-gray-900">Customers</h1>
          <div className="flex items-center gap-2">
            <button onClick={() => { setShowAdd(!showAdd); setAddError('') }}
              className="inline-flex items-center gap-2 text-sm font-semibold text-gray-700 bg-white border border-gray-200 hover:border-brand-300 px-4 py-2 rounded-xl transition-colors">
              {showAdd ? <X size={15} /> : <UserPlus size={15} />} {showAdd ? 'Cancel' : 'Add customer'}
            </button>
            <label className="inline-flex items-center gap-2 text-sm font-semibold text-brand-600 bg-brand-50 hover:bg-brand-100 px-4 py-2 rounded-xl cursor-pointer transition-colors">
              <Upload size={15} />
              {uploading ? 'Importing…' : 'Import report'}
              <input type="file" accept=".csv,.xlsx,.xls" onChange={onUpload} className="hidden" disabled={uploading} />
            </label>
          </div>
        </div>
        <p className="text-sm text-gray-500 mb-6">
          Segmented by RFM — recency, frequency, and spend — with a marketing move for each group
        </p>

        {/* Manual add-customer form */}
        {showAdd && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 mb-6">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Add a customer</h2>
            {addError && <p className="text-xs text-red-500 mb-3">{addError}</p>}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
              <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              <input placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              <input placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}
                className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
              <div>
                <label className="block text-[11px] text-gray-400 mb-1">Total spent ($)</label>
                <input type="number" min="0" step="0.01" value={form.total_spent} onChange={(e) => setForm({ ...form, total_spent: e.target.value })}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-[11px] text-gray-400 mb-1">Visits</label>
                <input type="number" min="0" value={form.purchase_count} onChange={(e) => setForm({ ...form, purchase_count: e.target.value })}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-[11px] text-gray-400 mb-1">Last purchase</label>
                <input type="date" value={form.last_purchase_date} onChange={(e) => setForm({ ...form, last_purchase_date: e.target.value })}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
            </div>
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-4 text-xs text-gray-600">
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={form.sms_opt_in} onChange={(e) => setForm({ ...form, sms_opt_in: e.target.checked })} /> SMS opt-in
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={form.email_opt_in} onChange={(e) => setForm({ ...form, email_opt_in: e.target.checked })} /> Email opt-in
                </label>
              </div>
              <button onClick={addCustomer} disabled={saving || (!form.name.trim() && !form.email.trim() && !form.phone.trim())}
                className="bg-brand-500 hover:bg-brand-600 text-white font-semibold px-5 py-2 rounded-xl text-sm disabled:opacity-60">
                {saving ? 'Saving…' : 'Save customer'}
              </button>
            </div>
            <p className="text-[11px] text-gray-400 mt-2">Enter at least a name, email, or phone. Consent is stored for future campaigns — no messages are sent.</p>
          </div>
        )}

        {error && <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{error}</div>}

        {loading ? (
          <p className="text-gray-400 text-sm">Loading…</p>
        ) : (summary?.total_customers ?? 0) === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-100 p-12 text-center">
            <p className="text-4xl mb-3">🧑‍🤝‍🧑</p>
            <p className="text-gray-600 font-medium">No customers yet</p>
            <p className="text-gray-400 text-sm mt-1">Import a customer report (CSV/Excel) to segment your customers.</p>
          </div>
        ) : (
          <>
            {/* Totals */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4">
                <div className="flex items-center gap-2 text-gray-400 text-xs font-semibold uppercase tracking-wide mb-1"><Users size={13} /> Customers</div>
                <p className="text-xl font-bold text-gray-900">{summary.total_customers.toLocaleString()}</p>
              </div>
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4">
                <div className="text-gray-400 text-xs font-semibold uppercase tracking-wide mb-1">Customer value</div>
                <p className="text-xl font-bold text-gray-900">{money(summary.total_value)}</p>
              </div>
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4">
                <div className="flex items-center gap-2 text-gray-400 text-xs font-semibold uppercase tracking-wide mb-1"><MessageSquare size={13} /> SMS opted-in</div>
                <p className="text-xl font-bold text-gray-900">{summary.sms_opted_in.toLocaleString()}</p>
              </div>
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4">
                <div className="flex items-center gap-2 text-gray-400 text-xs font-semibold uppercase tracking-wide mb-1"><Mail size={13} /> Email opted-in</div>
                <p className="text-xl font-bold text-gray-900">{summary.email_opted_in.toLocaleString()}</p>
              </div>
            </div>

            {/* Segment cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
              {activeSegments.map((s) => (
                <button key={s.segment} onClick={() => setSegment(segment === s.segment ? null : s.segment)}
                  className={`text-left bg-white rounded-2xl border p-4 shadow-sm transition-colors ${
                    segment === s.segment ? 'border-brand-300 ring-2 ring-brand-100' : 'border-gray-100 hover:border-brand-200'
                  }`}>
                  <div className="flex items-center justify-between mb-2">
                    <Badge segment={s.segment} />
                    <span className="text-sm font-bold text-gray-900">{s.count}</span>
                  </div>
                  <p className="text-xs text-gray-400 mb-1">{money(s.total_spent)} lifetime value</p>
                  <p className="text-xs text-gray-600 leading-snug">{s.recommendation}</p>
                </button>
              ))}
            </div>

            {/* Filter bar */}
            <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
              <div className="flex items-center gap-2">
                {segment && (
                  <button onClick={() => setSegment(null)} className="text-xs font-semibold text-brand-500 hover:underline">
                    Clear filter: {segment} ✕
                  </button>
                )}
              </div>
              <form onSubmit={onSearch} className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input value={search} onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search name, email, phone"
                  className="w-64 border border-gray-200 rounded-xl pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </form>
            </div>

            {/* Customer table */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400 uppercase tracking-wide border-b border-gray-100">
                    <th className="px-4 py-3">Customer</th>
                    <th className="px-4 py-3 text-right">Last seen</th>
                    <th className="px-4 py-3 text-right">Visits</th>
                    <th className="px-4 py-3 text-right">Spend</th>
                    <th className="px-4 py-3">Segment</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400 text-sm">No customers match.</td></tr>
                  ) : rows.map((c) => (
                    <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-800 truncate">{c.name || c.email || c.phone || '—'}</p>
                        <p className="text-xs text-gray-400 truncate">{c.email || c.phone || ''}</p>
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600">
                        {c.recency_days != null ? `${c.recency_days}d ago` : '—'}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600">{c.purchase_count}</td>
                      <td className="px-4 py-3 text-right font-semibold text-gray-800">{money(c.total_spent)}</td>
                      <td className="px-4 py-3"><Badge segment={c.segment} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-[11px] text-gray-300 mt-3">
              Consent (SMS/email opt-in) is stored for future campaigns — no messages are sent yet.
            </p>
          </>
        )}
      </div>
    </Layout>
  )
}
