import { useTranslation } from 'react-i18next'
import type { Preset, ProcessOptions } from '@/shared/api/client'
import { fieldClass, labelClass } from './processOptions'

const PRESETS: Preset[] = ['storefront', 'instagram_feed', 'instagram_square', 'original_hd']
const SHADOWS: ProcessOptions['shadow'][] = ['none', 'soft', 'strong', 'auto']
const FILL_RATIOS = [0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9]

/** Campos de `ProcessOptions` (sin giro ni recorte, que se eligen sobre la foto). Los usan crear lote,
 * Ajustes > Procesamiento por defecto y el panel de ajustes por imagen. */
export function ProcessOptionsFields({
  value,
  onChange,
  compact = false,
}: {
  value: ProcessOptions
  onChange: (value: ProcessOptions) => void
  compact?: boolean
}) {
  const { t } = useTranslation()
  const presets = value.presets ?? []
  const set = <K extends keyof ProcessOptions>(key: K, next: ProcessOptions[K]) =>
    onChange({ ...value, [key]: next })
  const togglePreset = (preset: Preset) =>
    set(
      'presets',
      presets.includes(preset) ? presets.filter((item) => item !== preset) : [...presets, preset],
    )
  const grid = compact ? 'grid gap-4' : 'grid gap-4 sm:grid-cols-2'

  return (
    <div className="space-y-5">
      <fieldset>
        <legend className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-200">
          {t('batches.presets')}
        </legend>
        <div className={compact ? 'grid gap-2' : 'grid gap-2 sm:grid-cols-2'}>
          {PRESETS.map((preset) => (
            <label key={preset} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={presets.includes(preset)}
                disabled={presets.length === 1 && presets.includes(preset)}
                onChange={() => togglePreset(preset)}
              />
              {t(`batches.preset.${preset}`)}
            </label>
          ))}
        </div>
      </fieldset>

      <div className={grid}>
        <label className={labelClass}>
          {t('batches.layerLines')}
          <select
            value={value.layer_lines}
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
            value={value.shadow}
            onChange={(event) => set('shadow', event.target.value as ProcessOptions['shadow'])}
            className={fieldClass}
          >
            {SHADOWS.map((shadow) => (
              <option key={shadow} value={shadow}>
                {t(`batches.shadowMode.${shadow}`)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {(value.layer_lines === 'smooth' || value.generate_both_layer_variants) && (
        <label className={labelClass}>
          {t('batches.smoothStrength')}
          <input
            type="range"
            min="0"
            max="100"
            value={value.smooth_strength}
            onChange={(event) => set('smooth_strength', Number(event.target.value))}
            className="mt-2 w-full"
          />
          <span className="text-xs text-slate-500">{value.smooth_strength}%</span>
        </label>
      )}

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={value.generate_both_layer_variants}
          onChange={(event) => set('generate_both_layer_variants', event.target.checked)}
        />
        {t('batches.bothVariants')}
      </label>

      <div className={grid}>
        <label className={labelClass}>
          {t('batches.shadowIntensity')}
          <input
            type="range"
            min="0"
            max="200"
            value={value.shadow_intensity}
            disabled={value.shadow === 'none'}
            onChange={(event) => set('shadow_intensity', Number(event.target.value))}
            className="mt-2 w-full"
          />
          <span className="text-xs text-slate-500">{value.shadow_intensity}%</span>
        </label>
        <label className={labelClass}>
          {t('batches.fillRatio')}
          <select
            value={value.fill_ratio ?? ''}
            onChange={(event) => set('fill_ratio', event.target.value ? Number(event.target.value) : null)}
            className={fieldClass}
          >
            <option value="">{t('batches.fillAuto')}</option>
            {FILL_RATIOS.map((ratio) => (
              <option key={ratio} value={ratio}>
                {Math.round(ratio * 100)}%
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className={grid}>
        <label className={labelClass}>
          {t('batches.upscale')}
          <select
            value={value.upscale}
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
            checked={value.white_balance}
            onChange={(event) => set('white_balance', event.target.checked)}
          />
          {t('batches.whiteBalance')}
        </label>
      </div>
    </div>
  )
}
