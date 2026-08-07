/**
 * pages/campaign/CampaignAdSection.jsx — PHASE 23.8: the ad, inside the campaign.
 *
 * Phase 23.7 linked out to /creative. The pipeline carried the campaign with
 * it, so the workflow was continuous — but the owner still left the page that
 * was supposed to be showing him his campaign in order to make the biggest
 * piece of it.
 *
 * This section is the SAME Ad Creator, not a smaller one: the state comes from
 * useAdCreator and the controls from AdCreatorForm, both shared with the
 * standalone page. The only differences are presentational — no strategy picker
 * (here, the campaign IS the page) and the art direction folded away.
 *
 * When an ad lands it calls onGenerated, which makes the workspace re-read
 * GET /workspace/{id}. It reports THAT something happened, never what: progress
 * is computed server-side from the real assets, and a section that flipped its
 * own "ad done" flag here would start exactly the drift Phase 23.7 was designed
 * to make impossible.
 */

import { Link, useNavigate } from 'react-router-dom'
import { Palette } from 'lucide-react'
import AdCreatorForm from '../../components/adcreator/AdCreatorForm'
import AdResult, { GeneratingCard } from '../../components/adcreator/AdResult'
import useAdCreator from '../../hooks/useAdCreator'

export default function CampaignAdSection({ strategyId, onGenerated }) {
  const ad = useAdCreator(strategyId, { onGenerated })
  const { creative, generating, error, context } = ad
  const navigate = useNavigate()

  // Scroll to the labels section if this page has one, and fall back to the
  // Label Studio if it does not. The button must never be a dead click.
  const addLabels = () => {
    const section = document.getElementById('section-labels')
    if (section) section.scrollIntoView({ behavior: 'smooth' })
    else navigate(`/labels?creative=${creative.id}&strategy=${strategyId}`)
  }

  return (
    <section id="section-ad"
      className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-6 scroll-mt-6">
      <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
        <div>
          <h2 className="text-[15px] font-bold text-slate-900 flex items-center gap-2">
            <Palette size={15} className="text-brand-500" /> Advertisement
          </h2>
          <p className="text-[12px] text-slate-500 mt-0.5">
            {creative
              ? 'Regenerate it, or change the price and try again — your edits are kept.'
              : 'Filled in from this campaign. Change anything you like before generating.'}
          </p>
        </div>
        <Link to={`/creative?strategy=${strategyId}`}
          className="text-[11px] font-medium text-slate-400 hover:text-slate-700 shrink-0">
          Open in Ad Creator
        </Link>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{error}</div>
      )}

      {/* The prefill, said out loud. The owner should be able to see WHY the
          form looks like this without opening another page. */}
      {context?.reasons?.campaign_type && !creative && (
        <p className="text-[11px] text-slate-400 mb-3">
          Set to {context.prefill?.campaign_type?.replace('_', ' ')} because{' '}
          {context.reasons.campaign_type}.
        </p>
      )}

      <AdCreatorForm ad={ad} compact />

      {generating && <div className="mt-6"><GeneratingCard /></div>}
      {!generating && creative && (
        <div className="mt-6">
          <AdResult creative={creative} compact onAddLabels={addLabels} />
        </div>
      )}
    </section>
  )
}
