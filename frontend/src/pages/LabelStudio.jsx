/**
 * LabelStudio.jsx — MODULE 2: LABEL STUDIO (page)
 *
 * Shelf labels: the printed card clipped to the shelf edge. Modelled on the
 * tags the store already makes in Canva (serif, black on white, red sale price,
 * starburst, REGULAR / SAVE).
 *
 * A label is a list of MOVABLE elements. Styles are one-click starting points,
 * not cages: every piece can be dragged, edited, recoloured, duplicated or
 * deleted. The server renders the preview AND reports where it drew each
 * element, so the drag handles line up exactly with the print.
 *
 * PHASE 23.8 — the editor's state now lives in useLabelStudio and its panels in
 * LabelEditor/LabelLibrary, because the Campaign Workspace embeds the same
 * editor. This page is what remains that is genuinely a PAGE: the heading, the
 * dashboard-action banner, and the campaign notice when one sent us here.
 */

import { useEffect, useRef, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import Layout from '../components/Layout'
import FromActionBanner from '../components/FromActionBanner'
import LabelEditor, { EditorTools } from '../components/labelstudio/LabelEditor'
import LabelLibrary from '../components/labelstudio/LabelLibrary'
import useLabelStudio from '../hooks/useLabelStudio'
import { Tag } from 'lucide-react'

export default function LabelStudio() {
  /**
   * PHASE 23.8 — arriving from a campaign (`?strategy=…`).
   *
   * Read from the URL rather than held in state, for the same reason as the Ad
   * Creator: React Router reuses this component, so state seeded once would
   * keep stamping labels with the PREVIOUS campaign after arriving here from a
   * different one.
   *
   * The library still lists EVERY label on this page — it is the store's label
   * drawer, not one campaign's. The campaign only decides what a new label is
   * stamped with. The workspace section is the place that shows one campaign's.
   */
  const [searchParams] = useSearchParams()
  const campaignId = searchParams.get('strategy')

  const studio = useLabelStudio({ strategyId: campaignId })
  const { loading, error, options, spec, setProductQuery } = studio

  /**
   * Arriving from a bundle or upsell recommendation. The products it named are
   * dropped into the search box, so the list below is already narrowed to the
   * bottles the owner came here to make labels for instead of all 1,400.
   *
   * Only the FIRST name is used as the query — the search filters one term,
   * and the banner shows the rest so nothing is silently lost.
   */
  const location = useLocation()
  const applied = useRef(false)
  const [incoming, setIncoming] = useState(null)

  useEffect(() => {
    const from = location.state?.fromAction
    if (!from || applied.current) return
    applied.current = true
    setIncoming(from)
    const first = (from.products ?? [])[0]
    if (first) setProductQuery(first)
  }, [location.state, setProductQuery])

  if (loading) return <Layout><p className="text-sm text-gray-400">Loading Label Studio…</p></Layout>
  if (!options || !spec) {
    return <Layout><div className="max-w-xl bg-red-50 text-red-600 rounded-xl p-4 text-sm">
      {error || 'Label Studio is unavailable.'}</div></Layout>
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto">
        <FromActionBanner action={incoming} onDismiss={() => setIncoming(null)} />

        <div className="flex items-start justify-between gap-4 flex-wrap mb-5">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 mb-1 flex items-center gap-2">
              <Tag size={20} className="text-brand-500" /> Label Studio
            </h1>
            <p className="text-sm text-gray-500">
              Click a piece to edit it · drag to move · Delete key removes it
            </p>
            {campaignId && (
              <p className="text-[11px] font-medium text-brand-600 mt-1.5">
                Labels you save here count towards the campaign you came from.
              </p>
            )}
          </div>
          <EditorTools studio={studio} />
        </div>

        {error && <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{error}</div>}

        <LabelEditor studio={studio} />

        <div className="mt-10">
          <LabelLibrary studio={studio} />
        </div>
      </div>
    </Layout>
  )
}
