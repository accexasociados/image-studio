import { AlertCircle, CheckCircle2, Clock3, Images, SearchX } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { ReactNode } from 'react'
import type { Batch } from '@/shared/api/client'
import { BatchStatusBadge } from './BatchStatusBadge'

interface BatchListProps {
  batches: Batch[]
  onSelect?: (batch: Batch) => void
}

function formatDate(value: string, language: string): string {
  return new Intl.DateTimeFormat(language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function BatchList({ batches, onSelect }: BatchListProps) {
  const { t, i18n } = useTranslation()

  if (batches.length === 0) {
    return (
      <div className="grid min-h-72 place-items-center px-6 py-12 text-center">
        <div>
          <span className="mx-auto mb-4 grid size-14 place-items-center rounded-2xl bg-indigo-50 text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-300">
            <SearchX size={26} aria-hidden />
          </span>
          <h3 className="font-semibold text-slate-900 dark:text-white">{t('batches.emptyTitle')}</h3>
          <p className="mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">
            {t('batches.emptyDescription')}
          </p>
        </div>
      </div>
    )
  }

  return (
    <ul className="divide-y divide-slate-100 dark:divide-slate-800">
      {batches.map((batch) => (
        <li
          key={batch.id}
          className="grid cursor-pointer gap-4 px-5 py-5 transition hover:bg-slate-50/80 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:px-6 dark:hover:bg-slate-800/30"
          onClick={() => onSelect?.(batch)}
        >
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2.5">
              <h3 className="truncate font-semibold text-slate-950 dark:text-white">{batch.name}</h3>
              <BatchStatusBadge status={batch.status} />
            </div>
            <p className="mt-1.5 flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              <Clock3 size={13} aria-hidden />
              {formatDate(batch.created_at, i18n.language)}
            </p>
          </div>
          <dl className="grid grid-cols-4 gap-2 sm:min-w-80">
            <Count icon={<Images size={14} />} label={t('batches.total')} value={batch.counts?.total ?? 0} />
            <Count
              icon={<CheckCircle2 size={14} />}
              label={t('batches.ready')}
              value={batch.counts?.done ?? 0}
              tone="text-emerald-600 dark:text-emerald-400"
            />
            <Count
              icon={<AlertCircle size={14} />}
              label={t('batches.review')}
              value={batch.counts?.review ?? 0}
              tone="text-amber-600 dark:text-amber-400"
            />
            <Count
              icon={<AlertCircle size={14} />}
              label={t('batches.failed')}
              value={batch.counts?.failed ?? 0}
              tone="text-red-600 dark:text-red-400"
            />
          </dl>
        </li>
      ))}
    </ul>
  )
}

function Count({
  icon,
  label,
  value,
  tone = 'text-slate-700 dark:text-slate-300',
}: {
  icon: ReactNode
  label: string
  value: number
  tone?: string
}) {
  return (
    <div className="rounded-xl bg-slate-50 px-2 py-2.5 text-center dark:bg-slate-800/70">
      <dt className="flex items-center justify-center gap-1 text-[11px] text-slate-500 dark:text-slate-400">
        {icon}
        <span className="truncate">{label}</span>
      </dt>
      <dd className={`mt-1 text-sm font-bold ${tone}`}>{value}</dd>
    </div>
  )
}
