import { ArrowLeft, ImageOff, RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { Batch } from '@/shared/api/client'
import { ExportBar } from '@/modules/review/components/ExportBar'
import { ImageReviewer } from '@/modules/review/components/ImageReviewer'
import { ReviewGrid } from '@/modules/review/components/ReviewGrid'
import { useBatchImages } from '@/modules/review/hooks/useBatchImages'
import { ImageMetadataTable } from './ImageMetadataTable'

type Filter = 'all' | 'done' | 'review' | 'failed'

export function BatchDetailPanel({ batch, onBack }: { batch: Batch; onBack: () => void }) {
  const { t } = useTranslation()
  const [filter, setFilter] = useState<Filter>('all')
  const [reviewing, setReviewing] = useState<number | null>(null)
  const { data: images = [], isPending, refetch } = useBatchImages(batch.id)

  const visible = useMemo(
    () =>
      images.filter(
        (image) =>
          filter === 'all' || image.status === filter || (filter === 'done' && image.status === 'approved'),
      ),
    [images, filter],
  )
  const counts = {
    all: images.length,
    done: images.filter((image) => image.status === 'done' || image.status === 'approved').length,
    review: images.filter((image) => image.status === 'review').length,
    failed: images.filter((image) => image.status === 'failed').length,
  }
  const progress = counts.all ? Math.round((counts.done / counts.all) * 100) : 0

  return (
    <section
      className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"
      aria-labelledby="batch-detail-title"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4 dark:border-slate-800">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-2 text-sm font-semibold text-indigo-600"
        >
          <ArrowLeft size={16} aria-hidden />
          {t('batches.back')}
        </button>
        <button
          type="button"
          onClick={() => void refetch()}
          className="inline-flex items-center gap-2 text-sm text-slate-500"
          aria-label={t('batches.refresh')}
        >
          <RefreshCw size={16} aria-hidden />
          {t('batches.refresh')}
        </button>
      </div>
      <div className="px-5 py-5 sm:px-6">
        <h2 id="batch-detail-title" className="text-2xl font-bold text-slate-950 dark:text-white">
          {batch.name}
        </h2>
        <div className="mt-4 flex items-center gap-3">
          <progress className="h-2 flex-1" max={100} value={progress} aria-label={t('batches.progress')} />
          <span className="text-sm font-semibold">{progress}%</span>
        </div>
        <div className="mt-4">
          <ExportBar batch={batch} images={images} />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {(['all', 'done', 'review', 'failed'] as Filter[]).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setFilter(value)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold ${filter === value ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'}`}
            >
              {t(`batches.filter.${value}`)} ({counts[value]})
            </button>
          ))}
        </div>
      </div>
      {isPending && <p className="px-6 pb-6 text-sm text-slate-500">{t('common.loading')}</p>}
      {!isPending && visible.length === 0 && (
        <div className="grid min-h-48 place-items-center px-6 pb-6 text-center">
          <ImageOff className="text-slate-400" aria-hidden />
          <p className="mt-2 text-sm text-slate-500">{t('batches.noImages')}</p>
        </div>
      )}
      <ReviewGrid batchId={batch.id} images={visible} onOpen={setReviewing} />
      {reviewing !== null && (
        <ImageReviewer
          batch={batch}
          images={visible}
          index={reviewing}
          onIndexChange={setReviewing}
          onClose={() => setReviewing(null)}
        />
      )}
      <ImageMetadataTable batchId={batch.id} images={images} />
    </section>
  )
}
