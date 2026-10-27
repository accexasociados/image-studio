export type BrushMode = 'add' | 'erase'

export type Stroke = {
  mode: BrushMode
  /** Radio en píxeles de la foto original. */
  radius: number
  /** 0 = borde muy difuso, 100 = borde duro. */
  hardness: number
  points: { x: number; y: number }[]
}

/** Historial por trazos: deshacer vuelve a dibujar desde la máscara base en lugar de guardar
 * copias de una imagen de 12 MP en cada paso. */
export type MaskHistory = { done: Stroke[]; undone: Stroke[] }

export const emptyHistory: MaskHistory = { done: [], undone: [] }

export function pushStroke(history: MaskHistory, stroke: Stroke): MaskHistory {
  if (stroke.points.length === 0) return history
  return { done: [...history.done, stroke], undone: [] }
}

export function undo(history: MaskHistory): MaskHistory {
  const last = history.done.at(-1)
  if (!last) return history
  return { done: history.done.slice(0, -1), undone: [last, ...history.undone] }
}

export function redo(history: MaskHistory): MaskHistory {
  const [next, ...rest] = history.undone
  if (!next) return history
  return { done: [...history.done, next], undone: rest }
}

/** Puntos intermedios entre dos posiciones para que un trazo rápido no deje huecos. */
export function interpolate(
  from: { x: number; y: number },
  to: { x: number; y: number },
  spacing: number,
): { x: number; y: number }[] {
  const distance = Math.hypot(to.x - from.x, to.y - from.y)
  const steps = Math.max(1, Math.ceil(distance / Math.max(spacing, 0.5)))
  return Array.from({ length: steps }, (_, index) => {
    const ratio = (index + 1) / steps
    return { x: from.x + (to.x - from.x) * ratio, y: from.y + (to.y - from.y) * ratio }
  })
}

type Canvas2D = CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D

export function drawStroke(context: Canvas2D, stroke: Stroke): void {
  context.save()
  context.globalCompositeOperation = stroke.mode === 'add' ? 'source-over' : 'destination-out'
  const inner = stroke.radius * Math.min(Math.max(stroke.hardness, 0), 99) * 0.01
  for (const point of stroke.points) {
    const gradient = context.createRadialGradient(point.x, point.y, inner, point.x, point.y, stroke.radius)
    gradient.addColorStop(0, 'rgba(255,255,255,1)')
    gradient.addColorStop(1, 'rgba(255,255,255,0)')
    context.fillStyle = gradient
    context.beginPath()
    context.arc(point.x, point.y, stroke.radius, 0, Math.PI * 2)
    context.fill()
  }
  context.restore()
}
