/**
 * Creative.jsx — MODULE 1: AI AD CREATOR (page)
 *
 * ONE job: generate a beautiful, finished advertisement. The AI paints the
 * scene, product and lighting; the server typesets the headline, exact price
 * and store name. Product details appear only when the campaign type calls for
 * them or the owner explicitly opts in.
 *
 * Promotional badges, stickers and price tags are NOT made here — that's the
 * Label Studio, a separate tool. This page just hands the finished ad over.
 *
 * PHASE 23.8 — this page no longer OWNS ad generation. Everything that was
 * state here now lives in useAdCreator, and the controls in AdCreatorForm,
 * because the Campaign Workspace generates ads too. What is left here is what
 * is genuinely this page's own: the strategy picker, and the handoff banner
 * explaining which campaign the form was filled from. The embedded section
 * cannot need a picker — on the workspace, the campaign IS the page.
 */

import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { aiApi } from '../api/client'
import Layout from '../components/Layout'
import AdCreatorForm from '../components/adcreator/AdCreatorForm'
import AdResult, { GeneratingCard } from '../components/adcreator/AdResult'
import useAdCreator from '../hooks/useAdCreator'
import { Palette } from 'lucide-react'

export default function Creative() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const preselected = searchParams.get('strategy')

  const [strategies, setStrategies] = useState([])
  // Fallback used only until the list loads and only when the URL names nothing.
  const [fallbackId, setFallbackId] = useState('')
  const [loadingList, setLoadingList] = useState(true)

  /**
   * THE URL IS THE SELECTION.
   *
   * Previously the strategy lived in component state seeded from the query
   * string. React Router reuses this component, so arriving from the AI
   * Advisor with a different ?strategy= did not re-run the initialiser and the
   * page kept showing the PREVIOUS campaign and its ad — the owner had to
   * re-pick the strategy the advisor had just named.
   *
   * Deriving it instead means the URL and the screen cannot disagree, a
   * refresh restores the same campaign, and the back button behaves. This stays
   * on the page that has a picker; the hook takes the id and asks no questions.
   */
  const selectedId = preselected || fallbackId
  const ad = useAdCreator(selectedId)
  const { context, creative, generating, error } = ad

  useEffect(() => {
    (async () => {
      try {
        const { data } = await aiApi.list()
        setStrategies(data)
        if (!preselected && data.length > 0) setFallbackId(data[0].id)
      } catch {
        // empty state shown below
      } finally {
        setLoadingList(false)
      }
    })()
  }, [preselected])

  const selectedStrategy = strategies.find((s) => s.id === selectedId)

  // Hand the finished ad to the Label Studio — a separate tool, not an edit
  // mode. The campaign rides along so labels saved there count towards it.
  const openLabelStudio = () =>
    navigate(`/labels?creative=${creative.id}&strategy=${selectedId}`)

  return (
    <Layout>
      <div className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">AI Ad Creator</h1>
        <p className="text-sm text-gray-500 mb-8">
          A finished, ready-to-post advertisement — scene, product, headline, your exact price and store name.
          Add promotional badges afterwards in <span className="font-medium">Label Studio</span>.
        </p>

        {/* ── Generate panel ── */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-8">
          <div className="flex items-center gap-3 mb-4">
            <Palette size={20} className="text-brand-500" />
            <h2 className="text-sm font-semibold text-gray-700">Create ad</h2>
          </div>

          {error && <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{error}</div>}

          {loadingList ? (
            <p className="text-gray-400 text-sm">Loading strategies…</p>
          ) : strategies.length === 0 ? (
            <p className="text-sm text-gray-500">
              No strategies yet — generate one on the <span className="font-medium">AI Strategy</span> page first.
            </p>
          ) : (
            <AdCreatorForm ad={ad}>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Campaign</label>
                <select
                  value={selectedId}
                  onChange={(e) => setSearchParams({ strategy: e.target.value })}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  {strategies.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.strategy_title} · {new Date(s.created_at).toLocaleDateString()}
                    </option>
                  ))}
                </select>
              </div>
            </AdCreatorForm>
          )}
        </div>

        {/* ── Result ── */}
        {generating && <div className="mb-8"><GeneratingCard /></div>}

        {/* THE HANDOFF, MADE VISIBLE.
            The owner has just been told what campaign to run. Showing him the
            same campaign here — goal, occasion, audience, offer — is what makes
            this feel like the next step in one conversation rather than a
            separate tool that happens to be open. */}
        {context && preselected && !generating && (
          <div className="bg-brand-50/50 ring-1 ring-brand-200 rounded-2xl p-5 mb-6">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold text-brand-700 uppercase tracking-wide">
                  This advertisement is based on your AI recommendation
                </p>
                <h3 className="text-base font-bold text-gray-900 mt-1">
                  {context.summary.campaign}
                </h3>
              </div>
              {!creative && (
                <span className="text-[11px] font-semibold px-3 py-1.5 rounded-full bg-white text-brand-700 ring-1 ring-brand-200 shrink-0">
                  Ready to generate
                </span>
              )}
            </div>

            <div className="grid sm:grid-cols-2 gap-x-6 gap-y-2.5 mt-4">
              {[
                ['Goal', context.summary.goal],
                ['Occasion', context.summary.occasion],
                ['Target audience', context.summary.audience],
                ['Recommended offer', context.summary.offer],
                ['Primary product', context.summary.primary_product],
                ['Expected outcome', context.summary.expected_outcome],
              ].filter(([, v]) => v).map(([label, value]) => (
                <div key={label} className="min-w-0">
                  <p className="text-[10px] text-gray-400 uppercase tracking-wide">{label}</p>
                  <p className="text-[12px] text-gray-800 leading-snug">{value}</p>
                </div>
              ))}
            </div>

            <p className="text-[11px] text-gray-500 mt-4 pt-3 border-t border-brand-200/60">
              The form below is filled in from this campaign. Change anything you
              like — your edits are kept.
            </p>
          </div>
        )}

        {!generating && (
          <AdResult creative={creative} onAddLabels={openLabelStudio}
            title={selectedStrategy?.strategy_title} />
        )}
      </div>
    </Layout>
  )
}
