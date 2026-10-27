import { Download } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { Batch, ImageItem, Preset } from '@/shared/api/client'
import { outputPresets } from '../lib/outputs'

/** Un `.zip` por formato con las fotos aprobadas (nombradas por SKU, con la variante elegida). */
export function ExportBar({ batch, images }: { batch: Batch; images: ImageItem[] }) {
  const { t } = useTranslation()
  const approved = images.filter((image) => image.status === 'approved')
  const presets = [...new Set<Preset>(approved.flatMap((image) => outputPresets(image)))]

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="font-semibold text-slate-700 dark:text-slate-200">{t('review.export.title')}</span>
      <span className="text-slate-500">{t('review.export.count', { count: approved.length })}</span>
      {presets.length === 0 ? (
        <span className="text-slate-500">{t('review.export.none')}</span>
      ) : (
        presets.map((preset) => (
          <a
            key={preset}
            href={`/api/v1/batches/${batch.id}/download/${preset}.zip`}
            download
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 font-semibold text-indigo-600 hover:bg-indigo-50 dark:border-slate-600 dark:hover:bg-slate-800"
          >
            <Download size={15} aria-hidden />
            {t(`batches.preset.${preset}`)}
          </a>
        ))
      )}
    </div>
  )
}
