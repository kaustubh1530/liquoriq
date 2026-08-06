/**
 * AIAdvisor.jsx — PHASE 23: the AI Business Advisor.
 *
 * THIS IS NOT A CHAT WINDOW WITH A ROBOT IN IT.
 *
 * The difference is visible in three places:
 *
 *   1. THE ADVISOR SPEAKS FIRST. The page opens with today's briefing, before
 *      the owner has typed anything. A blank chat box asks him to know what to
 *      ask, which is the job he's paying us to do.
 *
 *   2. IT ALREADY KNOWS HIS SHOP. No "tell me about your inventory". The
 *      context panel shows exactly what it walked in holding.
 *
 *   3. EVERY ANSWER SHOWS ITS SOURCES. Not a claim — the tools that actually
 *      ran, recorded server-side while they executed. An owner can't audit a
 *      language model, but he can audit a citation.
 *
 * The markdown renderer is deliberately small and local: the answers use six
 * fixed headings from a prompt we control, so a full markdown dependency would
 * be weight for nothing.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Brain, Send, Loader2, Sparkles, Database, Plus, Trash2, MessageSquare,
  Boxes, Users, Palette, Tag, ChevronDown, ChevronUp, Wrench, ArrowRight,
} from 'lucide-react'
import { advisorApi } from '../api/client'
import Layout from '../components/Layout'
import { useAuth } from '../context/AuthContext'
import { greeting } from './dashboard/summary'

/** Friendly names for the tools, so the citation list reads like a person. */
const TOOL_LABEL = {
  inventory_intelligence: 'Your inventory',
  category_intelligence: 'Category performance',
  action_center: 'Your recommendations',
  reorder_list: 'Reorder list',
  customer_segments: 'Customer segments',
  campaign_performance: 'Campaign results',
  ai_strategies: 'Past campaigns',
  upcoming_holidays: 'Holiday calendar',
  supplier_deals: 'Supplier deals',
  revenue_trend: 'Revenue history',
  product_lookup: 'Product lookup',
}

const QUICK_ACTIONS = [
  { to: '/ai', label: 'Generate campaign', icon: Sparkles },
  { to: '/inventory', label: 'Open inventory', icon: Boxes },
  { to: '/customers', label: 'View customers', icon: Users },
  { to: '/creative', label: 'Create ad', icon: Palette },
  { to: '/labels', label: 'Create labels', icon: Tag },
]

/**
 * Minimal markdown: the six headings the prompt asks for, bullets, bold.
 * Enough for a contract we control, and nothing more.
 */
function Markdown({ text }) {
  const blocks = []
  let list = []

  const flush = (key) => {
    if (list.length) {
      blocks.push(
        <ul key={`ul-${key}`} className="space-y-1.5 my-2">
          {list.map((item, i) => (
            <li key={i} className="flex gap-2 text-[13px] text-slate-700 leading-relaxed">
              <span className="text-slate-300 mt-0.5">•</span>
              <span dangerouslySetInnerHTML={{ __html: inline(item) }} />
            </li>
          ))}
        </ul>
      )
      list = []
    }
  }

  const inline = (s) => s
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-slate-900">$1</strong>')

  ;(text ?? '').split('\n').forEach((raw, i) => {
    const line = raw.trim()
    if (!line) { flush(i); return }

    if (line.startsWith('## ')) {
      flush(i)
      blocks.push(
        <h3 key={i} className="text-[11px] font-bold text-slate-400 uppercase tracking-wide mt-5 first:mt-0 mb-2">
          {line.slice(3)}
        </h3>
      )
    } else if (/^[-*•]\s/.test(line)) {
      list.push(line.replace(/^[-*•]\s/, ''))
    } else if (/^(P[123]|\d+)[.)]\s/.test(line)) {
      flush(i)
      const [, tag, rest] = line.match(/^(P[123]|\d+)[.)]\s(.*)$/)
      blocks.push(
        <p key={i} className="flex gap-2.5 text-[13px] text-slate-700 leading-relaxed my-1.5">
          <span className="shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-900 text-white h-fit mt-0.5">
            {tag}
          </span>
          <span dangerouslySetInnerHTML={{ __html: inline(rest) }} />
        </p>
      )
    } else {
      flush(i)
      blocks.push(
        <p key={i} className="text-[13px] text-slate-700 leading-relaxed my-1.5"
          dangerouslySetInnerHTML={{ __html: inline(line) }} />
      )
    }
  })
  flush('end')
  return <div>{blocks}</div>
}

/**
 * The buttons under an answer. Derived server-side from the tools the advisor
 * actually used, so a route can never be one the model imagined.
 */
function NextActions({ actions }) {
  if (!actions?.length) return null
  return (
    <div className="flex flex-wrap gap-2 mt-4">
      {actions.map((a) => (
        <Link key={a.route} to={a.route}
          className="inline-flex items-center gap-1.5 text-[12px] font-semibold px-3.5 py-2 rounded-xl bg-slate-900 text-white hover:bg-slate-700 transition-colors">
          {a.label} <ArrowRight size={12} />
        </Link>
      ))}
    </div>
  )
}

function Sources({ tools }) {
  const [open, setOpen] = useState(false)
  if (!tools?.length) return null

  return (
    <div className="mt-4 pt-3 border-t border-slate-100">
      <button onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400 hover:text-slate-700">
        <Database size={11} />
        Business data used ({tools.length})
        {open ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
      </button>
      {open && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {tools.map((t, i) => (
            <span key={i}
              className={`text-[10px] font-medium px-2 py-1 rounded-lg ${
                t.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
              {TOOL_LABEL[t.tool] ?? t.tool}
              {t.arguments?.category && ` · ${t.arguments.category}`}
              {t.arguments?.stock_class && ` · ${t.arguments.stock_class}`}
              {!t.ok && ' (unavailable)'}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function AIAdvisor() {
  const { user } = useAuth()
  const firstName = (user?.full_name ?? '').trim().split(' ')[0] || 'there'

  const [brief, setBrief] = useState(null)
  const [suggestions, setSuggestions] = useState([])
  const [conversations, setConversations] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [thinking, setThinking] = useState(false)
  const [briefLoading, setBriefLoading] = useState(true)
  const bottomRef = useRef(null)

  const loadConversations = useCallback(() => {
    advisorApi.conversations()
      .then((r) => setConversations(r.data.conversations ?? []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    advisorApi.suggestions()
      .then((r) => setSuggestions(r.data.suggestions ?? []))
      .catch(() => {})
    advisorApi.brief()
      .then((r) => setBrief(r.data))
      .catch(() => setBrief({ brief: 'I could not reach my reasoning engine. '
                                     + 'Your dashboard is still up to date.' }))
      .finally(() => setBriefLoading(false))
    loadConversations()
  }, [loadConversations])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  const send = async (text) => {
    const q = (text ?? question).trim()
    if (!q || thinking) return

    setQuestion('')
    setMessages((prev) => [...prev, { role: 'user', content: q }])
    setThinking(true)

    try {
      const { data } = await advisorApi.ask(q, conversationId)
      setConversationId(data.conversation_id)
      setMessages((prev) => [...prev, {
        role: 'assistant', content: data.answer, tools_used: data.tools_used,
        next_actions: data.next_actions,
        // Shown when the model was unreachable. A friendly message with no
        // cause is undebuggable — that is how an ImportError hid for a session.
        error: data.error,
      }])
      loadConversations()
    } catch {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: "I couldn't reach my reasoning engine just then. Your dashboard "
                 + 'and Business Intelligence page are still accurate — everything '
                 + 'there is calculated without AI.',
      }])
    } finally { setThinking(false) }
  }

  const openConversation = async (id) => {
    try {
      const { data } = await advisorApi.conversation(id)
      setConversationId(id)
      setMessages(data.messages ?? [])
    } catch { /* noop */ }
  }

  const newConversation = () => {
    setConversationId(null)
    setMessages([])
  }

  const remove = async (id, e) => {
    e.stopPropagation()
    try {
      await advisorApi.deleteConversation(id)
      if (id === conversationId) newConversation()
      loadConversations()
    } catch { /* noop */ }
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto grid lg:grid-cols-[1fr_240px] gap-6 pb-10">

        {/* ── Main column ─────────────────────────────────────────────── */}
        <div className="min-w-0 space-y-5">

          {/* Today's business brief — the advisor speaks first. */}
          <section className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-7">
            <div className="flex items-center gap-2.5 mb-4">
              <span className="w-8 h-8 rounded-xl bg-white/10 flex items-center justify-center">
                <Brain size={16} className="text-white" />
              </span>
              <div>
                <p className="text-[13px] font-semibold text-white">
                  {greeting()}, {firstName}
                </p>
                <p className="text-[11px] text-slate-400">Today’s business brief</p>
              </div>
              {brief?.health_score != null && (
                <span className="ml-auto text-[11px] font-semibold px-2.5 py-1 rounded-full bg-white/10 text-white">
                  Health {Math.round(brief.health_score)}/100
                </span>
              )}
            </div>

            {briefLoading ? (
              <p className="flex items-center gap-2 text-[13px] text-slate-400">
                <Loader2 size={13} className="animate-spin" /> Reading your numbers…
              </p>
            ) : (
              <>
                {brief?.signals?.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-4">
                    {brief.signals.map((sig) => (
                      <span key={sig.headline} title={sig.detail}
                        className={`text-[11px] font-medium px-2.5 py-1 rounded-full ring-1 ${
                          sig.urgency === 1
                            ? 'bg-red-500/15 text-red-200 ring-red-400/20'
                            : sig.urgency === 2
                              ? 'bg-amber-500/15 text-amber-200 ring-amber-400/20'
                              : 'bg-white/10 text-slate-200 ring-white/10'}`}>
                        {sig.headline}
                      </span>
                    ))}
                  </div>
                )}
                <p className="text-[14px] leading-relaxed text-slate-100 whitespace-pre-line">
                  {brief?.brief}
                </p>
                {brief?.source === 'deterministic' && (
                  <>
                    <p className="text-[11px] text-slate-500 mt-3">
                      Written from your figures without AI — the model was unavailable.
                    </p>
                    {brief?.error && (
                      <p className="text-[11px] font-mono text-red-300 mt-1">{brief.error}</p>
                    )}
                  </>
                )}
              </>
            )}
          </section>

          {/* Conversation */}
          <div className="space-y-4">
            {messages.map((m, i) => (
              m.role === 'user' ? (
                <div key={i} className="flex justify-end">
                  <p className="max-w-[80%] text-[13px] px-4 py-2.5 rounded-2xl rounded-br-md bg-slate-900 text-white">
                    {m.content}
                  </p>
                </div>
              ) : (
                <div key={i} className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-6">
                  <Markdown text={m.content} />
                  <NextActions actions={m.next_actions} />
                  {m.error && (
                    <p className="mt-3 text-[11px] font-mono text-red-600 bg-red-50 rounded-lg px-3 py-2">
                      {m.error}
                    </p>
                  )}
                  <Sources tools={m.tools_used} />
                </div>
              )
            ))}

            {thinking && (
              <div className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-6">
                <p className="flex items-center gap-2 text-[13px] text-slate-500">
                  <Wrench size={13} className="animate-pulse" />
                  Checking your inventory, categories and campaigns…
                </p>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Suggestions — only before the first question. */}
          {messages.length === 0 && suggestions.length > 0 && (
            <div>
              <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide mb-2.5">
                Ask me anything about your store
              </p>
              <div className="flex flex-wrap gap-2">
                {suggestions.map((s) => (
                  <button key={s.key} onClick={() => send(s.question)}
                    className="text-[12px] font-medium px-3.5 py-2 rounded-xl bg-white ring-1 ring-slate-200 text-slate-700 hover:ring-slate-900 hover:text-slate-900 transition-all">
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Composer */}
          <div className="sticky bottom-4">
            <div className="flex items-end gap-2 bg-white rounded-2xl ring-1 ring-slate-200 p-2 shadow-sm">
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
                }}
                rows={1}
                placeholder="Why are tequila sales down? What should I reorder first?"
                className="flex-1 resize-none text-[13px] px-3 py-2.5 focus:outline-none max-h-32"
              />
              <button onClick={() => send()} disabled={thinking || !question.trim()}
                className="shrink-0 w-10 h-10 rounded-xl bg-slate-900 text-white flex items-center justify-center disabled:opacity-30 hover:bg-slate-700 transition-colors">
                {thinking ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
              </button>
            </div>
          </div>
        </div>

        {/* ── Sidebar ─────────────────────────────────────────────────── */}
        <aside className="space-y-5">
          <button onClick={newConversation}
            className="w-full flex items-center justify-center gap-2 text-[12px] font-semibold px-3 py-2.5 rounded-xl bg-white ring-1 ring-slate-200 text-slate-700 hover:ring-slate-900">
            <Plus size={13} /> New conversation
          </button>

          <div>
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
              Quick actions
            </p>
            <div className="space-y-1">
              {QUICK_ACTIONS.map((a) => (
                <Link key={a.to} to={a.to}
                  className="flex items-center gap-2 text-[12px] text-slate-600 hover:text-slate-900 hover:bg-white rounded-lg px-2.5 py-2 transition-colors">
                  <a.icon size={13} className="text-slate-400" /> {a.label}
                </Link>
              ))}
            </div>
          </div>

          {conversations.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
                History
              </p>
              <div className="space-y-1">
                {conversations.map((c) => (
                  <button key={c.id} onClick={() => openConversation(c.id)}
                    className={`group w-full flex items-start gap-2 text-left rounded-lg px-2.5 py-2 transition-colors ${
                      c.id === conversationId ? 'bg-white ring-1 ring-slate-200' : 'hover:bg-white'
                    }`}>
                    <MessageSquare size={12} className="text-slate-400 mt-0.5 shrink-0" />
                    <span className="flex-1 min-w-0">
                      <span className="block text-[12px] text-slate-700 truncate">{c.title}</span>
                      <span className="block text-[10px] text-slate-400">
                        {c.message_count} messages
                      </span>
                    </span>
                    <span onClick={(e) => remove(c.id, e)}
                      className="opacity-0 group-hover:opacity-100 text-slate-300 hover:text-red-500 shrink-0">
                      <Trash2 size={12} />
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    </Layout>
  )
}
