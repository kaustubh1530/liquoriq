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
 */

import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { aiApi, creativeApi, assetUrl } from '../api/client'
import Layout from '../components/Layout'
import { Palette, Download, RefreshCw, Image as ImageIcon, Upload, ChevronDown, ChevronUp, Tag } from 'lucide-react'

// Campaign types where customer-facing product details earn their place on the
// ad. Everything else stays clean and minimal unless the owner opts in.
const CAMPAIGN_TYPES = [
  { v: 'standard',           label: 'Standard promotion', details: false },
  { v: 'new_arrival',        label: 'New arrival',        details: true },
  { v: 'product_spotlight',  label: 'Product spotlight',  details: true },
  { v: 'premium_collection', label: 'Premium collection', details: true },
  { v: 'limited_edition',    label: 'Limited edition',    details: true },
]

function CopyBox({ label, text }) {
  const [copied, setCopied] = useState(false)
  const hasText = typeof text === 'string' && text.trim().length > 0
  const copy = () => {
    if (!hasText) return
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div className="bg-gray-50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-gray-500">{label}</p>
        <button onClick={copy} disabled={!hasText}
          className="text-xs text-brand-500 hover:underline disabled:text-gray-300">
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{hasText ? text : '…'}</p>
    </div>
  )
}

export default function Creative() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const preselected = searchParams.get('strategy')

  const [strategies, setStrategies] = useState([])
  // Fallback used only until the list loads and only when the URL names nothing.
  const [fallbackId, setFallbackId] = useState('')

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
   * refresh restores the same campaign, and the back button behaves.
   */
  const selectedId = preselected || fallbackId
  const [creative, setCreative] = useState(null)
  const [offer, setOffer] = useState('')          // exact promo price/offer to render
  const [instructions, setInstructions] = useState('')  // owner art-direction hints
  const [productUrl, setProductUrl] = useState('')      // Phase 16: real bottle photo
  const [format, setFormat] = useState('square')        // square | portrait | landscape
  const [showMore, setShowMore] = useState(false)       // optional look-and-feel
  const [showFacts, setShowFacts] = useState(false)     // product details
  const [factsText, setFactsText] = useState('')        // one "key: value" per line
  const [category, setCategory] = useState('')
  const [layout, setLayout] = useState('auto')       // how the text is typeset
  const [campaignType, setCampaignType] = useState('standard')
  const [wantDetails, setWantDetails] = useState(false)  // owner opt-in for details
  const [uploading, setUploading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  // PHASE 23.6 — the campaign context, and the fields the owner has edited.
  //
  // `touched` is the whole "preserve edits" mechanism: auto-fill writes a field
  // only if it is not in this set. Without it, coming back to the page would
  // silently overwrite a price the owner had just corrected — which is worse
  // than never auto-filling at all, because he would not notice.
  const [context, setContext] = useState(null)
  const [touched, setTouched] = useState(() => new Set())
  const markTouched = (field) =>
    setTouched((prev) => (prev.has(field) ? prev : new Set(prev).add(field)))

  // Details are automatic for product-led campaigns; the toggle is the manual opt-in
  const autoDetails = CAMPAIGN_TYPES.find((c) => c.v === campaignType)?.details ?? false
  const detailsOn = autoDetails || wantDetails

  // Load strategy list once; default to preselected or newest
  useEffect(() => {
    (async () => {
      try {
        const { data } = await aiApi.list()
        setStrategies(data)
        if (!preselected && data.length > 0) setFallbackId(data[0].id)
      } catch {
        // empty state shown below
      } finally {
        setLoading(false)
      }
    })()
  }, [preselected])


  const selectedStrategy = strategies.find((s) => s.id === selectedId)
  const heroProduct = selectedStrategy?.products_to_promote?.[0] ?? ''

  // When the selected strategy changes, fetch its latest creative (404 = none yet)
  useEffect(() => {
    if (!selectedId) return
    // Clear everything belonging to the previous strategy BEFORE fetching, so
    // a slow request can never leave the last campaign's ad on screen next to
    // the new campaign's name.
    setCreative(null)
    setError('')
    setProductUrl('')
    setOffer('')
    setInstructions('')
    // A different campaign is a different form: edits belonged to the old one.
    setTouched(new Set())
    ;(async () => {
      try {
        const { data } = await creativeApi.get(selectedId)
        setCreative(data)
      } catch {
        // 404 — no creative yet, fine
      }
    })()
  }, [selectedId])

  /**
   * Pull the campaign context and fill the form from it.
   *
   * The owner already told the advisor what campaign to run. Asking him to
   * describe it again — type, layout, offer, look and feel — is the system
   * forgetting a conversation it just had.
   *
   * Every write is guarded by `touched`, so an edit survives navigating away
   * and coming back. Auto-fill happens once per field, not once per render.
   */
  useEffect(() => {
    if (!selectedId) { setContext(null); return }
    let cancelled = false

    creativeApi.campaignContext(selectedId)
      .then(({ data }) => {
        if (cancelled) return
        setContext(data)
        const pre = data.prefill ?? {}

        // Each of these is "fill it in unless he has already touched it".
        if (!touched.has('offer') && pre.offer) setOffer(pre.offer)
        if (!touched.has('instructions') && pre.instructions) setInstructions(pre.instructions)
        if (!touched.has('campaignType') && pre.campaign_type) setCampaignType(pre.campaign_type)
        if (!touched.has('layout') && pre.layout) setLayout(pre.layout)
        if (!touched.has('format') && pre.image_format) setFormat(pre.image_format)
        if (!touched.has('category') && pre.category) setCategory(pre.category)
        if (!touched.has('productUrl') && pre.product_url) setProductUrl(pre.product_url)
        if (!touched.has('facts') && pre.facts && Object.keys(pre.facts).length) {
          setFactsText(Object.entries(pre.facts).map(([k, v]) => `${k}: ${v}`).join('\n'))
        }
        // Only open the details panel when there is something to put in it.
        if (!touched.has('details') && pre.show_details) {
          setWantDetails(true)
          setShowFacts(true)
        }
      })
      .catch(() => { /* no context — the form stays manual, which still works */ })

    return () => { cancelled = true }
    // `touched` is deliberately NOT a dependency: re-running on every edit
    // would re-fill the fields the owner is in the middle of changing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId])

  // Load the saved library photo + facts for the hero product (reused each time)
  useEffect(() => {
    if (!heroProduct) { setProductUrl(''); setFactsText(''); return }
    ;(async () => {
      try {
        const { data } = await creativeApi.getProductPhoto(heroProduct)
        setProductUrl(data.product_image_url || '')
      } catch { setProductUrl('') }
      try {
        const { data } = await creativeApi.getFacts(heroProduct)
        const f = data.facts || {}
        setFactsText(Object.entries(f).map(([k, v]) => `${k}: ${v}`).join('\n'))
      } catch { setFactsText('') }
    })()
  }, [heroProduct])

  // Parse the "key: value" lines into a facts object (only confirmed, owner-entered)
  const parseFacts = () => {
    const facts = {}
    for (const line of factsText.split('\n')) {
      const i = line.indexOf(':')
      if (i > 0) {
        const k = line.slice(0, i).trim().toLowerCase().replace(/\s+/g, '_')
        const v = line.slice(i + 1).trim()
        if (k && v) facts[k] = v
      }
    }
    return facts
  }

  const handleGenerate = async () => {
    setError('')
    setGenerating(true)
    try {
      const facts = parseFacts()
      if (heroProduct && Object.keys(facts).length) {
        try { await creativeApi.saveFacts(heroProduct, category.trim() || null, facts) } catch { /* noop */ }
      }
      const { data } = await creativeApi.generate(selectedId, {
        offerOverride: offer.trim() || null,
        instructions: instructions.trim() || null,
        productImageUrl: productUrl || null,
        imageFormat: format,
        productFacts: Object.keys(facts).length ? facts : null,
        campaignType,
        showProductDetails: wantDetails,
        adLayout: layout,
      })
      setCreative(data)
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Failed to generate creative.')
    } finally {
      setGenerating(false)
    }
  }

  // Hand the finished ad to the Label Studio — a separate tool, not an edit mode.
  const openLabelStudio = () => navigate(`/labels?creative=${creative.id}`)

  const handlePhoto = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError('')
    try {
      // Attach to the hero product → saved to the library and reused forever
      const { data } = await creativeApi.uploadProductPhoto(file, heroProduct || null)
      setProductUrl(data.product_image_url)
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Could not upload that photo.')
    } finally {
      setUploading(false)
    }
  }

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

          {loading ? (
            <p className="text-gray-400 text-sm">Loading strategies…</p>
          ) : strategies.length === 0 ? (
            <p className="text-sm text-gray-500">
              No strategies yet — generate one on the <span className="font-medium">AI Strategy</span> page first.
            </p>
          ) : (
            <div className="space-y-4">
              {/* Strategy + price */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Price on the ad <span className="text-gray-300 font-normal">(optional)</span></label>
                  <input
                    type="text"
                    value={offer}
                    onChange={(e) => { markTouched('offer'); setOffer(e.target.value) }}
                    placeholder="$69.99 · 20% OFF · BOGO"
                    className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
              </div>

              {/* Campaign type — drives whether product details appear at all */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Campaign type</label>
                <select
                  value={campaignType}
                  onChange={(e) => { markTouched('campaignType'); setCampaignType(e.target.value) }}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  {CAMPAIGN_TYPES.map((c) => (
                    <option key={c.v} value={c.v}>{c.label}</option>
                  ))}
                </select>
                <p className="text-[11px] text-gray-400 mt-1">
                  {autoDetails
                    ? 'Product details are included automatically for this campaign type.'
                    : 'Kept clean and minimal — no product details unless you turn them on below.'}
                </p>
              </div>

              {/* Text layout — how the caption sits over the photo */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Text layout</label>
                <div className="inline-flex rounded-xl border border-gray-200 overflow-hidden text-xs font-semibold flex-wrap">
                  {[
                    { v: 'auto', label: 'Auto' },
                    { v: 'poster', label: 'Poster' },
                    { v: 'band', label: 'Bottom band' },
                    { v: 'rail', label: 'Side column' },
                    { v: 'banner', label: 'Top banner' },
                  ].map((l) => (
                    <button key={l.v} onClick={() => { markTouched('layout'); setLayout(l.v) }}
                      className={`px-3.5 py-1.5 transition-colors ${
                        layout === l.v ? 'bg-brand-500 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'
                      }`}>
                      {l.label}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-gray-400 mt-1">
                  Poster is the premium spirits look — big headline over the photo with a painted price mark.
                  Auto picks the one that suits your format.
                </p>
              </div>

              {/* Format — compact segmented control + photo status on one line */}
              <div className="flex items-center justify-between gap-4 flex-wrap">
                <div className="inline-flex rounded-xl border border-gray-200 overflow-hidden text-xs font-semibold">
                  {[
                    { v: 'square', label: 'Square' },
                    { v: 'portrait', label: 'Portrait' },
                    { v: 'landscape', label: 'Landscape' },
                  ].map((f) => (
                    <button key={f.v} onClick={() => { markTouched('format'); setFormat(f.v) }}
                      className={`px-3.5 py-1.5 transition-colors ${
                        format === f.v ? 'bg-brand-500 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'
                      }`}>
                      {f.label}
                    </button>
                  ))}
                </div>

                {/* Real photo — compact */}
                {productUrl ? (
                  <div className="flex items-center gap-2 text-xs">
                    <img src={assetUrl(productUrl)} alt="" className="w-8 h-8 object-contain rounded-md border border-gray-200 bg-gray-50" />
                    <span className="text-green-600 font-medium">Real photo on file</span>
                    <label className="text-brand-500 hover:underline cursor-pointer">
                      Replace<input type="file" accept="image/*" onChange={handlePhoto} className="hidden" disabled={uploading} />
                    </label>
                  </div>
                ) : (
                  <label className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-600 hover:text-brand-700 cursor-pointer">
                    <Upload size={13} />
                    {uploading ? 'Uploading…' : `Add real photo${heroProduct ? '' : ''}`}
                    <input type="file" accept="image/*" onChange={handlePhoto} className="hidden" disabled={uploading} />
                  </label>
                )}
              </div>

              {/* Product details — confirmed facts used (and only these) on the ad */}
              <div>
                <button onClick={() => setShowFacts(!showFacts)}
                  className="text-xs font-medium text-gray-400 hover:text-gray-600 flex items-center gap-1">
                  {showFacts ? <ChevronUp size={13} /> : <ChevronDown size={13} />} Product details (optional — for new arrivals & premium products)
                </button>
                {showFacts && (
                  <div className="mt-2 space-y-2">
                    <label className="flex items-center gap-2 text-xs text-gray-600">
                      <input type="checkbox" checked={detailsOn} disabled={autoDetails}
                        onChange={(e) => { markTouched('details'); setWantDetails(e.target.checked) }} />
                      Show product details on the advertisement
                      {autoDetails && <span className="text-gray-400">(always on for {CAMPAIGN_TYPES.find((c) => c.v === campaignType)?.label.toLowerCase()})</span>}
                    </label>
                    <input value={category} onChange={(e) => { markTouched('category'); setCategory(e.target.value) }}
                      placeholder="Category (e.g. Whiskey, Wine, Tequila)"
                      className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                    <textarea value={factsText} onChange={(e) => { markTouched('facts'); setFactsText(e.target.value) }}
                      rows={4}
                      placeholder={"One fact per line, as label: value —\nproof: 90 proof\nage: aged 12 years\norigin: Lynchburg, Tennessee\ntasting notes: caramel, oak, vanilla"}
                      className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
                    <p className="text-[11px] text-gray-400">
                      Only these confirmed facts are used on the ad — the AI never invents proof, age, awards, or origin. Saved and reused for {heroProduct || 'this product'}.
                    </p>
                  </div>
                )}
              </div>

              {/* Optional look-and-feel — tucked away to keep it clean */}
              <div>
                <button onClick={() => setShowMore(!showMore)}
                  className="text-xs font-medium text-gray-400 hover:text-gray-600 flex items-center gap-1">
                  {showMore ? <ChevronUp size={13} /> : <ChevronDown size={13} />} Look &amp; feel (optional)
                </button>
                {showMore && (
                  <textarea
                    value={instructions}
                    onChange={(e) => { markTouched('instructions'); setInstructions(e.target.value) }}
                    rows={2}
                    placeholder="e.g. Christmas theme with snow & a fireplace. Bigger price tag. Cocktail beside the bottle."
                    className="mt-2 w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                  />
                )}
              </div>

              <button
                onClick={handleGenerate}
                disabled={generating || !selectedId}
                className="w-full sm:w-auto flex items-center justify-center gap-2 bg-brand-500 hover:bg-brand-600 text-white font-semibold px-6 py-2.5 rounded-xl text-sm transition-colors disabled:opacity-60"
              >
                {creative ? <RefreshCw size={16} /> : <ImageIcon size={16} />}
                {generating ? 'Generating… (40-60s)' : creative ? 'Regenerate ad' : 'Generate ad'}
              </button>
            </div>
          )}
        </div>

        {/* ── Result ── */}
        {generating && (
          <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center mb-8">
            <p className="text-3xl mb-3 animate-pulse">🎨</p>
            <p className="text-gray-600 font-medium">Designing your ad…</p>
            <p className="text-gray-400 text-sm mt-1">Rendering a festive, ready-to-post image — up to a minute.</p>
          </div>
        )}

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

        {creative && !generating && (
          <div className="space-y-6">
            {/* The finished ad — the AI Ad Creator's job ends here */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <img
                src={assetUrl(creative.image_url)}
                alt="Finished ad"
                className="w-full max-h-[70vh] object-contain bg-gray-50"
              />
              <div className="flex items-center justify-between px-6 py-4 gap-4 flex-wrap">
                <p className="text-xs text-gray-400">
                  {new Date(creative.created_at).toLocaleString()} · ready to post
                </p>
                <div className="flex items-center gap-4">
                  <button
                    onClick={openLabelStudio}
                    className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:border-brand-300 hover:text-brand-600 transition-colors"
                  >
                    <Tag size={14} />
                    Add labels
                  </button>
                  <a
                    href={assetUrl(creative.image_url)}
                    download="liquoriq-ad.png"
                    className="flex items-center gap-1.5 text-xs font-semibold text-brand-500 hover:underline"
                  >
                    <Download size={14} />
                    Download ad
                  </a>
                </div>
              </div>
            </div>

            {/* Platform copy */}
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
                Platform copy {selectedStrategy && `— ${selectedStrategy.strategy_title}`}
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <CopyBox label="📸 Instagram" text={creative.instagram_caption} />
                <CopyBox label="👥 Facebook" text={creative.facebook_post} />
                <CopyBox label="🛵 Uber Eats" text={creative.ubereats_description} />
                <CopyBox label="🚗 DoorDash" text={creative.doordash_description} />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                <CopyBox label="🌐 Website banner — headline" text={creative.website_banner_headline} />
                <CopyBox label="🌐 Website banner — text" text={creative.website_banner_text} />
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
