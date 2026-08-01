/**
 * shapes.js — Label Studio shape geometry
 *
 * Every badge shape is a pure function of (width, height) returning either a
 * Konva Rect config or a point array for a Line. Keeping the geometry here (and
 * out of the component) means shapes are trivially testable and easy to extend:
 * add a case, get a new badge everywhere.
 */

/** Rounded-rect radius per shape — a pill is just a rect with radius = h/2. */
export function radiusFor(shape, w, h) {
  switch (shape) {
    case 'pill': return h / 2
    case 'circle': return Math.min(w, h) / 2
    case 'rounded': return Math.min(18, h * 0.28)
    case 'price_tag': return Math.min(14, h * 0.2)
    case 'rectangle': return 0
    default: return 0
  }
}

/** Shapes drawn as a simple (rounded) rectangle. */
export const RECT_SHAPES = new Set(['rectangle', 'rounded', 'pill', 'circle', 'price_tag'])

/** Star/burst points: alternating outer and inner radius. */
function burstPoints(w, h, spikes, innerRatio) {
  const cx = w / 2
  const cy = h / 2
  const rx = w / 2
  const ry = h / 2
  const pts = []
  const step = Math.PI / spikes
  for (let i = 0; i < spikes * 2; i++) {
    const r = i % 2 === 0 ? 1 : innerRatio
    const a = i * step - Math.PI / 2
    pts.push(cx + Math.cos(a) * rx * r, cy + Math.sin(a) * ry * r)
  }
  return pts
}

/** Scalloped seal — many shallow spikes reads as a wax seal / rosette. */
function sealPoints(w, h) {
  return burstPoints(w, h, 16, 0.88)
}

/** Ribbon: a banner with notched (swallow-tail) ends. */
function ribbonPoints(w, h) {
  const notch = Math.min(w * 0.09, h * 0.6)
  return [
    0, 0,
    w, 0,
    w - notch, h / 2,
    w, h,
    0, h,
    notch, h / 2,
  ]
}

/** Banner: a rectangle with a folded lower edge — flatter, more editorial. */
function bannerPoints(w, h) {
  const fold = h * 0.22
  return [0, 0, w, 0, w, h, w / 2, h - fold, 0, h]
}

/** Speech bubble body + a tail on the lower-left. */
function speechPoints(w, h) {
  const bh = h * 0.78
  const tail = Math.min(w * 0.16, h * 0.22)
  return [
    0, 0,
    w, 0,
    w, bh,
    tail * 2.2, bh,
    tail * 1.1, h,
    tail * 0.9, bh,
    0, bh,
  ]
}

/**
 * Points for any polygon-based shape. Returns null for rect-based shapes.
 */
export function pointsFor(shape, w, h) {
  switch (shape) {
    case 'starburst': return burstPoints(w, h, 12, 0.62)
    case 'burst': return burstPoints(w, h, 20, 0.78)
    case 'seal': return sealPoints(w, h)
    case 'ribbon': return ribbonPoints(w, h)
    case 'banner': return bannerPoints(w, h)
    case 'speech_bubble': return speechPoints(w, h)
    default: return null
  }
}

/**
 * Text inset for a shape — burst/seal shapes need the text pulled well inside
 * so it doesn't spill over the spikes.
 */
export function textInsetFor(shape, w, h) {
  switch (shape) {
    case 'starburst':
    case 'burst':
    case 'seal':
      return { x: w * 0.2, y: h * 0.22, width: w * 0.6, height: h * 0.56 }
    case 'circle':
      return { x: w * 0.14, y: h * 0.16, width: w * 0.72, height: h * 0.68 }
    case 'speech_bubble':
      return { x: w * 0.08, y: 0, width: w * 0.84, height: h * 0.78 }
    case 'ribbon':
      return { x: w * 0.12, y: 0, width: w * 0.76, height: h }
    case 'banner':
      return { x: w * 0.06, y: 0, width: w * 0.88, height: h * 0.82 }
    default:
      return { x: 0, y: 0, width: w, height: h }
  }
}

export const SHAPE_LABELS = {
  none: 'No shape',
  rectangle: 'Rectangle',
  rounded: 'Rounded',
  circle: 'Circle',
  pill: 'Pill',
  ribbon: 'Ribbon',
  price_tag: 'Price tag',
  starburst: 'Starburst',
  burst: 'Burst',
  seal: 'Seal',
  banner: 'Banner',
  speech_bubble: 'Speech bubble',
}
