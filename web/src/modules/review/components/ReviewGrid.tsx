import { AlertTriangle, CheckCircle2, Loader2, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fileUrl, type ImageItem } from '@/shared/api/client'
import { useImageActions } from '../hooks/useImageActions'
import { APPROVABLE, imageLabel, pickOutput } from '../lib/outputs'
import { ImageStatusBadge } from './ImageStatusBadge'

type Feedback = { kind: 'ok' | 'error'; text: string }

export function ReviewGrid({
  batchId,
  images,
  onOpen,
}: {
  batchId: string
  images: ImageItem[]
  onOpen: (index: number) => void
}) {
  const { t } = useTranslation()
  const { bulk } = useImageActions(batchId)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const visibleSelected = images.filter((image) => selected.has(image.id))

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const run = (action: 'approve' | 'reprocess') => {
    const ids = visibleSelected.map((image) => image.id)
    bulk.mutate(
      { action, ids },
      {
        onSuccess: (updated) => {
          const affected = updated.filter((image) =>
            action === 'approve' ? image.status === 'approved' : image.status === 'pending',
          ).length
          const skipped = updated.length - affected
          const done = t(action === 'approve' ? 'review.approvedCount' : 'review.reprocessedCount', {
            count: affected,
          })
          setFeedback({
            kind: 'ok',
            text: skipped ? `${done} ${t('review.skipped', { count: skipped })}` : done,
          })
          setSelected(new Set())
        },
        onError: () => setFeedback({ kind: 'error', text: t('review.actionError') }),
      },
    )
  }

  return (
    <div className="border-t border-slate-100 dark:border-slate-800">
      <div className="flex flex-wrap items-center gap-2 px-5 py-3 text-sm">
        <button
          type="button"
          onClick={() =>
            setSelected(
              visibleSelected.length === images.length ? new Set() : new Set(images.map((i) => i.id)),
            )
          }
          className="rounded-lg border border-slate-200 px-3 py-1.5 font-medium dark:border-slate-700"
          disabled={images.length === 0}
        >
          {visibleSelected.length === images.length && images.length > 0
            ? t('review.clearSelection')
            : t('review.selectAll')}
        </button>
        {visibleSelected.length > 0 && (
          <>
            <span className="text-slate-500">{t('review.selected', { count: visibleSelected.length })}</span>
            <button
              type="button"
              onClick={() => run('approve')}
              disabled={bulk.isPending}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 font-semibold text-white disabled:opacity-50"
            >
              <CheckCircle2 size={15} aria-hidden />
              {t('review.approveSelected')}
            </button>
            <button
              type="button"
              onClick={() => run('reprocess')}
              disabled={bulk.isPending}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 font-semibold disabled:opacity-50 dark:border-slate-600"
            >
              <RotateCcw size={15} aria-hidden />
              {t('review.reprocessSelected')}
            </button>
          </>
        )}
        {feedback && (
          <span
            role={feedback.kind === 'error' ? 'alert' : 'status'}
            className={feedback.kind === 'error' ? 'text-red-600' : 'text-emerald-700 dark:text-emerald-400'}
          >
            {feedback.text}
          </span>
        )}
      </div>

      <ul className="grid grid-cols-2 gap-3 px-5 pb-5 sm:grid-cols-3 lg:grid-cols-4">
        {images.map((image, index) => {
          const output = pickOutput(image)
          const name = imageLabel(image)
          const isSelected = selected.has(image.id)
          return (
            <li
              key={image.id}
              className={`group relative overflow-hidden rounded-xl border bg-white dark:bg-slate-900 ${isSelected ? 'border-indigo-500 ring-2 ring-indigo-500/40' : 'border-slate-200 dark:border-slate-700'}`}
            >
              <label className="absolute top-2 left-2 z-10 rounded-md bg-white/90 p-1 shadow-sm dark:bg-slate-900/90">
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggle(image.id)}
                  aria-label={t('review.selectImage', { name })}
                />
              </label>
              <button
                type="button"
                onClick={() => onOpen(index)}
                aria-label={t('review.openImage', { name })}
                className="block w-full text-left"
              >
                <div className="relative grid aspect-square place-items-center bg-white">
                  <img
                    src={fileUrl(output?.path ?? image.original_path, 320)}
                    alt=""
                    loading="lazy"
                    className={`max-h-full max-w-full object-contain ${output ? '' : 'opacity-60'}`}
                  />
                  {(image.status === 'pending' || image.status === 'processing') && (
                    <Loader2 className="absolute animate-spin text-indigo-500" size={28} aria-hidden />
                  )}
                </div>
                <div className="space-y-1.5 p-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">
                      {name}
                    </span>
                    <ImageStatusBadge status={image.status} />
                  </div>
                  {image.review_reasons && image.review_reasons.length > 0 && (
                    <p className="flex items-start gap-1 text-xs text-amber-700 dark:text-amber-400">
                      <AlertTriangle size={13} className="mt-px shrink-0" aria-hidden />
                      <span className="line-clamp-2">
                        {image.review_reasons.map((reason) => t(`review.reason.${reason}`)).join(' · ')}
                      </span>
                    </p>
                  )}
                  {!output && APPROVABLE.includes(image.status) && (
                    <p className="text-xs text-slate-500">{t('review.noOutput')}</p>
                  )}
                </div>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
