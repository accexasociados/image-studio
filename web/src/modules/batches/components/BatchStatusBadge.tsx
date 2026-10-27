import type { Batch } from '@/shared/api/client'
import { useTranslation } from 'react-i18next'

const styles: Record<Batch['status'], string> = {
  draft: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  queued: 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300',
  processing: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300',
  done: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300',
  failed: 'bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-300',
  cancelled: 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300',
}

export function BatchStatusBadge({ status }: { status: Batch['status'] }) {
  const { t } = useTranslation()
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${styles[status]}`}>
      {t(`batches.status.${status}`)}
    </span>
  )
}
