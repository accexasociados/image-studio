import { Upload, X } from 'lucide-react'
import { useState, type ChangeEvent, type DragEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  apiGet,
  apiPost,
  apiUpload,
  type AppSettingsPublic,
  type Batch,
  type ProcessOptions,
} from '@/shared/api/client'
import { ProcessOptionsFields } from '@/shared/components/ProcessOptionsFields'
import { FALLBACK_OPTIONS, fieldClass, labelClass } from '@/shared/components/processOptions'

function isAccepted(file: File) {
  return /^image\/(jpeg|png|webp)$/.test(file.type) || file.name.toLowerCase().endsWith('.zip')
}

export function CreateBatchPanel({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const settings = useQuery({ queryKey: ['settings'], queryFn: () => apiGet<AppSettingsPublic>('/settings') })
  const [name, setName] = useState('')
  const [edited, setEdited] = useState<ProcessOptions | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [progress, setProgress] = useState(0)
  const [batchId, setBatchId] = useState<string | null>(null)
  const options = edited ?? settings.data?.processing_defaults ?? FALLBACK_OPTIONS
  const presets = options.presets ?? []

  const create = useMutation({
    mutationFn: async () => {
      // Si la carga falló, el reintento reutiliza el lote ya creado en vez de duplicarlo.
      const id =
        batchId ?? (await apiPost<Batch>('/batches', { name: name.trim(), default_options: options })).id
      setBatchId(id)
      if (files.length) await apiUpload(`/batches/${id}/images`, files, setProgress)
    },
    onSuccess: onClose,
    onSettled: () => void queryClient.invalidateQueries({ queryKey: ['batches'] }),
  })

  const addFiles = (incoming: File[]) => setFiles((current) => [...current, ...incoming.filter(isAccepted)])
  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    addFiles(Array.from(event.dataTransfer.files))
  }
  const onInput = (event: ChangeEvent<HTMLInputElement>) => addFiles(Array.from(event.target.files ?? []))

  return (
    <section
      className="rounded-2xl border border-indigo-200 bg-white p-5 shadow-sm sm:p-6 dark:border-indigo-900 dark:bg-slate-900"
      aria-labelledby="create-batch-title"
    >
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 id="create-batch-title" className="text-lg font-semibold text-slate-950 dark:text-white">
            {t('batches.createTitle')}
          </h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{t('batches.createDescription')}</p>
        </div>
        <button type="button" onClick={onClose} aria-label={t('common.close')}>
          <X size={19} />
        </button>
      </div>

      <form
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate()
        }}
      >
        <label className={labelClass}>
          {t('batches.name')}
          <input
            required
            maxLength={120}
            value={name}
            disabled={batchId !== null}
            onChange={(event) => setName(event.target.value)}
            placeholder={t('batches.namePlaceholder')}
            className={fieldClass}
          />
        </label>

        <ProcessOptionsFields value={options} onChange={setEdited} />

        <label
          onDragOver={(event) => event.preventDefault()}
          onDrop={onDrop}
          className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 px-5 py-7 text-center dark:border-slate-700"
        >
          <Upload size={24} className="mb-2 text-indigo-500" aria-hidden />
          <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            {t('batches.dropFiles')}
          </span>
          <span className="mt-1 text-xs text-slate-500">{t('batches.fileTypes')}</span>
          <input
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp,.zip"
            className="sr-only"
            onChange={onInput}
          />
          {files.length > 0 && (
            <span className="mt-2 text-xs text-indigo-600">
              {t('batches.filesSelected', { count: files.length })}
            </span>
          )}
        </label>

        {create.isPending && files.length > 0 && (
          <progress
            className="h-2 w-full"
            max={100}
            value={progress}
            aria-label={t('batches.uploadProgress')}
          />
        )}
        {create.isError && (
          <p role="alert" className="text-sm text-red-600">
            {t('batches.createError')}
          </p>
        )}
        <button
          type="submit"
          disabled={create.isPending || presets.length === 0}
          className="w-full rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
        >
          {create.isPending ? t('batches.creating') : t('batches.createSubmit')}
        </button>
      </form>
    </section>
  )
}
