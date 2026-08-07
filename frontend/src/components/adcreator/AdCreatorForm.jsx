/**
 * components/adcreator/AdCreatorForm.jsx — PHASE 23.8
 *
 * The Ad Creator's controls, rendered from a `useAdCreator` hook the CALLER
 * owns. There is exactly one of these: the standalone page and the embedded
 * workspace section differ in `compact`, and in nothing else. Two forms would
 * mean the day someone adds a field to one, the other quietly keeps sending the
 * old payload to a paid, 40-second image call.
 *
 * `compact` hides nothing — it only moves the art direction behind a
 * disclosure, so the workspace stays scannable and a wrong prefilled price is
 * still fixable where the owner is standing.
 */

import { useState } from 'react'
import {
  ChevronDown, ChevronUp, Image as ImageIcon, RefreshCw, Upload,
} from 'lucide-react'
import { assetUrl } from '../../api/client'
import { AD_FORMATS, AD_LAYOUTS, CAMPAIGN_TYPES } from '../../hooks/useAdCreator'

const FIELD =
  'w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500'
const LABEL = 'block text-xs font-medium text-gray-500 mb-1'

function Segmented({ options, value, onChange }) {
  return (
    <div className="inline-flex rounded-xl border border-gray-200 overflow-hidden text-xs font-semibold flex-wrap">
      {options.map((o) => (
        <button key={o.v} onClick={() => onChange(o.v)}
          className={`px-3.5 py-1.5 transition-colors ${
            value === o.v ? 'bg-brand-500 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'
          }`}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export default function AdCreatorForm({ ad, compact = false, children }) {
  const { values, setField, autoDetails, detailsOn, heroProduct,
          generating, uploading, creative, generate } = ad

  // In the compact rendering the art direction starts folded away; on the full
  // page it keeps the behaviour it always had.
  const [showArt, setShowArt] = useState(!compact)
  const [showFacts, setShowFacts] = useState(false)
  const [showMore, setShowMore] = useState(false)

  const typeLabel = CAMPAIGN_TYPES.find((c) => c.v === values.campaignType)?.label ?? ''

  return (
    <div className="space-y-4">
      {children}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className={LABEL}>
            Price on the ad <span className="text-gray-300 font-normal">(optional)</span>
          </label>
          <input type="text" value={values.offer}
            onChange={(e) => setField('offer', e.target.value)}
            placeholder="$69.99 · 20% OFF · BOGO" className={FIELD} />
        </div>
        <div>
          <label className={LABEL}>Campaign type</label>
          <select value={values.campaignType}
            onChange={(e) => setField('campaignType', e.target.value)} className={FIELD}>
            {CAMPAIGN_TYPES.map((c) => (
              <option key={c.v} value={c.v}>{c.label}</option>
            ))}
          </select>
        </div>
      </div>
      <p className="text-[11px] text-gray-400 -mt-2">
        {autoDetails
          ? `Product details are included automatically for a ${typeLabel.toLowerCase()}.`
          : 'Kept clean and minimal — no product details unless you turn them on.'}
      </p>

      {compact && (
        <button onClick={() => setShowArt(!showArt)}
          className="text-xs font-medium text-gray-400 hover:text-gray-600 flex items-center gap-1">
          {showArt ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          Layout, format, photo &amp; details
        </button>
      )}

      {showArt && (
        <div className="space-y-4">
          <div>
            <label className={LABEL}>Text layout</label>
            <Segmented options={AD_LAYOUTS} value={values.layout}
              onChange={(v) => setField('layout', v)} />
            <p className="text-[11px] text-gray-400 mt-1">
              Poster is the premium spirits look — big headline over the photo with a
              painted price mark. Auto picks the one that suits your format.
            </p>
          </div>

          <div className="flex items-center justify-between gap-4 flex-wrap">
            <Segmented options={AD_FORMATS} value={values.format}
              onChange={(v) => setField('format', v)} />

            {values.productUrl ? (
              <div className="flex items-center gap-2 text-xs">
                <img src={assetUrl(values.productUrl)} alt=""
                  className="w-8 h-8 object-contain rounded-md border border-gray-200 bg-gray-50" />
                <span className="text-green-600 font-medium">Real photo on file</span>
                <label className="text-brand-500 hover:underline cursor-pointer">
                  Replace
                  <input type="file" accept="image/*" className="hidden" disabled={uploading}
                    onChange={(e) => ad.uploadPhoto(e.target.files?.[0])} />
                </label>
              </div>
            ) : (
              <label className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-600 hover:text-brand-700 cursor-pointer">
                <Upload size={13} />
                {uploading ? 'Uploading…' : 'Add real photo'}
                <input type="file" accept="image/*" className="hidden" disabled={uploading}
                  onChange={(e) => ad.uploadPhoto(e.target.files?.[0])} />
              </label>
            )}
          </div>

          {/* Product details — only confirmed, owner-entered facts reach the ad */}
          <div>
            <button onClick={() => setShowFacts(!showFacts)}
              className="text-xs font-medium text-gray-400 hover:text-gray-600 flex items-center gap-1">
              {showFacts ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              Product details (optional — for new arrivals &amp; premium products)
            </button>
            {showFacts && (
              <div className="mt-2 space-y-2">
                <label className="flex items-center gap-2 text-xs text-gray-600">
                  <input type="checkbox" checked={detailsOn} disabled={autoDetails}
                    onChange={(e) => setField('wantDetails', e.target.checked)} />
                  Show product details on the advertisement
                  {autoDetails && (
                    <span className="text-gray-400">(always on for {typeLabel.toLowerCase()})</span>
                  )}
                </label>
                <input value={values.category}
                  onChange={(e) => setField('category', e.target.value)}
                  placeholder="Category (e.g. Whiskey, Wine, Tequila)" className={FIELD} />
                <textarea value={values.factsText} rows={4}
                  onChange={(e) => setField('factsText', e.target.value)}
                  placeholder={'One fact per line, as label: value —\nproof: 90 proof\nage: aged 12 years\norigin: Lynchburg, Tennessee'}
                  className={`${FIELD} font-mono resize-none`} />
                <p className="text-[11px] text-gray-400">
                  Only these confirmed facts are used on the ad — the AI never invents
                  proof, age, awards or origin. Saved and reused for{' '}
                  {heroProduct || 'this product'}.
                </p>
              </div>
            )}
          </div>

          <div>
            <button onClick={() => setShowMore(!showMore)}
              className="text-xs font-medium text-gray-400 hover:text-gray-600 flex items-center gap-1">
              {showMore ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              Look &amp; feel (optional)
            </button>
            {showMore && (
              <textarea value={values.instructions} rows={2}
                onChange={(e) => setField('instructions', e.target.value)}
                placeholder="e.g. Christmas theme with snow & a fireplace. Bigger price tag."
                className={`mt-2 ${FIELD} resize-none`} />
            )}
          </div>
        </div>
      )}

      <button onClick={generate} disabled={generating}
        className="w-full sm:w-auto flex items-center justify-center gap-2 bg-brand-500 hover:bg-brand-600 text-white font-semibold px-6 py-2.5 rounded-xl text-sm transition-colors disabled:opacity-60">
        {creative ? <RefreshCw size={16} /> : <ImageIcon size={16} />}
        {generating ? 'Generating… (40-60s)' : creative ? 'Regenerate ad' : 'Generate ad'}
      </button>
    </div>
  )
}
