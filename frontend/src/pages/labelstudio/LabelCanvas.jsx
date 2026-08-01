/**
 * LabelCanvas.jsx — MODULE 2: LABEL STUDIO (the canvas)
 *
 * Renders the untouched base ad plus a stack of live, editable label nodes.
 * The AI image is NEVER modified — labels sit on top as canvas objects and are
 * only flattened when the owner exports.
 *
 * Each label is a <Group> containing an optional shape (Rect for rect-family
 * shapes, Line for polygon shapes) plus its text and optional subtext. The Group
 * is what drags/rotates/scales, so shape and text always move together.
 */

import { forwardRef, useEffect, useMemo, useRef, useState } from 'react'
import { Stage, Layer, Group, Rect, Line, Text, Transformer } from 'react-konva'
import { pointsFor, radiusFor, RECT_SHAPES, textInsetFor } from './shapes'

const SNAP = 8 // px (canvas space) — how close before a guide grabs

/** Load an <img> for Konva. crossOrigin keeps the canvas exportable (Cloudinary). */
function useImage(src) {
  const [img, setImg] = useState(null)
  useEffect(() => {
    if (!src) { setImg(null); return }
    let cancelled = false
    const image = new window.Image()
    image.crossOrigin = 'anonymous'
    image.onload = () => { if (!cancelled) setImg(image) }
    image.src = src
    return () => { cancelled = true }
  }, [src])
  return img
}

const LabelCanvas = forwardRef(function LabelCanvas(
  {
    design, labels, selectedId, onSelect, onCommit,
    displayWidth = 560, showGrid = false, snapEnabled = true,
  },
  stageRef,
) {
  const canvasW = design?.canvas?.width || 1024
  const canvasH = design?.canvas?.height || 1024
  const scale = displayWidth / canvasW
  const displayH = canvasH * scale

  const bg = useImage(design?.base_image)
  const trRef = useRef()
  const nodeRefs = useRef({})
  const [guides, setGuides] = useState({ v: null, h: null })

  const selected = labels.find((l) => l.id === selectedId)

  // Attach the transformer to whatever is selected (locked labels aren't grabbable)
  useEffect(() => {
    const tr = trRef.current
    if (!tr) return
    const node = selected && !selected.locked ? nodeRefs.current[selected.id] : null
    tr.nodes(node ? [node] : [])
    tr.getLayer()?.batchDraw()
  }, [selectedId, labels, selected])

  // ── Snap targets: canvas edges/centre + every other label's edges/centre ────
  const snapTargets = useMemo(() => {
    const v = [0, canvasW / 2, canvasW]
    const h = [0, canvasH / 2, canvasH]
    for (const l of labels) {
      if (l.id === selectedId) continue
      v.push(l.x, l.x + l.width / 2, l.x + l.width)
      h.push(l.y, l.y + l.height / 2, l.y + l.height)
    }
    return { v, h }
  }, [labels, selectedId, canvasW, canvasH])

  const snap = (label, x, y) => {
    if (!snapEnabled) return { x, y, guideV: null, guideH: null }
    let guideV = null
    let guideH = null
    const edgesX = [x, x + label.width / 2, x + label.width]
    for (let i = 0; i < edgesX.length && guideV === null; i++) {
      for (const t of snapTargets.v) {
        if (Math.abs(edgesX[i] - t) < SNAP) { x += t - edgesX[i]; guideV = t; break }
      }
    }
    const edgesY = [y, y + label.height / 2, y + label.height]
    for (let i = 0; i < edgesY.length && guideH === null; i++) {
      for (const t of snapTargets.h) {
        if (Math.abs(edgesY[i] - t) < SNAP) { y += t - edgesY[i]; guideH = t; break }
      }
    }
    return { x, y, guideV, guideH }
  }

  const gridLines = useMemo(() => {
    if (!showGrid) return []
    const step = Math.round(canvasW / 12)
    const lines = []
    for (let x = step; x < canvasW; x += step) lines.push([x, 0, x, canvasH])
    for (let y = step; y < canvasH; y += step) lines.push([0, y, canvasW, y])
    return lines
  }, [showGrid, canvasW, canvasH])

  return (
    <Stage
      ref={stageRef}
      width={displayWidth}
      height={displayH}
      scaleX={scale}
      scaleY={scale}
      onMouseDown={(e) => { if (e.target === e.target.getStage()) onSelect(null) }}
      onTouchStart={(e) => { if (e.target === e.target.getStage()) onSelect(null) }}
    >
      <Layer>
        {/* The untouched AI advertisement */}
        {bg && (
          <Rect
            width={canvasW}
            height={canvasH}
            fillPatternImage={bg}
            fillPatternScaleX={canvasW / bg.width}
            fillPatternScaleY={canvasH / bg.height}
          />
        )}

        {gridLines.map((pts, i) => (
          <Line key={`g${i}`} points={pts} stroke="#ffffff" strokeWidth={1}
            opacity={0.14} listening={false} />
        ))}

        {labels.map((l) => {
          if (l.visible === false) return null
          const inset = textInsetFor(l.shape, l.width, l.height)
          const hasSub = !!(l.subtext && l.subtext.trim())
          const subSize = Math.max(10, l.fontSize * 0.42)
          const isRect = RECT_SHAPES.has(l.shape)
          return (
            <Group
              key={l.id}
              id={l.id}
              x={l.x}
              y={l.y}
              rotation={l.rotation || 0}
              opacity={l.opacity ?? 1}
              draggable={!l.locked}
              ref={(n) => { if (n) nodeRefs.current[l.id] = n }}
              onClick={() => onSelect(l.id)}
              onTap={() => onSelect(l.id)}
              onDragMove={(e) => {
                const s = snap(l, e.target.x(), e.target.y())
                e.target.position({ x: s.x, y: s.y })
                setGuides({ v: s.guideV, h: s.guideH })
              }}
              onDragEnd={(e) => {
                setGuides({ v: null, h: null })
                onCommit({ ...l, x: e.target.x(), y: e.target.y() })
              }}
              onTransformEnd={(e) => {
                const n = e.target
                const next = {
                  ...l,
                  x: n.x(),
                  y: n.y(),
                  rotation: n.rotation(),
                  width: Math.max(24, l.width * n.scaleX()),
                  height: Math.max(24, l.height * n.scaleY()),
                }
                n.scaleX(1)
                n.scaleY(1)
                onCommit(next)
              }}
            >
              {l.shape !== 'none' && isRect && (
                <Rect
                  width={l.width}
                  height={l.height}
                  fill={l.shapeFill}
                  cornerRadius={l.shape === 'rounded'
                    ? l.cornerRadius
                    : radiusFor(l.shape, l.width, l.height)}
                  stroke={l.strokeWidth > 0 ? l.stroke : undefined}
                  strokeWidth={l.strokeWidth || 0}
                  shadowColor="#000000"
                  shadowOpacity={l.shadow ? 0.28 : 0}
                  shadowBlur={l.shadow ? 14 : 0}
                  shadowOffsetY={l.shadow ? 4 : 0}
                />
              )}
              {l.shape !== 'none' && !isRect && (
                <Line
                  points={pointsFor(l.shape, l.width, l.height) || []}
                  closed
                  fill={l.shapeFill}
                  stroke={l.strokeWidth > 0 ? l.stroke : undefined}
                  strokeWidth={l.strokeWidth || 0}
                  shadowColor="#000000"
                  shadowOpacity={l.shadow ? 0.28 : 0}
                  shadowBlur={l.shadow ? 14 : 0}
                  shadowOffsetY={l.shadow ? 4 : 0}
                />
              )}

              <Text
                text={l.text}
                x={inset.x}
                y={inset.y}
                width={inset.width}
                height={hasSub ? inset.height * 0.62 : inset.height}
                fontSize={l.fontSize}
                fontStyle={l.fontStyle}
                fontFamily={l.fontFamily}
                fill={l.fill}
                align={l.align}
                verticalAlign="middle"
                padding={l.padding}
                wrap="word"
                listening={false}
              />
              {hasSub && (
                <Text
                  text={l.subtext}
                  x={inset.x}
                  y={inset.y + inset.height * 0.58}
                  width={inset.width}
                  height={inset.height * 0.4}
                  fontSize={subSize}
                  fontFamily={l.fontFamily}
                  fill={l.fill}
                  align={l.align}
                  verticalAlign="middle"
                  opacity={0.88}
                  wrap="word"
                  listening={false}
                />
              )}
            </Group>
          )
        })}

        {/* Snap guides */}
        {guides.v !== null && (
          <Line points={[guides.v, 0, guides.v, canvasH]} stroke="#22d3ee"
            strokeWidth={2 / scale} dash={[8, 6]} listening={false} />
        )}
        {guides.h !== null && (
          <Line points={[0, guides.h, canvasW, guides.h]} stroke="#22d3ee"
            strokeWidth={2 / scale} dash={[8, 6]} listening={false} />
        )}

        <Transformer
          ref={trRef}
          rotateEnabled
          keepRatio={false}
          anchorSize={10}
          borderStroke="#22d3ee"
          anchorStroke="#22d3ee"
          enabledAnchors={['top-left', 'top-right', 'bottom-left', 'bottom-right',
            'middle-left', 'middle-right']}
          boundBoxFunc={(oldBox, newBox) =>
            (newBox.width < 24 || newBox.height < 24 ? oldBox : newBox)}
        />
      </Layer>
    </Stage>
  )
})

export default LabelCanvas
