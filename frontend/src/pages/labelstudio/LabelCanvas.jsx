/**
 * LabelCanvas.jsx — MODULE 2: LABEL STUDIO (drag surface)
 *
 * Shows the server-rendered label with an invisible drag handle over each
 * element. The handles are positioned from the boxes the RENDERER reports, so
 * they line up exactly with what will print — there is no second layout engine
 * in the browser to drift out of sync.
 *
 * While dragging we move the handle locally (instant, no round trip) and only
 * commit the new position on release, which re-renders the label.
 */

import { useEffect, useRef, useState } from 'react'

const SNAP = 0.02          // relative units — ~2% of the card
const GUIDES = [0, 0.5, 1] // edges and centre

export default function LabelCanvas({
  image, boxes, selectedId, onSelect, onMove, onDelete, onDuplicate,
  width = 460, aspect = 4 / 3, snapEnabled = true, showGrid = false,
}) {
  const wrapRef = useRef(null)
  const [drag, setDrag] = useState(null)   // {id, dx, dy, x, y}
  const [guides, setGuides] = useState({ v: null, h: null })
  const height = width / aspect

  const snap = (value, extra = []) => {
    if (!snapEnabled) return { value, guide: null }
    for (const g of [...GUIDES, ...extra]) {
      if (Math.abs(value - g) < SNAP) return { value: g, guide: g }
    }
    return { value, guide: null }
  }

  useEffect(() => {
    if (!drag) return

    const move = (e) => {
      const rect = wrapRef.current?.getBoundingClientRect()
      if (!rect) return
      const point = e.touches ? e.touches[0] : e
      let x = (point.clientX - rect.left) / rect.width - drag.dx
      let y = (point.clientY - rect.top) / rect.height - drag.dy

      // Snap the element's left/centre/right edge to the card's guides
      const sx = snap(x, [0.5 - drag.w / 2, 1 - drag.w])
      const sy = snap(y, [0.5 - drag.h / 2, 1 - drag.h])
      x = Math.min(Math.max(sx.value, -0.3), 1.3)
      y = Math.min(Math.max(sy.value, -0.3), 1.3)

      setDrag((d) => (d ? { ...d, x, y } : d))
      setGuides({ v: sx.guide, h: sy.guide })
    }

    const up = () => {
      setGuides({ v: null, h: null })
      setDrag((d) => {
        if (d) onMove(d.id, d.x, d.y)
        return null
      })
    }

    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    window.addEventListener('touchmove', move, { passive: false })
    window.addEventListener('touchend', up)
    return () => {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
      window.removeEventListener('touchmove', move)
      window.removeEventListener('touchend', up)
    }
  }, [drag, onMove, snapEnabled])

  const startDrag = (e, box) => {
    e.preventDefault()
    onSelect(box.id)
    const rect = wrapRef.current.getBoundingClientRect()
    const point = e.touches ? e.touches[0] : e
    setDrag({
      id: box.id,
      w: box.w, h: box.h,
      dx: (point.clientX - rect.left) / rect.width - box.x,
      dy: (point.clientY - rect.top) / rect.height - box.y,
      x: box.x, y: box.y,
    })
  }

  const pct = (n) => `${n * 100}%`
  const selectedBox = boxes.find((b) => b.id === selectedId) || null

  return (
    <div
      ref={wrapRef}
      className="relative select-none bg-white rounded shadow-sm overflow-hidden"
      style={{ width, height, touchAction: 'none' }}
      onMouseDown={(e) => { if (e.target === wrapRef.current) onSelect(null) }}
    >
      {image && (
        <img src={image} alt="Label preview" draggable={false}
          className="absolute inset-0 w-full h-full" />
      )}

      {showGrid && (
        <div className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage:
              'linear-gradient(to right, rgba(0,0,0,.10) 1px, transparent 1px),' +
              'linear-gradient(to bottom, rgba(0,0,0,.10) 1px, transparent 1px)',
            backgroundSize: `${100 / 8}% ${100 / 6}%`,
          }} />
      )}

      {boxes.map((box) => {
        const live = drag?.id === box.id ? drag : null
        const isSel = selectedId === box.id
        return (
          <div
            key={box.id}
            onMouseDown={(e) => startDrag(e, box)}
            onTouchStart={(e) => startDrag(e, box)}
            title="Drag to move"
            className={`absolute cursor-move transition-colors ${
              isSel ? 'ring-2 ring-brand-500 bg-brand-500/5'
                    : 'hover:ring-1 hover:ring-brand-300'}`}
            style={{
              left: pct(live ? live.x : box.x),
              top: pct(live ? live.y : box.y),
              width: pct(box.w),
              height: pct(box.h),
              borderRadius: 3,
            }}
          />
        )
      })}

      {/* Delete / duplicate float right on the selected piece — the owner
          shouldn't have to hunt for them in a side panel. */}
      {selectedBox && !drag && (
        <div
          className="absolute z-10 flex items-center gap-1 bg-white rounded-lg shadow-md border border-gray-200 px-1 py-0.5"
          style={{
            left: pct(selectedBox.x),
            top: `calc(${pct(selectedBox.y)} - 30px)`,
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <button onClick={() => onDuplicate?.(selectedBox.id)} title="Duplicate"
            className="p-1 text-gray-500 hover:text-gray-900">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          </button>
          <button onClick={() => onDelete?.(selectedBox.id)} title="Delete (or press Delete)"
            className="p-1 text-gray-500 hover:text-red-600">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
            </svg>
          </button>
        </div>
      )}

      {guides.v !== null && (
        <div className="absolute top-0 bottom-0 pointer-events-none"
          style={{ left: pct(guides.v), borderLeft: '1px dashed #06b6d4' }} />
      )}
      {guides.h !== null && (
        <div className="absolute left-0 right-0 pointer-events-none"
          style={{ top: pct(guides.h), borderTop: '1px dashed #06b6d4' }} />
      )}
    </div>
  )
}
