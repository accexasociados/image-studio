import { CircleCheck, CircleX, Cpu, Workflow } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { ReactNode } from 'react'
import { useHealth } from '../hooks/useHealth'

function Row({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-3 py-2">
      <span className="text-neutral-500">{icon}</span>
      <dt className="w-40 text-sm text-neutral-500">{label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  )
}

export function HealthStatus() {
  const { t } = useTranslation()
  const { data, isPending, isError, refetch } = useHealth()

  return (
    <section className="rounded-xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900">
      <h2 className="mb-3 text-base font-semibold">{t('health.title')}</h2>
      {isPending && <p className="text-sm text-neutral-500">{t('common.loading')}</p>}
      {isError && (
        <div className="flex items-center gap-3 text-sm text-red-600">
          <CircleX size={18} aria-hidden />
          <span>{t('health.apiDown')}</span>
          <button type="button" className="underline" onClick={() => void refetch()}>
            {t('common.retry')}
          </button>
        </div>
      )}
      {data && (
        <dl className="divide-y divide-neutral-100 dark:divide-neutral-800">
          <Row icon={<CircleCheck size={18} aria-hidden />} label={t('health.api')}>
            {t('health.apiOk', { version: data.version })}
          </Row>
          <Row icon={<Workflow size={18} aria-hidden />} label={t('health.pipelineMode')}>
            {data.pipeline_mode === 'real' ? t('health.modeReal') : t('health.modeStub')}
          </Row>
          <Row icon={<Cpu size={18} aria-hidden />} label={t('health.gpu')}>
            {data.gpu.available
              ? t('health.gpuValue', { name: data.gpu.name, vram: data.gpu.vram_mb })
              : t('health.gpuUnavailable')}
          </Row>
        </dl>
      )}
    </section>
  )
}
