import { useState, type ChangeEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { apiPatch, apiUpload, type ImageItem } from '@/shared/api/client'

export function ImageMetadataTable({ batchId, images }: { batchId: string; images: ImageItem[] }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [saving, setSaving] = useState<string | null>(null)
  const [csvError, setCsvError] = useState(false)
  const save = async (image: ImageItem, field: 'product_name' | 'sku', value: string) => {
    setSaving(image.id)
    await apiPatch(`/images/${image.id}`, { [field]: value || null })
    await queryClient.invalidateQueries({ queryKey: ['batch-images', batchId] })
    setSaving(null)
  }
  const uploadCsv = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setCsvError(false)
    try {
      await apiUpload(`/batches/${batchId}/metadata-csv`, [file], () => undefined, 'file')
      await queryClient.invalidateQueries({ queryKey: ['batch-images', batchId] })
    } catch {
      setCsvError(true)
    }
    event.target.value = ''
  }

  return (
    <section className="border-t border-slate-100 p-5 dark:border-slate-800">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-semibold text-slate-950 dark:text-white">{t('batches.metadataTitle')}</h3>
        <label className="cursor-pointer rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold dark:border-slate-700">
          <input type="file" accept=".csv,text/csv" className="sr-only" onChange={uploadCsv} />
          {t('batches.importCsv')}
        </label>
      </div>
      {csvError && (
        <p role="alert" className="mb-3 text-sm text-red-600">
          {t('batches.csvError')}
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs text-slate-500 dark:border-slate-700">
              <th className="px-2 py-2">{t('batches.file')}</th>
              <th className="px-2 py-2">{t('batches.productName')}</th>
              <th className="px-2 py-2">{t('batches.sku')}</th>
            </tr>
          </thead>
          <tbody>
            {images.map((image) => (
              <tr key={image.id} className="border-b border-slate-100 dark:border-slate-800">
                <td className="max-w-48 truncate px-2 py-2 text-slate-500">{image.original_path}</td>
                <td className="px-2 py-2">
                  <input
                    defaultValue={image.product_name ?? ''}
                    onBlur={(event) => void save(image, 'product_name', event.target.value)}
                    className="w-full rounded border border-transparent bg-slate-50 px-2 py-1 focus:border-indigo-400 dark:bg-slate-800"
                    aria-label={`${t('batches.productName')} ${image.original_path}`}
                  />
                </td>
                <td className="px-2 py-2">
                  <input
                    defaultValue={image.sku ?? ''}
                    onBlur={(event) => void save(image, 'sku', event.target.value)}
                    className="w-full rounded border border-transparent bg-slate-50 px-2 py-1 focus:border-indigo-400 dark:bg-slate-800"
                    aria-label={`${t('batches.sku')} ${image.original_path}`}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {saving && <p className="mt-2 text-xs text-slate-500">{t('batches.saving')}</p>}
    </section>
  )
}
