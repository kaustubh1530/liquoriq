/**
 * Creative.jsx — Ad Creative studio (Phase 10, simplified Phase 15+)
 *
 * The AI now renders a FINISHED festive ad — scene, hero product, headline,
 * offer, and store name are all baked into the image. So there's no separate
 * price-overlay step anymore (it produced ugly double-text). Instead the owner
 * can set the exact promo price/offer to render, then Generate / Regenerate.
 */

import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { aiApi, creativeApi, assetUrl } from '../api/client'
import Layout from '../components/Layout'
import { Megaphone, Download, RefreshCw, Image as ImageIcon, Upload, X } from 'lucide-react'

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
  const [searchParams] = useSearchParams()
  const preselected = searchParams.get('strategy')

  const [strategies, setStrategies] = useState([])
  const [selectedId, setSelectedId] = useState(preselected ?? '')
  const [creative, setCreative] = useState(null)
  const [offer, setOffer] = useState('')          // exact promo price/offer to render
  const [instructions, setInstructions] = useState('')  // owner art-direction hints
  const [productUrl, setProductUrl] = useState('')      // Phase 16: real bottle photo
  const [uploading, setUploading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  // Load strategy list once; default to preselected or newest
  useEffect(() => {
    (async () => {
      try {
        const { data } = await aiApi.list()
        setStrategies(data)
        if (!preselected && data.length > 0) setSelectedId(data[0].id)
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
    setCreative(null)
    setError('')
    setProductUrl('')
    ;(async () => {
      try {
        const { data } = await creativeApi.get(selectedId)
        setCreative(data)
      } catch {
        // 404 — no creative yet, fine
      }
    })()
  }, [selectedId])

  // Load the saved library photo for the hero product ("upload once, reuse forever")
  useEffect(() => {
    if (!heroProduct) { setProductUrl(''); return }
    ;(async () => {
      try {
        const { data } = await creativeApi.getProductPhoto(heroProduct)
        setProductUrl(data.product_image_url || '')
      } catch {
        setProductUrl('')
      }
    })()
  }, [heroProduct])

  const handleGenerate = async () => {
    setError('')
    setGenerating(true)
    try {
      const { data } = await creativeApi.generate(selectedId, {
        offerOverride: offer.trim() || null,
        instructions: instructions.trim() || null,
        productImageUrl: productUrl || null,
      })
      setCreative(data)
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Failed to generate creative.')
    } finally {
      setGenerating(false)
    }
  }

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
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Ad Creative</h1>
        <p className="text-sm text-gray-500 mb-8">
          A finished, ready-to-post ad — scene, product, offer, and your store name, all in one image
        </p>

        {/* ── Generate panel ── */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-8">
          <div className="flex items-center gap-3 mb-4">
            <Megaphone size={20} className="text-brand-500" />
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
              <div>
                <label className="block text-xs text-gray-500 mb-1">Strategy</label>
                <select
                  value={selectedId}
                  onChange={(e) => setSelectedId(e.target.value)}
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
                <label className="block text-xs text-gray-500 mb-1">
                  Promo price / offer to show on the ad <span className="text-gray-300">(optional — defaults to the strategy's offer)</span>
                </label>
                <input
                  type="text"
                  value={offer}
                  onChange={(e) => setOffer(e.target.value)}
                  placeholder="e.g. $69.99  ·  20% OFF  ·  Buy 2 get 1 free"
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                <p className="text-[11px] text-gray-400 mt-1">
                  This exact price is rendered into the image. Change it and Regenerate to update the ad.
                </p>
              </div>

              <div>
                <label className="block text-xs text-gray-500 mb-1">
                  Real photo for <span className="font-medium text-gray-600">{heroProduct || 'the hero product'}</span>{' '}
                  <span className="text-gray-300">(optional — accurate bottle & label)</span>
                </label>
                {productUrl ? (
                  <div className="flex items-center gap-3">
                    <img src={assetUrl(productUrl)} alt="Product" className="w-14 h-14 object-contain rounded-lg border border-gray-200 bg-gray-50" />
                    <span className="text-xs text-green-600 font-medium">On file — reused automatically for this product ✓</span>
                    <label className="text-xs text-brand-500 hover:underline cursor-pointer">
                      Replace
                      <input type="file" accept="image/*" onChange={handlePhoto} className="hidden" disabled={uploading} />
                    </label>
                  </div>
                ) : (
                  <label className="inline-flex items-center gap-2 text-sm text-brand-600 bg-brand-50 hover:bg-brand-100 px-4 py-2 rounded-xl cursor-pointer transition-colors">
                    <Upload size={15} />
                    {uploading ? 'Uploading…' : 'Upload bottle photo (once)'}
                    <input type="file" accept="image/*" onChange={handlePhoto} className="hidden" disabled={uploading} />
                  </label>
                )}
                <p className="text-[11px] text-gray-400 mt-1">
                  Upload once per product — we save it and reuse it for every future ad of {heroProduct || 'this product'}. Use your own photo or a manufacturer image you're allowed to use.
                </p>
              </div>

              <div>
                <label className="block text-xs text-gray-500 mb-1">
                  How should the ad look? <span className="text-gray-300">(optional — theme, event, layout, mood, changes)</span>
                </label>
                <textarea
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  rows={2}
                  placeholder="e.g. Make it a Christmas theme with snow and a fireplace. Bigger price tag. Warmer, gold tones. Show a festive cocktail beside the bottle."
                  className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                />
              </div>

              <button
                onClick={handleGenerate}
                disabled={generating || !selectedId}
                className="flex items-center gap-2 bg-brand-500 hover:bg-brand-600 text-white font-semibold px-5 py-2.5 rounded-xl text-sm transition-colors disabled:opacity-60"
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

        {creative && !generating && (
          <div className="space-y-6">
            {/* The finished ad */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <img
                src={assetUrl(creative.image_url)}
                alt="Finished ad"
                className="w-full aspect-square object-cover"
              />
              <div className="flex items-center justify-between px-6 py-4">
                <p className="text-xs text-gray-400">
                  {new Date(creative.created_at).toLocaleString()} · ready to post
                </p>
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
