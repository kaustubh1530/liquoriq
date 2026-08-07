/**
 * pages/campaign/CampaignLabelsSection.jsx — PHASE 23.8: labels, in the campaign.
 *
 * The Phase 23.7 handoff called embedding Label Studio "a phase" — it is a
 * canvas editor with its own state machine, and the tempting shortcut was a
 * cut-down editor here. That would have been a second layout engine: the server
 * renders the preview AND reports the box it drew each element into, and a
 * simplified client-side stand-in would have drifted from the printer the first
 * time either side changed. So this is the SAME editor — useLabelStudio and
 * LabelEditor, shared with the page — with two differences:
 *
 *   · the library lists only this campaign's labels, which the strategy_id
 *     migration made possible, and
 *   · new labels are stamped with this campaign, so the progress step and the
 *     download package both know what belongs here.
 *
 * onSaved re-reads the workspace. The section never marks the step done itself:
 * the server counts the rows.
 */

import { useState } from 'react'
import { ChevronDown, ChevronUp, Tag } from 'lucide-react'
import { Link } from 'react-router-dom'
import LabelEditor, { EditorTools } from '../../components/labelstudio/LabelEditor'
import LabelLibrary from '../../components/labelstudio/LabelLibrary'
import useLabelStudio from '../../hooks/useLabelStudio'

export default function CampaignLabelsSection({ strategyId, onSaved }) {
  const studio = useLabelStudio({ strategyId, scopeToStrategy: true, onSaved })
  const { loading, error, options, spec, labels } = studio

  /**
   * The editor starts folded.
   *
   * It is the biggest thing on this page by a wide margin, and the workspace's
   * job is to show the owner where he is. Folded, he sees his labels and the
   * pipeline; opened, he has the whole studio without leaving the campaign.
   * Open by default when there are no labels yet — then the editor IS the
   * next thing to do.
   */
  const [open, setOpen] = useState(false)
  const editing = open || (!loading && labels.length === 0)

  return (
    <section id="section-labels"
      className="bg-white rounded-3xl ring-1 ring-slate-200/70 p-6 scroll-mt-6">
      <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
        <div>
          <h2 className="text-[15px] font-bold text-slate-900 flex items-center gap-2">
            <Tag size={15} className="text-brand-500" /> Shelf labels
          </h2>
          <p className="text-[12px] text-slate-500 mt-0.5">
            {labels.length
              ? `${labels.length} for this campaign · tick them to print a sheet`
              : 'The printed card for the shelf edge. Anything you save here counts towards this campaign.'}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {editing && <EditorTools studio={studio} />}
          <Link to={`/labels?strategy=${strategyId}`}
            className="text-[11px] font-medium text-slate-400 hover:text-slate-700">
            Open Label Studio
          </Link>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{error}</div>
      )}

      {loading ? (
        <div className="h-40 bg-slate-100 rounded-2xl animate-pulse" />
      ) : (
        <>
          {labels.length > 0 && (
            <button onClick={() => setOpen(!open)}
              className="text-xs font-medium text-gray-400 hover:text-gray-600 flex items-center gap-1 mb-4">
              {editing ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              {editing ? 'Hide the editor' : 'Design another label'}
            </button>
          )}

          {editing && options && spec && (
            <div className="mb-8">
              <LabelEditor studio={studio} compact />
            </div>
          )}

          <LabelLibrary studio={studio} title="Labels for this campaign"
            emptyHint="None for this campaign yet — design one above and hit Save." />
        </>
      )}
    </section>
  )
}
