import { Brush, Eraser, Redo2, Undo2, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type PointerEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  drawStroke,
  emptyHistory,
  interpolate,
  pushStroke,
  redo,
  undo,
  type BrushMode,
  type MaskHistory,
  type Stroke,
} from '../lib/maskHistory'

// Resolución de trabajo de la vista; la máscara se edita a la resolución completa de la foto.
const VIEW_LONG_SIDE = 1600
const TINT = 'rgba(239, 68, 68, 0.5)'

type Loaded = { photo: HTMLImageElement; base: HTMLCanvasElement; work: HTMLCanvasElement; scale: number }

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = reject
    image.src = src
  })
}

/** Máscara gris (L) -> lienzo blanco con alfa = máscara, a la resolución de la foto. */
function maskToAlpha(mask: HTMLImageElement, width: number, height: number): HTMLCanvasElement {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) return canvas
  context.drawImage(mask, 0, 0, width, height)
  const pixels = context.getImageData(0, 0, width, height)
  const data = pixels.data
  for (let index = 0; index < data.length; index += 4) {
    data[index + 3] = data[index]
    data[index] = 255
    data[index + 1] = 255
    data[index + 2] = 255
  }
  context.putImageData(pixels, 0, 0)
  return canvas
}

/** El lienzo de trabajo ya lleva la máscara en el alfa, que es el canal que usa
 * `PUT /images/{id}/mask` cuando el PNG trae transparencia (el navegador siempre la incluye). */
function alphaToPng(alpha: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) =>
    alpha.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('toBlob'))), 'image/png'),
  )
}

export function MaskEditor({
  photoSrc,
  maskSrc,
  saving,
  failed,
  onSave,
  onClose,
}: {
  photoSrc: string
  maskSrc: string
  saving: boolean
  failed: boolean
  onSave: (mask: Blob) => void
  onClose: () => void
}) {
  const { t } = useTranslation()
  const viewRef = useRef<HTMLCanvasElement>(null)
  const strokeRef = useRef<Stroke | null>(null)
  const finishedRef = useRef<Stroke | null>(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  })
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [history, setHistory] = useState<MaskHistory>(emptyHistory)
  const [mode, setMode] = useState<BrushMode>('add')
  const [size, setSize] = useState(40)
  const [hardness, setHardness] = useState(60)

  useEffect(() => {
    let cancelled = false
    void Promise.all([loadImage(photoSrc), loadImage(maskSrc)]).then(([photo, mask]) => {
      if (cancelled) return
      const base = maskToAlpha(mask, photo.naturalWidth, photo.naturalHeight)
      const work = document.createElement('canvas')
      work.width = base.width
      work.height = base.height
      const scale = Math.min(1, VIEW_LONG_SIDE / Math.max(photo.naturalWidth, photo.naturalHeight))
      setLoaded({ photo, base, work, scale })
    })
    return () => {
      cancelled = true
    }
  }, [photoSrc, maskSrc])

  const render = useCallback(() => {
    const view = viewRef.current
    if (!view || !loaded) return
    const work = loaded.work
    const width = Math.round(loaded.photo.naturalWidth * loaded.scale)
    const height = Math.round(loaded.photo.naturalHeight * loaded.scale)
    if (view.width !== width || view.height !== height) {
      view.width = width
      view.height = height
    }
    const context = view.getContext('2d')
    if (!context) return
    context.globalCompositeOperation = 'source-over'
    context.drawImage(loaded.photo, 0, 0, width, height)
    // Tinte rojo sobre el fondo (lo que queda fuera de la máscara).
    const tint = document.createElement('canvas')
    tint.width = width
    tint.height = height
    const tintContext = tint.getContext('2d')
    if (!tintContext) return
    tintContext.fillStyle = TINT
    tintContext.fillRect(0, 0, width, height)
    tintContext.globalCompositeOperation = 'destination-out'
    tintContext.drawImage(work, 0, 0, width, height)
    context.drawImage(tint, 0, 0)
  }, [loaded])

  // Se reconstruye desde la base solo al deshacer o rehacer: un trazo nuevo ya quedó pintado.
  useEffect(() => {
    if (!loaded) return
    const finished = finishedRef.current
    finishedRef.current = null
    if (finished && history.done.at(-1) === finished) {
      render()
      return
    }
    const context = loaded.work.getContext('2d', { willReadFrequently: true })
    if (!context) return
    context.clearRect(0, 0, loaded.work.width, loaded.work.height)
    context.drawImage(loaded.base, 0, 0)
    history.done.forEach((stroke) => drawStroke(context, stroke))
    render()
  }, [loaded, history, render])

  const toPhoto = (event: PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const photo = loaded?.photo
    if (!photo) return { x: 0, y: 0 }
    return {
      x: ((event.clientX - rect.left) / rect.width) * photo.naturalWidth,
      y: ((event.clientY - rect.top) / rect.height) * photo.naturalHeight,
    }
  }
  // El tamaño del pincel se elige en píxeles de pantalla y se lleva a píxeles de la foto.
  const radiusInPhoto = (event: PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    return (size / 2) * ((loaded?.photo.naturalWidth ?? rect.width) / rect.width)
  }

  const paint = (points: { x: number; y: number }[]) => {
    const stroke = strokeRef.current
    const context = loaded?.work.getContext('2d', { willReadFrequently: true })
    if (!stroke || !context) return
    drawStroke(context, { ...stroke, points })
    stroke.points.push(...points)
    requestAnimationFrame(render)
  }

  const finishStroke = () => {
    const stroke = strokeRef.current
    strokeRef.current = null
    if (!stroke) return
    finishedRef.current = stroke
    setHistory((current) => pushStroke(current, stroke))
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        onCloseRef.current()
        return
      }
      if (!(event.ctrlKey || event.metaKey)) return
      const key = event.key.toLowerCase()
      if (key === 'z' && !event.shiftKey) setHistory(undo)
      else if (key === 'y' || (key === 'z' && event.shiftKey)) setHistory(redo)
      else return
      event.preventDefault()
      event.stopPropagation()
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [])

  const save = () => {
    if (loaded) void alphaToPng(loaded.work).then(onSave)
  }

  const toolClass = (active: boolean) =>
    `inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold ${active ? 'bg-indigo-600 text-white' : 'border border-slate-300 dark:border-slate-600'}`

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="mask-editor-title"
      className="fixed inset-0 z-[60] flex flex-col bg-slate-950/95 text-slate-100"
    >
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-800 px-4 py-3">
        <h2 id="mask-editor-title" className="mr-auto font-semibold">
          {t('review.mask.title')}
        </h2>
        <button type="button" onClick={() => setMode('add')} className={toolClass(mode === 'add')}>
          <Brush size={15} aria-hidden />
          {t('review.mask.add')}
        </button>
        <button type="button" onClick={() => setMode('erase')} className={toolClass(mode === 'erase')}>
          <Eraser size={15} aria-hidden />
          {t('review.mask.erase')}
        </button>
        <label className="flex items-center gap-2 text-sm">
          {t('review.mask.size')}
          <input
            type="range"
            min="4"
            max="200"
            value={size}
            onChange={(event) => setSize(Number(event.target.value))}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          {t('review.mask.hardness')}
          <input
            type="range"
            min="0"
            max="100"
            value={hardness}
            onChange={(event) => setHardness(Number(event.target.value))}
          />
        </label>
        <button
          type="button"
          onClick={() => setHistory(undo)}
          disabled={history.done.length === 0}
          aria-label={t('review.mask.undo')}
          title={t('review.mask.undo')}
          className="rounded-lg border border-slate-600 p-2 disabled:opacity-40"
        >
          <Undo2 size={15} aria-hidden />
        </button>
        <button
          type="button"
          onClick={() => setHistory(redo)}
          disabled={history.undone.length === 0}
          aria-label={t('review.mask.redo')}
          title={t('review.mask.redo')}
          className="rounded-lg border border-slate-600 p-2 disabled:opacity-40"
        >
          <Redo2 size={15} aria-hidden />
        </button>
        <button
          type="button"
          onClick={save}
          disabled={!loaded || saving || history.done.length === 0}
          className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          {saving ? t('review.mask.saving') : t('review.mask.save')}
        </button>
        <button
          type="button"
          onClick={onClose}
          aria-label={t('review.mask.cancel')}
          title={t('review.mask.cancel')}
          className="rounded-lg p-2 hover:bg-slate-800"
        >
          <X size={18} aria-hidden />
        </button>
      </div>
      <p className="px-4 pt-2 text-xs text-slate-400">
        {t('review.mask.hint')}
        {failed && (
          <span role="alert" className="ml-2 text-red-400">
            {t('review.mask.error')}
          </span>
        )}
      </p>
      <div className="grid min-h-0 flex-1 place-items-center overflow-auto p-4">
        {!loaded && <p className="text-sm text-slate-400">{t('review.mask.loading')}</p>}
        <canvas
          ref={viewRef}
          aria-label={t('review.mask.canvas')}
          className={`max-h-full max-w-full touch-none ${loaded ? 'cursor-crosshair' : 'hidden'}`}
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId)
            const point = toPhoto(event)
            strokeRef.current = { mode, radius: radiusInPhoto(event), hardness, points: [] }
            paint([point])
          }}
          onPointerMove={(event) => {
            const stroke = strokeRef.current
            const last = stroke?.points.at(-1)
            if (!stroke || !last) return
            paint(interpolate(last, toPhoto(event), stroke.radius * 0.3))
          }}
          onPointerUp={finishStroke}
          onPointerCancel={finishStroke}
        />
      </div>
    </div>
  )
}
