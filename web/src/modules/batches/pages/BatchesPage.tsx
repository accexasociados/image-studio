import { CircleX, Layers3, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { HealthStatus } from '@/modules/health/components/HealthStatus'
import { BatchList } from '../components/BatchList'
import { useBatches } from '../hooks/useBatches'

export function BatchesPage() {
  const { t } = useTranslation()
  const { data, isPending, isError, refetch } = useBatches()

  return (
    <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8 lg:py-10">
      <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="mb-2 flex items-center gap-2 text-xs font-bold tracking-widest text-indigo-600 uppercase dark:text-indigo-400">
            <Layers3 size={15} aria-hidden />
            {t('batches.eyebrow')}
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-slate-950 dark:text-white">
            {t('batches.title')}
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-500 sm:text-base dark:text-slate-400">
            {t('batches.description')}
          </p>
        </div>
        <button
          type="button"
          disabled
          title={t('batches.createComingSoon')}
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-semibold text-white shadow-sm shadow-indigo-600/20 opacity-60"
        >
          <Plus size={18} aria-hidden />
          {t('batches.create')}
        </button>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4 sm:px-6 dark:border-slate-800">
            <h2 className="font-semibold text-slate-900 dark:text-white">{t('batches.recent')}</h2>
            {data && (
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                {t('batches.count', { count: data.length })}
              </span>
            )}
          </div>
          {isPending && <BatchListSkeleton label={t('common.loading')} />}
          {isError && (
            <div className="flex min-h-64 flex-col items-center justify-center gap-3 px-6 text-center">
              <CircleX size={30} className="text-red-500" aria-hidden />
              <p className="text-sm text-slate-600 dark:text-slate-300">{t('batches.loadError')}</p>
              <button
                type="button"
                className="text-sm font-semibold text-indigo-600 hover:underline dark:text-indigo-400"
                onClick={() => void refetch()}
              >
                {t('common.retry')}
              </button>
            </div>
          )}
          {data && <BatchList batches={data} />}
        </section>
        <HealthStatus />
      </div>
    </main>
  )
}

function BatchListSkeleton({ label }: { label: string }) {
  return (
    <div className="divide-y divide-slate-100 dark:divide-slate-800" aria-label={label}>
      {[0, 1, 2].map((item) => (
        <div key={item} className="animate-pulse px-6 py-6">
          <div className="h-4 w-2/5 rounded bg-slate-200 dark:bg-slate-700" />
          <div className="mt-3 h-3 w-1/4 rounded bg-slate-100 dark:bg-slate-800" />
        </div>
      ))}
    </div>
  )
}
