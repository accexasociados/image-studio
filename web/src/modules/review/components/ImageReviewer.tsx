import { AlertTriangle, Brush, CheckCircle2, ChevronLeft, ChevronRight, RotateCcw, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fileUrl, type Batch, type ImageItem, type Preset, type ProcessOptions } from '@/shared/api/client'
import { ProcessOptionsFields } from '@/shared/components/ProcessOptionsFields'
import { FALLBACK_OPTIONS } from '@/shared/components/processOptions'
import { useImageActions } from '../hooks/useImageActions'
import { useReviewShortcuts } from '../hooks/useReviewShortcuts'
import {
  APPROVABLE,
  REPROCESSABLE,
  imageLabel,
  outputPresets,
  outputVariants,
  pickOutput,
} from '../lib/outputs'
import { CompareView } from './CompareView'
import { FramingEditor } from './FramingEditor'
import { ImageStatusBadge } from './ImageStatusBadge'
import { MaskEditor } from './MaskEditor'

type Tab = 'options' | 'variant' | 'framing'

export function ImageReviewer({
  batch,
  images,
  index,
  onIndexChange,
  onClose,
}: {
  batch: Batch
  images: ImageItem[]
  index: number
  onIndexChange: (index: number) => void
  onClose: () => void
}) {
  const image = images[index]
  return image ? (
    // `key` reinicia los borradores (ajustes, encuadre) al cambiar de foto.
    <Reviewer
      key={image.id}
      batch={batch}
      image={image}
      position={{ index, total: images.length }}
      onPrevious={() => onIndexChange(Math.max(0, index - 1))}
      onNext={() => onIndexChange(Math.min(images.length - 1, index + 1))}
      onClose={onClose}
    />
  ) : null
}

function Reviewer({
  batch,
  image,
  position,
  onPrevious,
  onNext,
  onClose,
}: {
  batch: Batch
  image: ImageItem
  position: { index: number; total: number }
  onPrevious: () => void
  onNext: () => void
  onClose: () => void
}) {
  const { t } = useTranslation()
  const { approve, reprocess, resetOptions, saveMask, discardMask } = useImageActions(batch.id)
  const effective: ProcessOptions = {
    ...FALLBACK_OPTIONS,
    ...(image.options_override ?? batch.default_options),
  }
  const [tab, setTab] = useState<Tab>('options')
  const [draft, setDraft] = useState<ProcessOptions>(effective)
  const [chosenPreset, setPreset] = useState<Preset>()
  const [maskOpen, setMaskOpen] = useState(false)
  const preset = chosenPreset ?? outputPresets(image)[0]
  const output = pickOutput(image, preset)
  const variants = preset ? outputVariants(image, preset) : []
  const canApprove = APPROVABLE.includes(image.status)
  const canReprocess = REPROCESSABLE.includes(image.status)
  const busy = approve.isPending || reprocess.isPending || resetOptions.isPending || discardMask.isPending

  const doApprove = () => {
    if (canApprove && !busy) approve.mutate({ id: image.id, variant: image.selected_variant ?? undefined })
  }
  const doReprocess = (options?: ProcessOptions) => {
    if (canReprocess && !busy) reprocess.mutate({ id: image.id, options })
  }

  useReviewShortcuts(
    { onApprove: doApprove, onReprocess: () => doReprocess(), onPrevious, onNext, onClose },
    !maskOpen,
  )

  const tabs: Tab[] = ['options', 'variant', 'framing']
  const name = imageLabel(image)

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="reviewer-title"
      className="fixed inset-0 z-50 flex flex-col bg-slate-50 dark:bg-slate-950"
    >
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900">
        <h2 id="reviewer-title" className="truncate font-semibold text-slate-950 dark:text-white">
          {t('review.reviewer.title', { name })}
        </h2>
        <ImageStatusBadge status={image.status} />
        <span className="text-sm text-slate-500">
          {t('review.reviewer.position', { current: position.index + 1, total: position.total })}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={onPrevious}
            disabled={position.index === 0}
            aria-label={t('review.reviewer.previous')}
            title={t('review.reviewer.previous')}
            className="rounded-lg p-2 hover:bg-slate-100 disabled:opacity-40 dark:hover:bg-slate-800"
          >
            <ChevronLeft size={18} aria-hidden />
          </button>
          <button
            type="button"
            onClick={onNext}
            disabled={position.index === position.total - 1}
            aria-label={t('review.reviewer.next')}
            title={t('review.reviewer.next')}
            className="rounded-lg p-2 hover:bg-slate-100 disabled:opacity-40 dark:hover:bg-slate-800"
          >
            <ChevronRight size={18} aria-hidden />
          </button>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('common.close')}
            title={t('common.close')}
            className="rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X size={18} aria-hidden />
          </button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 gap-4 overflow-auto p-4 lg:grid-cols-[minmax(0,1fr)_24rem] lg:overflow-hidden">
        <section className="flex min-h-[60vh] flex-col gap-3 lg:min-h-0">
          {outputPresets(image).length > 1 && (
            <div className="flex flex-wrap gap-2" role="group" aria-label={t('review.reviewer.preset')}>
              {outputPresets(image).map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setPreset(item)}
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${item === preset ? 'bg-indigo-600 text-white' : 'bg-white text-slate-600 dark:bg-slate-800 dark:text-slate-300'}`}
                >
                  {t(`batches.preset.${item}`)}
                </button>
              ))}
            </div>
          )}
          <CompareView
            before={fileUrl(image.original_path, 1280)}
            after={output ? fileUrl(output.path, 1280) : undefined}
            afterFull={output ? fileUrl(output.path) : undefined}
          />
          {image.status === 'pending' || image.status === 'processing' ? (
            <p role="status" className="text-sm text-indigo-600">
              {t('review.reviewer.processing')}
            </p>
          ) : null}
          {image.status === 'failed' && image.error && (
            <p role="alert" className="text-sm text-red-600">
              {t('review.reviewer.failed', { message: image.error })}
            </p>
          )}
          {image.review_reasons && image.review_reasons.length > 0 && (
            <ul className="flex flex-wrap gap-2 text-xs text-amber-800 dark:text-amber-300">
              {image.review_reasons.map((reason) => (
                <li
                  key={reason}
                  className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-1 dark:bg-amber-950"
                >
                  <AlertTriangle size={13} aria-hidden />
                  {t(`review.reason.${reason}`)}
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className="flex min-h-0 flex-col rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
          <div role="tablist" className="flex border-b border-slate-100 dark:border-slate-800">
            {tabs.map((item) => (
              <button
                key={item}
                type="button"
                role="tab"
                aria-selected={tab === item}
                onClick={() => setTab(item)}
                className={`flex-1 px-3 py-3 text-sm font-semibold ${tab === item ? 'border-b-2 border-indigo-600 text-indigo-600' : 'text-slate-500'}`}
              >
                {t(`review.reviewer.tabs.${item}`)}
              </button>
            ))}
          </div>

          <div role="tabpanel" className="min-h-0 flex-1 overflow-auto p-4">
            {tab === 'options' && (
              <div className="space-y-4">
                <p className="text-xs text-slate-500">
                  {image.options_override
                    ? t('review.reviewer.usingOwnOptions')
                    : t('review.reviewer.usingBatchOptions')}
                </p>
                <ProcessOptionsFields value={draft} onChange={setDraft} compact />
                <button
                  type="button"
                  disabled={!canReprocess || busy}
                  onClick={() => doReprocess(draft)}
                  className="w-full rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {t('review.reviewer.applyOptions')}
                </button>
                {image.options_override && (
                  <button
                    type="button"
                    disabled={!canReprocess || busy}
                    onClick={() => resetOptions.mutate(image.id)}
                    className="w-full text-sm font-semibold text-indigo-600 disabled:opacity-50"
                  >
                    {t('review.reviewer.resetOptions')}
                  </button>
                )}
              </div>
            )}

            {tab === 'variant' &&
              (variants.length > 1 && preset ? (
                <div className="grid gap-3">
                  {variants.map((variant) => {
                    const candidate = pickOutput(image, preset, variant)
                    const chosen = image.status === 'approved' && image.selected_variant === variant
                    return (
                      <figure
                        key={variant}
                        className={`overflow-hidden rounded-xl border ${chosen ? 'border-emerald-500 ring-2 ring-emerald-500/30' : 'border-slate-200 dark:border-slate-700'}`}
                      >
                        {candidate && (
                          <img
                            src={fileUrl(candidate.path, 640)}
                            alt={t(`review.variant.${variant}`)}
                            className="aspect-square w-full bg-white object-contain"
                          />
                        )}
                        <figcaption className="flex items-center justify-between gap-2 p-2.5 text-sm">
                          <span>{t(`review.variant.${variant}`)}</span>
                          {chosen ? (
                            <span className="font-semibold text-emerald-600">
                              {t('review.variant.chosen')}
                            </span>
                          ) : (
                            <button
                              type="button"
                              disabled={!canApprove || busy}
                              onClick={() => approve.mutate({ id: image.id, variant })}
                              className="rounded-lg bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white disabled:opacity-50"
                            >
                              {t('review.variant.choose')}
                            </button>
                          )}
                        </figcaption>
                      </figure>
                    )
                  })}
                </div>
              ) : (
                <p className="text-sm text-slate-500">{t('review.variant.onlyOne')}</p>
              ))}

            {tab === 'framing' && (
              <div className="space-y-4">
                <FramingEditor
                  src={fileUrl(image.original_path, 640)}
                  rotate={draft.rotate}
                  crop={draft.crop}
                  onChange={(rotate, crop) => setDraft((current) => ({ ...current, rotate, crop }))}
                />
                <button
                  type="button"
                  disabled={!canReprocess || busy}
                  onClick={() => doReprocess(draft)}
                  className="w-full rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {t('review.framing.apply')}
                </button>
                <button
                  type="button"
                  disabled={!image.mask_path || !canReprocess}
                  onClick={() => setMaskOpen(true)}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold disabled:opacity-50 dark:border-slate-600"
                >
                  <Brush size={16} aria-hidden />
                  {t('review.mask.open')}
                </button>
                {!image.mask_path && <p className="text-xs text-slate-500">{t('review.mask.noMask')}</p>}
                {image.mask_edited && (
                  <div className="space-y-2 rounded-xl bg-indigo-50 p-3 text-xs text-indigo-900 dark:bg-indigo-950 dark:text-indigo-200">
                    <p>{t('review.mask.edited')}</p>
                    <button
                      type="button"
                      disabled={!canReprocess || busy}
                      onClick={() => discardMask.mutate(image.id)}
                      className="font-semibold text-indigo-600 disabled:opacity-50 dark:text-indigo-300"
                    >
                      {t('review.mask.discard')}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </aside>
      </div>

      <footer className="flex flex-wrap items-center gap-3 border-t border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900">
        <span className="mr-auto hidden text-xs text-slate-500 sm:inline">
          {t('review.reviewer.shortcuts')}
        </span>
        <button
          type="button"
          onClick={() => doReprocess()}
          disabled={!canReprocess || busy}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold disabled:opacity-50 dark:border-slate-600"
        >
          <RotateCcw size={16} aria-hidden />
          {t('review.reviewer.reprocess')}
        </button>
        <button
          type="button"
          onClick={doApprove}
          disabled={!canApprove || busy || image.status === 'approved'}
          className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          <CheckCircle2 size={16} aria-hidden />
          {image.status === 'approved' ? t('review.imageStatus.approved') : t('review.reviewer.approve')}
        </button>
      </footer>

      {maskOpen && image.mask_path && (
        <MaskEditor
          photoSrc={fileUrl(image.original_path)}
          maskSrc={fileUrl(image.mask_path)}
          saving={saveMask.isPending}
          failed={saveMask.isError}
          onClose={() => setMaskOpen(false)}
          onSave={(mask) => saveMask.mutate({ id: image.id, mask }, { onSuccess: () => setMaskOpen(false) })}
        />
      )}
    </div>
  )
}
