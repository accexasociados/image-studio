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
  type Preset,
  type ProcessOptions,
} from '@/shared/api/client'

const PRESETS: Preset[] = ['storefront', 'instagram_feed', 'instagram_square', 'original_hd']
const SHADOWS: ProcessOptions['shadow'][] = ['none', 'soft', 'strong', 'auto']

// Respaldo mientras cargan los ajustes; los valores reales vienen de Ajustes > Procesamiento por defecto.
const FALLBACK_OPTIONS: ProcessOptions = {
  presets: ['storefront', 'instagram_feed'],
  layer_lines: 'keep',
  smooth_strength: 35,
  shadow: 'auto',
  shadow_intensity: 100,
  fill_ratio: null,
  upscale: 2,
  white_balance: true,
  generate_both_layer_variants: false,
}

const fieldClass =
  'mt-1.5 w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2.5 dark:border-slate-700'
const labelClass = 'block text-sm font-medium text-slate-700 dark:text-slate-200'

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

  const set = <K extends keyof ProcessOptions>(key: K, value: ProcessOptions[K]) =>
    setEdited({ ...options, [key]: value })
  const togglePreset = (preset: Preset) =>
    set(
      'presets',
      presets.includes(preset) ? presets.filter((item) => item !== preset) : [...presets, preset],
    )
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

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-200">
            {t('batches.presets')}
          </legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {PRESETS.map((preset) => (
              <label key={preset} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={presets.includes(preset)}
                  onChange={() => togglePreset(preset)}
                />
                {t(`batches.preset.${preset}`)}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className={labelClass}>
            {t('batches.layerLines')}
            <select
              value={options.layer_lines}
              onChange={(event) => set('layer_lines', event.target.value as ProcessOptions['layer_lines'])}
              className={fieldClass}
            >
              <option value="keep">{t('batches.layerKeep')}</option>
              <option value="smooth">{t('batches.layerSmooth')}</option>
            </select>
          </label>
          <label className={labelClass}>
            {t('batches.shadow')}
            <select
              value={options.shadow}
              onChange={(event) => set('shadow', event.target.value as ProcessOptions['shadow'])}
              className={fieldClass}
            >
              {SHADOWS.map((value) => (
                <option key={value} value={value}>
                  {t(`batches.shadowMode.${value}`)}
                </option>
              ))}
            </select>
          </label>
        </div>

        {(options.layer_lines === 'smooth' || options.generate_both_layer_variants) && (
          <label className={labelClass}>
            {t('batches.smoothStrength')}
            <input
              type="range"
              min="0"
              max="100"
              value={options.smooth_strength}
              onChange={(event) => set('smooth_strength', Number(event.target.value))}
              className="mt-2 w-full"
            />
            <span className="text-xs text-slate-500">{options.smooth_strength}%</span>
          </label>
        )}

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={options.generate_both_layer_variants}
            onChange={(event) => set('generate_both_layer_variants', event.target.checked)}
          />
          {t('batches.bothVariants')}
        </label>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className={labelClass}>
            {t('batches.shadowIntensity')}
            <input
              type="range"
              min="0"
              max="200"
              value={options.shadow_intensity}
              disabled={options.shadow === 'none'}
              onChange={(event) => set('shadow_intensity', Number(event.target.value))}
              className="mt-2 w-full"
            />
            <span className="text-xs text-slate-500">{options.shadow_intensity}%</span>
          </label>
          <label className={labelClass}>
            {t('batches.fillRatio')}
            <select
              value={options.fill_ratio ?? ''}
              onChange={(event) => set('fill_ratio', event.target.value ? Number(event.target.value) : null)}
              className={fieldClass}
            >
              <option value="">{t('batches.fillAuto')}</option>
              {[0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9].map((ratio) => (
                <option key={ratio} value={ratio}>
                  {Math.round(ratio * 100)}%
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className={labelClass}>
            {t('batches.upscale')}
            <select
              value={options.upscale}
              onChange={(event) => set('upscale', Number(event.target.value) as ProcessOptions['upscale'])}
              className={fieldClass}
            >
              <option value="1">1×</option>
              <option value="2">2×</option>
              <option value="4">4×</option>
            </select>
          </label>
          <label className="flex items-center gap-2 self-end pb-3 text-sm">
            <input
              type="checkbox"
              checked={options.white_balance}
              onChange={(event) => set('white_balance', event.target.checked)}
            />
            {t('batches.whiteBalance')}
          </label>
        </div>

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
