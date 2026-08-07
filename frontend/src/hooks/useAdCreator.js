/**
 * hooks/useAdCreator.js — PHASE 23.8: ad generation, owned in one place.
 *
 * THE PROBLEM THIS SOLVES
 *
 * The Campaign Workspace needs to generate an advertisement inside the page.
 * The obvious way to get there is to write a smaller Ad Creator into the
 * workspace — and then there are two ad generators, and the day someone adds a
 * field to one of them the other quietly keeps sending the old payload. The ad
 * is the most expensive thing this product makes (40-60 seconds and a paid
 * image call); two code paths to it is two ways for it to come out wrong.
 *
 * So the state moved OUT of Creative.jsx and into here. The standalone page and
 * the embedded section both call this hook. Neither owns anything the other
 * needs, so there is nothing to keep in sync.
 *
 * WHERE THE CAMPAIGN COMES FROM
 *
 * Always the server: creativeApi.campaignContext(strategyId). Never a prop.
 *
 * The workspace has already fetched a copy of the campaign context inside
 * GET /workspace/{id}, so passing it down would save a request. It would also
 * make the ad form fill itself from a snapshot taken when the workspace loaded,
 * and that snapshot would become a second, ageing supply line for prefills
 * alongside the one CampaignContext was built to be. The context endpoint is
 * pure mapping — no model call, no calculation — so the second request costs
 * almost nothing, and it buys a rule that cannot rot: one consumer, one fetch.
 *
 * The hook never reads the URL either. The standalone page passes
 * ?strategy=; the workspace passes its route param. Both get the same
 * behaviour, and the "URL is the selection" fix from Phase 23.6 stays where it
 * belongs — on the page that has a strategy picker.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { creativeApi } from '../api/client'

// Campaign types where customer-facing product details earn their place on the
// ad. Everything else stays clean and minimal unless the owner opts in.
// Exported so both renderings label them identically.
export const CAMPAIGN_TYPES = [
  { v: 'standard',           label: 'Standard promotion', details: false },
  { v: 'new_arrival',        label: 'New arrival',        details: true },
  { v: 'product_spotlight',  label: 'Product spotlight',  details: true },
  { v: 'premium_collection', label: 'Premium collection', details: true },
  { v: 'limited_edition',    label: 'Limited edition',    details: true },
]

export const AD_LAYOUTS = [
  { v: 'auto', label: 'Auto' },
  { v: 'poster', label: 'Poster' },
  { v: 'band', label: 'Bottom band' },
  { v: 'rail', label: 'Side column' },
  { v: 'banner', label: 'Top banner' },
]

export const AD_FORMATS = [
  { v: 'square', label: 'Square' },
  { v: 'portrait', label: 'Portrait' },
  { v: 'landscape', label: 'Landscape' },
]

const EMPTY = {
  offer: '',           // the exact promo price/offer to render
  instructions: '',    // owner art-direction hints
  productUrl: '',      // real bottle photo
  format: 'square',
  category: '',
  layout: 'auto',
  campaignType: 'standard',
  wantDetails: false,  // owner opt-in for product details
  factsText: '',       // one "key: value" per line
}

/** The "key: value" lines as an object — only confirmed, owner-entered facts. */
export function parseFacts(factsText) {
  const facts = {}
  for (const line of (factsText || '').split('\n')) {
    const i = line.indexOf(':')
    if (i > 0) {
      const k = line.slice(0, i).trim().toLowerCase().replace(/\s+/g, '_')
      const v = line.slice(i + 1).trim()
      if (k && v) facts[k] = v
    }
  }
  return facts
}

/**
 * @param {string|null} strategyId  the campaign, from wherever the caller got it
 * @param {object}  opts
 * @param {function} opts.onGenerated  called after a successful generation, so
 *   the workspace can re-read its state. It is told THAT something landed, not
 *   what — progress is computed server-side from the real assets, and a caller
 *   that set its own "ad done" flag here would start the drift Phase 23.7 spent
 *   its whole design avoiding.
 */
export default function useAdCreator(strategyId, { onGenerated } = {}) {
  /**
   * The form, and the fields the owner has edited, in ONE piece of state.
   *
   * `touched` is the whole "preserve edits" mechanism: prefill writes a field
   * only if it is not in there. Without it, coming back to the page would
   * silently overwrite a price he had just corrected — worse than never
   * prefilling at all, because he would not notice.
   *
   * It sits beside the values rather than in a ref so that the prefill can read
   * it inside a functional update — no dependency on the current edits, so
   * prefill never re-runs while he is typing, and no ref read during render.
   */
  const [form, setForm] = useState({ values: EMPTY, touched: [] })
  const values = form.values
  const [context, setContext] = useState(null)
  const [creative, setCreative] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [loading, setLoading] = useState(Boolean(strategyId))
  const [error, setError] = useState('')

  const setField = useCallback((field, value) => {
    setForm((f) => ({
      values: { ...f.values, [field]: value },
      touched: f.touched.includes(field) ? f.touched : [...f.touched, field],
    }))
  }, [])

  /**
   * A different campaign is a different form.
   *
   * Reset DURING RENDER rather than in an effect. An effect would let one frame
   * paint with the previous campaign's ad sitting under this campaign's name —
   * brief, but it is a picture of the wrong bottle at the wrong price, and the
   * owner has no way to know he saw a stale frame. React re-renders immediately
   * on a set during render and never commits the in-between state.
   */
  const [renderedFor, setRenderedFor] = useState(strategyId)
  if (renderedFor !== strategyId) {
    setRenderedFor(strategyId)
    setForm({ values: EMPTY, touched: [] })
    setContext(null)
    setCreative(null)
    setError('')
    setLoading(Boolean(strategyId))
  }

  // The latest ad for this campaign (404 = none generated yet, which is fine).
  useEffect(() => {
    if (!strategyId) return
    let cancelled = false
    creativeApi.get(strategyId)
      .then(({ data }) => { if (!cancelled) setCreative(data) })
      .catch(() => { /* no creative yet */ })
    return () => { cancelled = true }
  }, [strategyId])

  /**
   * The campaign context, and the form filled from it.
   *
   * The owner already told the advisor what campaign to run. Asking him to
   * describe it again — type, layout, offer, look and feel — is the system
   * forgetting a conversation it just had.
   */
  useEffect(() => {
    if (!strategyId) return
    let cancelled = false

    creativeApi.campaignContext(strategyId)
      .then(({ data }) => {
        if (cancelled) return
        setContext(data)
        const pre = data.prefill ?? {}

        // Read `touched` from the update itself: whatever he has typed by the
        // time this lands is respected, without prefill depending on it.
        setForm((f) => {
          const next = { ...f.values }
          const fill = (field, value) => {
            if (!f.touched.includes(field) && value) next[field] = value
          }
          fill('offer', pre.offer)
          fill('instructions', pre.instructions)
          fill('campaignType', pre.campaign_type)
          fill('layout', pre.layout)
          fill('format', pre.image_format)
          fill('category', pre.category)
          fill('productUrl', pre.product_url)
          if (!f.touched.includes('factsText') && pre.facts
              && Object.keys(pre.facts).length) {
            next.factsText = Object.entries(pre.facts)
              .map(([k, v]) => `${k}: ${v}`).join('\n')
          }
          // Details are switched on only when there is something to put in them.
          if (!f.touched.includes('wantDetails') && pre.show_details) {
            next.wantDetails = true
          }
          return { ...f, values: next }
        })
      })
      .catch(() => { /* no context — the form stays manual, which still works */ })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [strategyId])

  // The hero product comes from the context rather than from a separate lookup.
  // The page used to fetch the saved photo and facts a second time, directly
  // from the library, and that second write was NOT guarded by `touched` — it
  // could overwrite an edit. One supply line removes the bug with the duplicate.
  const heroProduct = context?.summary?.primary_product ?? ''

  const autoDetails = useMemo(
    () => CAMPAIGN_TYPES.find((c) => c.v === values.campaignType)?.details ?? false,
    [values.campaignType],
  )
  const detailsOn = autoDetails || values.wantDetails

  const generate = useCallback(async () => {
    if (!strategyId) return null
    setError('')
    setGenerating(true)
    try {
      const facts = parseFacts(values.factsText)
      if (heroProduct && Object.keys(facts).length) {
        try {
          await creativeApi.saveFacts(heroProduct, values.category.trim() || null, facts)
        } catch { /* the ad matters more than the library write */ }
      }
      const { data } = await creativeApi.generate(strategyId, {
        offerOverride: values.offer.trim() || null,
        instructions: values.instructions.trim() || null,
        productImageUrl: values.productUrl || null,
        imageFormat: values.format,
        productFacts: Object.keys(facts).length ? facts : null,
        campaignType: values.campaignType,
        showProductDetails: values.wantDetails,
        adLayout: values.layout,
      })
      setCreative(data)
      onGenerated?.()
      return data
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Failed to generate creative.')
      return null
    } finally {
      setGenerating(false)
    }
  }, [strategyId, values, heroProduct, onGenerated])

  const uploadPhoto = useCallback(async (file) => {
    if (!file) return
    setUploading(true)
    setError('')
    try {
      // Attached to the hero product → saved to the library and reused forever
      const { data } = await creativeApi.uploadProductPhoto(file, heroProduct || null)
      setField('productUrl', data.product_image_url)
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Could not upload that photo.')
    } finally {
      setUploading(false)
    }
  }, [heroProduct, setField])

  return {
    values, setField,
    context, creative, heroProduct,
    autoDetails, detailsOn,
    loading, generating, uploading, error, setError,
    generate, uploadPhoto,
  }
}
