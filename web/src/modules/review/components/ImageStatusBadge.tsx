import { useTranslation } from 'react-i18next'
import type { ImageItem } from '@/shared/api/client'

const STYLES: Record<ImageItem['status'], string> = {
  pending: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  processing: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300',
  done: 'bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300',
  review: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
  failed: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300',
  approved: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
}

export function ImageStatusBadge({ status }: { status: ImageItem['status'] }) {
  const { t } = useTranslation()
  return (
    <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${STYLES[status]}`}>
      {t(`review.imageStatus.${status}`)}
    </span>
  )
}
