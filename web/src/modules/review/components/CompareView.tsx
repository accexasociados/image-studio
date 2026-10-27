import { Maximize2, Minimize2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

/** Antes (foto original) y después (resultado) en el mismo marco, con un deslizador; o el
 * resultado al 100 % con desplazamiento para revisar bordes y líneas de capa. */
export function CompareView({
  before,
  after,
  afterFull,
}: {
  before: string
  after?: string
  afterFull?: string
}) {
  const { t } = useTranslation()
  const [split, setSplit] = useState(50)
  const [actualSize, setActualSize] = useState(false)

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="flex items-center justify-between gap-2 text-xs font-semibold text-slate-500">
        <span>{actualSize ? t('review.reviewer.after') : t('review.reviewer.before')}</span>
        {after && (
          <button
            type="button"
            onClick={() => setActualSize((value) => !value)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1 text-slate-600 dark:border-slate-700 dark:text-slate-300"
          >
            {actualSize ? <Minimize2 size={14} aria-hidden /> : <Maximize2 size={14} aria-hidden />}
            {actualSize ? t('review.reviewer.zoomFit') : t('review.reviewer.zoom100')}
          </button>
        )}
        {!actualSize && <span>{t('review.reviewer.after')}</span>}
      </div>

      {actualSize && afterFull ? (
        <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-slate-200 bg-white dark:border-slate-700">
          <img src={afterFull} alt={t('review.reviewer.after')} className="max-w-none" />
        </div>
      ) : (
        <div className="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-slate-200 bg-white select-none dark:border-slate-700">
          {after ? (
            <img
              src={after}
              alt={t('review.reviewer.after')}
              className="absolute inset-0 h-full w-full object-contain"
              draggable={false}
            />
          ) : null}
          <div
            className="absolute inset-0 bg-slate-100 dark:bg-slate-800"
            style={after ? { clipPath: `inset(0 ${100 - split}% 0 0)` } : undefined}
          >
            <img
              src={before}
              alt={t('review.reviewer.before')}
              className="h-full w-full object-contain"
              draggable={false}
            />
          </div>
          {after && (
            <>
              <div
                className="pointer-events-none absolute inset-y-0 w-0.5 bg-indigo-500 shadow"
                style={{ left: `${split}%` }}
              />
              <input
                type="range"
                min="0"
                max="100"
                value={split}
                onChange={(event) => setSplit(Number(event.target.value))}
                aria-label={t('review.reviewer.compareSlider')}
                className="absolute inset-x-3 bottom-3 accent-indigo-600"
              />
            </>
          )}
        </div>
      )}
    </div>
  )
}
