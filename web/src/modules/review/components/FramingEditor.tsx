import { RotateCcw, RotateCw } from 'lucide-react'
import { useEffect, useRef, useState, type PointerEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { CropBox, ProcessOptions } from '@/shared/api/client'

type Rotation = ProcessOptions['rotate']
type Point = { x: number; y: number }

const clamp = (value: number) => Math.min(Math.max(value, 0), 1)

/** Gira la foto (en pasos de 90°) y recorta arrastrando sobre ella. El recorte se expresa en
 * fracciones de la foto ya girada, como lo espera `ProcessOptions.crop`. */
export function FramingEditor({
  src,
  rotate,
  crop,
  onChange,
}: {
  src: string
  rotate: Rotation
  crop: CropBox | null | undefined
  onChange: (rotate: Rotation, crop: CropBox | null) => void
}) {
  const { t } = useTranslation()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [image, setImage] = useState<HTMLImageElement | null>(null)
  const [dragStart, setDragStart] = useState<Point | null>(null)

  useEffect(() => {
    const element = new Image()
    element.onload = () => setImage(element)
    element.src = src
  }, [src])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !image) return
    const quarter = rotate === 90 || rotate === 270
    canvas.width = quarter ? image.naturalHeight : image.naturalWidth
    canvas.height = quarter ? image.naturalWidth : image.naturalHeight
    const context = canvas.getContext('2d')
    if (!context) return
    context.save()
    context.translate(canvas.width / 2, canvas.height / 2)
    context.rotate((rotate * Math.PI) / 180)
    context.drawImage(image, -image.naturalWidth / 2, -image.naturalHeight / 2)
    context.restore()
  }, [image, rotate])

  const toFraction = (event: PointerEvent<HTMLElement>): Point => {
    const rect = event.currentTarget.getBoundingClientRect()
    return {
      x: clamp((event.clientX - rect.left) / rect.width),
      y: clamp((event.clientY - rect.top) / rect.height),
    }
  }
  const updateCrop = (from: Point, to: Point) => {
    const box = {
      x: Math.min(from.x, to.x),
      y: Math.min(from.y, to.y),
      width: Math.abs(to.x - from.x),
      height: Math.abs(to.y - from.y),
    }
    if (box.width > 0.02 && box.height > 0.02) onChange(rotate, box)
  }
  const turn = (delta: 90 | -90) => onChange(((((rotate + delta) % 360) + 360) % 360) as Rotation, null)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <button
          type="button"
          onClick={() => turn(-90)}
          aria-label={t('review.framing.rotateLeft')}
          title={t('review.framing.rotateLeft')}
          className="rounded-lg border border-slate-200 p-2 dark:border-slate-700"
        >
          <RotateCcw size={16} aria-hidden />
        </button>
        <button
          type="button"
          onClick={() => turn(90)}
          aria-label={t('review.framing.rotateRight')}
          title={t('review.framing.rotateRight')}
          className="rounded-lg border border-slate-200 p-2 dark:border-slate-700"
        >
          <RotateCw size={16} aria-hidden />
        </button>
        <span className="text-slate-500">{t('review.framing.rotation', { degrees: rotate })}</span>
        {crop && (
          <button
            type="button"
            onClick={() => onChange(rotate, null)}
            className="ml-auto text-sm font-semibold text-indigo-600"
          >
            {t('review.framing.reset')}
          </button>
        )}
      </div>
      <p className="text-xs text-slate-500">{t('review.framing.hint')}</p>
      <div
        className="relative cursor-crosshair touch-none overflow-hidden rounded-lg bg-slate-100 select-none dark:bg-slate-800"
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId)
          setDragStart(toFraction(event))
        }}
        onPointerMove={(event) => dragStart && updateCrop(dragStart, toFraction(event))}
        onPointerUp={(event) => {
          if (dragStart) updateCrop(dragStart, toFraction(event))
          setDragStart(null)
        }}
      >
        <canvas ref={canvasRef} className="block h-auto w-full" />
        {crop && (
          <div
            aria-label={t('review.framing.area')}
            className="pointer-events-none absolute border-2 border-indigo-500 shadow-[0_0_0_9999px_rgba(15,23,42,0.45)]"
            style={{
              left: `${crop.x * 100}%`,
              top: `${crop.y * 100}%`,
              width: `${crop.width * 100}%`,
              height: `${crop.height * 100}%`,
            }}
          />
        )}
      </div>
    </div>
  )
}
