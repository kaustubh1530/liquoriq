/**
 * Transfers.jsx — Shared exchange ledger (Phase 14, shared model)
 *
 * Both stores must be on LiquorIQ. Flow:
 *   1. Your store's EXCHANGE CODE is shown — partners need it to add you
 *   2. Add a partner by entering THEIR code (mandatory). "Mutual" once they
 *      add you back — then both see the same shared history
 *   3. Select a partner → send/receive toggle, multiple items
 *   4. Every record shows who added it; undo asks to confirm and logs who removed it
 *   5. Balance, settlements (undo), month-by-month statement + CSV
 */

import { useEffect, useState } from 'react'
import { transferApi } from '../api/client'
import { useAuth } from '../context/AuthContext'
import Layout from '../components/Layout'
import {
  ArrowLeftRight, ArrowUpRight, ArrowDownLeft, Plus, Trash2,
  Scale, FileDown, Undo2, KeyRound, Link2, X, CheckCircle2, AlertCircle,
} from 'lucide-react'

const money = (v) => `$${Math.abs(Number(v)).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export default function Transfers() {
  const { user, store } = useAuth()
  const isOwner = user?.role !== 'staff'

  const [partners, setPartners] = useState([])
  const [partnerId, setPartnerId] = useState('')
  const partner = partners.find((p) => p.id === partnerId)
  const [showAdd, setShowAdd] = useState(false)
  const [newCode, setNewCode] = useState('')
  const [newName, setNewName] = useState('')
  const [addError, setAddError] = useState('')
  const [adding, setAdding] = useState(false)

  const [direction, setDirection] = useState('outgoing')
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [note, setNote] = useState('')
  const [items, setItems] = useState([{ product_name: '', quantity: '', unit_cost: '' }])
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const [ledger, setLedger] = useState(null)
  const [payments, setPayments] = useState([])
  const [history, setHistory] = useState([])
  const [settleAmount, setSettleAmount] = useState('')
  const [settleError, setSettleError] = useState('')

  const loadPartners = async () => {
    try { setPartners((await transferApi.partners()).data) } catch { /* empty */ }
  }
  useEffect(() => { loadPartners() }, [])

  const loadPartnerData = async () => {
    if (!partnerId) return
    try {
      const [l, p, h] = await Promise.all([
        transferApi.ledger(partnerId), transferApi.payments(partnerId), transferApi.list(partnerId),
      ])
      setLedger(l.data); setPayments(p.data); setHistory(h.data)
      setSettleAmount(Math.abs(l.data.balance).toFixed(2))
    } catch { /* empty */ }
  }
  useEffect(() => { setLedger(null); setPayments([]); setHistory([]); loadPartnerData() }, [partnerId])

  const addPartner = async () => {
    setAddError(''); setAdding(true)
    try {
      const { data } = await transferApi.addPartner(newCode.trim(), newName.trim() || null)
      setNewCode(''); setNewName(''); setShowAdd(false)
      await loadPartners(); setPartnerId(data.id)
    } catch (err) {
      setAddError(err.response?.data?.detail ?? 'Failed to add partner.')
    } finally { setAdding(false) }
  }

  const updateItem = (i, f, v) => setItems((r) => r.map((x, idx) => idx === i ? { ...x, [f]: v } : x))
  const addItem = () => setItems((r) => [...r, { product_name: '', quantity: '', unit_cost: '' }])
  const removeItem = (i) => setItems((r) => r.filter((_, idx) => idx !== i))

  const validItems = items
    .filter((r) => r.product_name.trim() && Number(r.quantity) > 0 && r.unit_cost !== '')
    .map((r) => ({ product_name: r.product_name.trim(), quantity: Number(r.quantity), unit_cost: Number(r.unit_cost) }))
  const formTotal = validItems.reduce((s, r) => s + r.quantity * r.unit_cost, 0)

  const submit = async () => {
    setFormError(''); setSaving(true)
    try {
      await transferApi.create({ partner_id: partnerId, direction, transfer_date: date, note: note || null, items: validItems })
      setItems([{ product_name: '', quantity: '', unit_cost: '' }]); setNote('')
      await loadPartnerData()
    } catch (err) {
      setFormError(err.response?.data?.detail ?? 'Failed to record the exchange.')
    } finally { setSaving(false) }
  }

  const undoTransfer = async (t) => {
    const label = `${t.direction === 'outgoing' ? 'Sent' : 'Received'} ${money(t.total)} on ${t.transfer_date}`
    if (!window.confirm(`Remove this exchange record?\n\n${label}\n\nThis will be logged with your name. Continue?`)) return
    try { await transferApi.undoTransfer(t.id); await loadPartnerData() } catch { /* noop */ }
  }

  const settle = async () => {
    setSettleError('')
    try {
      const payer = ledger.balance >= 0 ? 'me' : 'partner'
      await transferApi.settle(partnerId, { amount: Number(settleAmount), payer })
      await loadPartnerData()
    } catch (err) {
      setSettleError(err.response?.data?.detail ?? 'Failed to record payment.')
    }
  }

  const undoPayment = async (p) => {
    if (!window.confirm(`Undo this payment of ${money(p.amount)} on ${p.paid_on}?\n\nThis will be logged with your name.`)) return
    try { await transferApi.undoPayment(p.id); await loadPartnerData() } catch { /* noop */ }
  }

  const historyByMonth = history.reduce((acc, t) => {
    const m = t.transfer_date.slice(0, 7)
    ;(acc[m] = acc[m] || []).push(t)
    return acc
  }, {})

  return (
    <Layout>
      <div className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Transfers</h1>
        <p className="text-sm text-gray-500 mb-6">
          Shared exchange ledger with your partner stores — both sides see the same records
        </p>

        {/* Your exchange code */}
        {store?.exchange_code && (
          <div className="flex items-center gap-2 mb-6 text-xs text-gray-600 bg-amber-50 border border-amber-100 rounded-xl px-4 py-3">
            <KeyRound size={14} className="text-amber-500 shrink-0" />
            <span>
              <b>{store.name}</b>'s exchange code: <b className="font-mono tracking-widest text-gray-900 text-sm">{store.exchange_code}</b>
              &nbsp;— give it to a partner so they can add you.
            </span>
          </div>
        )}

        {/* Partners */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">Exchange with…</h2>
            <button onClick={() => setShowAdd(!showAdd)}
              className="flex items-center gap-1 text-xs font-semibold text-brand-500 hover:underline">
              {showAdd ? <X size={14} /> : <Plus size={14} />} {showAdd ? 'Cancel' : 'Add partner'}
            </button>
          </div>

          {showAdd && (
            <div className="mb-4 p-4 bg-gray-50 rounded-xl">
              {addError && <p className="text-xs text-red-500 mb-2">{addError}</p>}
              <div className="flex gap-2 flex-wrap">
                <input type="text" placeholder="Partner's exchange code (required)" value={newCode}
                  onChange={(e) => setNewCode(e.target.value.toUpperCase())}
                  className="w-56 border border-gray-200 rounded-xl px-3 py-2 text-sm font-mono tracking-wider focus:outline-none focus:ring-2 focus:ring-brand-500" />
                <input type="text" placeholder="Nickname (optional)" value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="flex-1 min-w-40 border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                <button onClick={addPartner} disabled={adding || newCode.trim().length < 4}
                  className="bg-brand-500 hover:bg-brand-600 text-white font-semibold px-4 py-2 rounded-xl text-sm disabled:opacity-60">
                  {adding ? 'Adding…' : 'Add'}
                </button>
              </div>
              <p className="text-[11px] text-gray-400 mt-2">
                Both stores must be on LiquorIQ. Enter the code your partner shares with you.
              </p>
            </div>
          )}

          {partners.length === 0 ? (
            <p className="text-sm text-gray-400">No partners yet — add a store using their exchange code.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {partners.map((p) => (
                <button key={p.id} onClick={() => setPartnerId(p.id)}
                  className={`flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-semibold border transition-colors ${
                    partnerId === p.id ? 'bg-brand-500 text-white border-brand-500'
                    : 'bg-white text-gray-700 border-gray-200 hover:border-brand-300'
                  }`}>
                  {p.name}
                  {p.mutual
                    ? <Link2 size={12} className={partnerId === p.id ? 'text-white/80' : 'text-green-500'} title="Linked both ways" />
                    : <AlertCircle size={12} className={partnerId === p.id ? 'text-white/80' : 'text-amber-400'} title="Waiting for them to add you back" />}
                </button>
              ))}
            </div>
          )}

          {partner && !partner.mutual && (
            <p className="text-[11px] text-amber-600 mt-3 flex items-center gap-1">
              <AlertCircle size={12} /> {partner.name} hasn't added {store?.name} back yet — they'll see this shared
              ledger once they enter your code ({store?.exchange_code}).
            </p>
          )}
        </div>

        {partner && (
          <>
            {/* Balance + settle + payments */}
            {ledger && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
                <div className="flex items-center gap-3 mb-3">
                  <Scale size={18} className="text-brand-500" />
                  <h2 className="text-sm font-semibold text-gray-700">Balance with {partner.name}</h2>
                </div>
                <div className={`p-4 rounded-xl mb-3 text-base font-bold ${
                  Math.abs(ledger.balance) < 0.01 ? 'bg-gray-50 text-gray-600'
                  : ledger.balance > 0 ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-700'
                }`}>
                  {Math.abs(ledger.balance) < 0.01 ? 'All settled ✓'
                    : ledger.balance > 0 ? `${store?.name} owes ${partner.name}: ${money(ledger.balance)}`
                    : `${partner.name} owes ${store?.name}: ${money(ledger.balance)}`}
                </div>

                {isOwner && Math.abs(ledger.balance) >= 0.01 && (
                  <div className="flex items-center gap-3 flex-wrap mb-3">
                    {settleError && <span className="text-xs text-red-500 w-full">{settleError}</span>}
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
                      <input type="number" min="0.01" step="0.01" value={settleAmount}
                        onChange={(e) => setSettleAmount(e.target.value)}
                        className="w-36 border border-gray-200 rounded-xl pl-7 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                    </div>
                    <button onClick={settle}
                      className="bg-gray-800 hover:bg-gray-900 text-white font-semibold px-4 py-2 rounded-xl text-sm">
                      Record payment ({ledger.balance > 0 ? `${store?.name} pays` : `${partner.name} pays`})
                    </button>
                  </div>
                )}

                {payments.length > 0 && (
                  <div className="border-t border-gray-50 pt-3 space-y-1.5">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Payments</p>
                    {payments.map((p) => (
                      <div key={p.id} className="flex items-center justify-between text-xs text-gray-600">
                        <span>
                          {p.paid_on} · {p.payer === 'me' ? `${store?.name} paid` : `${partner.name} paid`} {money(p.amount)}
                          {p.created_by_label && <span className="text-gray-300"> · by {p.created_by_label}</span>}
                        </span>
                        {isOwner && (
                          <button onClick={() => undoPayment(p)} title="Undo this payment"
                            className="flex items-center gap-1 text-gray-300 hover:text-red-400">
                            <Undo2 size={13} /> undo
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Record exchange */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
              <div className="flex items-center gap-3 mb-4">
                <ArrowLeftRight size={18} className="text-brand-500" />
                <h2 className="text-sm font-semibold text-gray-700">Record an exchange with {partner.name}</h2>
              </div>

              <div className="grid grid-cols-2 gap-2 mb-4">
                <button onClick={() => setDirection('outgoing')}
                  className={`flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold border transition-colors ${
                    direction === 'outgoing' ? 'bg-red-50 border-red-200 text-red-600'
                    : 'bg-white border-gray-200 text-gray-500 hover:border-gray-300'
                  }`}>
                  <ArrowUpRight size={16} /> We're sending
                </button>
                <button onClick={() => setDirection('incoming')}
                  className={`flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold border transition-colors ${
                    direction === 'incoming' ? 'bg-green-50 border-green-200 text-green-700'
                    : 'bg-white border-gray-200 text-gray-500 hover:border-gray-300'
                  }`}>
                  <ArrowDownLeft size={16} /> We're receiving
                </button>
              </div>

              {formError && <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{formError}</div>}

              <div className="mb-3">
                <label className="block text-xs text-gray-500 mb-1">Date</label>
                <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
                  className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>

              <div className="space-y-2 mb-3">
                {items.map((row, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input type="text" placeholder="Product name" value={row.product_name}
                      onChange={(e) => updateItem(i, 'product_name', e.target.value)}
                      className="flex-1 border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                    <input type="number" min="1" placeholder="Qty" value={row.quantity}
                      onChange={(e) => updateItem(i, 'quantity', e.target.value)}
                      className="w-20 border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
                      <input type="number" min="0" step="0.01" placeholder="Cost" value={row.unit_cost}
                        onChange={(e) => updateItem(i, 'unit_cost', e.target.value)}
                        className="w-28 border border-gray-200 rounded-xl pl-7 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                    </div>
                    <button onClick={() => removeItem(i)} className="text-gray-300 hover:text-red-400" title="Remove">
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>

              <input type="text" placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-brand-500" />

              <div className="flex items-center justify-between">
                <button onClick={addItem} className="flex items-center gap-1 text-xs font-semibold text-brand-500 hover:underline">
                  <Plus size={14} /> Add item
                </button>
                <div className="flex items-center gap-4">
                  <span className="text-sm font-bold text-gray-700">Total: {money(formTotal)}</span>
                  <button onClick={submit} disabled={saving || validItems.length === 0}
                    className="bg-brand-500 hover:bg-brand-600 text-white font-semibold px-5 py-2.5 rounded-xl text-sm disabled:opacity-60">
                    {saving ? 'Recording…' : direction === 'outgoing' ? 'Record — sending' : 'Record — receiving'}
                  </button>
                </div>
              </div>
            </div>

            {/* Monthly statement + downloads */}
            {ledger?.months?.length > 0 && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
                <h2 className="text-sm font-semibold text-gray-700 mb-3">Monthly statement</h2>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-400 uppercase tracking-wide">
                      <th className="text-left py-1">Month</th><th className="text-right">Sent</th>
                      <th className="text-right">Received</th><th className="text-right">Net</th><th className="text-right">Report</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ledger.months.map((m) => (
                      <tr key={m.month} className="border-t border-gray-50 text-gray-700">
                        <td className="py-2">{m.month}</td>
                        <td className="text-right">{money(m.sent)}</td>
                        <td className="text-right">{money(m.received)}</td>
                        <td className={`text-right font-semibold ${m.net > 0 ? 'text-red-500' : m.net < 0 ? 'text-green-600' : ''}`}>
                          {m.net > 0 ? '−' : m.net < 0 ? '+' : ''}{money(m.net)}
                        </td>
                        <td className="text-right">
                          <button onClick={() => transferApi.downloadReport(partnerId, m.month)}
                            className="inline-flex items-center gap-1 text-brand-500 hover:underline font-semibold">
                            <FileDown size={13} /> CSV
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Shared history with audit */}
            {Object.keys(historyByMonth).length > 0 && (
              <div className="mb-8">
                <h2 className="text-sm font-semibold text-gray-700 mb-3">Shared exchange history</h2>
                {Object.entries(historyByMonth).map(([month, rows]) => (
                  <div key={month} className="mb-4">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">{month}</p>
                    <div className="space-y-2">
                      {rows.map((t) => {
                        const outgoing = t.direction === 'outgoing'
                        return (
                          <div key={t.id}
                            className={`bg-white rounded-xl border px-4 py-3 flex items-center justify-between ${
                              t.is_deleted ? 'border-gray-100 opacity-60' : 'border-gray-100'
                            }`}>
                            <div className="flex items-center gap-3 min-w-0">
                              {outgoing ? <ArrowUpRight size={15} className="text-red-400 shrink-0" />
                                : <ArrowDownLeft size={15} className="text-green-500 shrink-0" />}
                              <div className="min-w-0">
                                <p className={`text-sm truncate ${t.is_deleted ? 'text-gray-400 line-through' : 'text-gray-800'}`}>
                                  {outgoing ? 'Sent' : 'Received'} · {t.transfer_date}
                                  <span className="text-gray-400"> · {t.items.length} item{t.items.length !== 1 ? 's' : ''}</span>
                                </p>
                                <p className="text-xs text-gray-400 truncate">
                                  {t.items.map((i) => `${i.product_name} ×${i.quantity}`).join(', ')}
                                </p>
                                <p className="text-[11px] text-gray-300 mt-0.5">
                                  {t.is_deleted
                                    ? `Removed by ${t.deleted_by_label ?? 'unknown'}`
                                    : t.created_by_label ? `Added by ${t.created_by_label}` : ''}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-3 shrink-0 ml-3">
                              <span className={`text-sm font-bold ${t.is_deleted ? 'text-gray-300 line-through' : outgoing ? 'text-red-500' : 'text-green-600'}`}>
                                {outgoing ? '−' : '+'}{money(t.total)}
                              </span>
                              {!t.is_deleted && (
                                <button onClick={() => undoTransfer(t)} title="Remove this record"
                                  className="text-gray-300 hover:text-red-400"><Undo2 size={15} /></button>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </Layout>
  )
}
