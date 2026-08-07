/**
 * components/adcreator/AdResult.jsx — PHASE 23.8
 *
 * The finished ad and the copy written alongside it. Shared by the standalone
 * Ad Creator and the workspace section for the same reason as the form: one
 * rendering of a generated asset means the download link, the Label Studio
 * handoff and the platform copy can never be present in one place and missing
 * in the other.
 */

import { useState } from 'react'
import { ChevronDown, ChevronUp, Download, Tag } from 'lucide-react'
import { assetUrl } from '../../api/client'

export function CopyBox({ label, text }) {
  const [copied, setCopied] = useState(false)
  const hasText = typeof text === 'string' && text.trim().length > 0
  return (
    <div className="bg-gray-50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-gray-500">{label}</p>
        <button disabled={!hasText}
          onClick={() => {
            navigator.clipboard.writeText(text)
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
          }}
          className="text-xs text-brand-500 hover:underline disabled:text-gray-300">
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
        {hasText ? text : '…'}
      </p>
    </div>
  )
}

export function GeneratingCard() {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center">
      <p className="text-3xl mb-3 animate-pulse">🎨</p>
      <p className="text-gray-600 font-medium">Designing your ad…</p>
      <p className="text-gray-400 text-sm mt-1">
        Rendering a festive, ready-to-post image — up to a minute.
      </p>
    </div>
  )
}

export default function AdResult({ creative, onAddLabels, compact = false, title }) {
  // On the workspace the platform copy starts folded: the page already has a
  // copy section, and two open stacks of text would bury the pipeline.
  const [showCopy, setShowCopy] = useState(!compact)
  if (!creative) return null

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <img src={assetUrl(creative.final_image_url || creative.image_url)}
          alt="Finished ad"
          className={`w-full object-contain bg-gray-50 ${compact ? 'max-h-[46vh]' : 'max-h-[70vh]'}`} />
        <div className="flex items-center justify-between px-6 py-4 gap-4 flex-wrap">
          <p className="text-xs text-gray-400">
            {new Date(creative.created_at).toLocaleString()} · ready to post
          </p>
          <div className="flex items-center gap-4">
            {onAddLabels && (
              <button onClick={onAddLabels}
                className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:border-brand-300 hover:text-brand-600 transition-colors">
                <Tag size={14} /> Add labels
              </button>
            )}
            <a href={assetUrl(creative.final_image_url || creative.image_url)}
              download="liquoriq-ad.png"
              className="flex items-center gap-1.5 text-xs font-semibold text-brand-500 hover:underline">
              <Download size={14} /> Download ad
            </a>
          </div>
        </div>
      </div>

      <div>
        {compact ? (
          <button onClick={() => setShowCopy(!showCopy)}
            className="text-xs font-semibold text-gray-400 hover:text-gray-600 uppercase tracking-wide flex items-center gap-1 mb-3">
            {showCopy ? <ChevronUp size={13} /> : <ChevronDown size={13} />} Platform copy
          </button>
        ) : (
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
            Platform copy {title && `— ${title}`}
          </p>
        )}
        {showCopy && (
          <>
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
          </>
        )}
      </div>
    </div>
  )
}
