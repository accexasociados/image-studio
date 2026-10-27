import type { ProcessOptions } from '@/shared/api/client'

// Respaldo mientras cargan los ajustes; los valores reales vienen de Ajustes > Procesamiento por defecto.
export const FALLBACK_OPTIONS: ProcessOptions = {
  presets: ['storefront', 'instagram_feed'],
  layer_lines: 'keep',
  smooth_strength: 35,
  shadow: 'auto',
  shadow_intensity: 100,
  fill_ratio: null,
  upscale: 2,
  white_balance: true,
  generate_both_layer_variants: false,
  rotate: 0,
  crop: null,
}

export const fieldClass =
  'mt-1.5 w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2.5 dark:border-slate-700'
export const labelClass = 'block text-sm font-medium text-slate-700 dark:text-slate-200'
