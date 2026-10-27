import type { ImageItem, LayerLines, OutputFile, Preset } from '@/shared/api/client'

const PRESET_ORDER: Preset[] = ['storefront', 'instagram_feed', 'instagram_square', 'original_hd']

export function outputPresets(image: ImageItem): Preset[] {
  const present = new Set(image.outputs?.map((output) => output.preset))
  return PRESET_ORDER.filter((preset) => present.has(preset))
}

export function outputVariants(image: ImageItem, preset: Preset): LayerLines[] {
  const variants = new Set(
    image.outputs?.filter((output) => output.preset === preset).map((output) => output.variant ?? 'keep'),
  )
  return (['keep', 'smooth'] as LayerLines[]).filter((variant) => variants.has(variant))
}

/** Salida a mostrar: el preset pedido (o el primero) y la variante elegida (o la primera). */
export function pickOutput(
  image: ImageItem,
  preset?: Preset,
  variant?: LayerLines | null,
): OutputFile | undefined {
  const chosenPreset = preset && outputPresets(image).includes(preset) ? preset : outputPresets(image)[0]
  const candidates = image.outputs?.filter((output) => output.preset === chosenPreset) ?? []
  const wanted = variant ?? image.selected_variant ?? 'keep'
  return candidates.find((output) => (output.variant ?? 'keep') === wanted) ?? candidates[0]
}

export function imageLabel(image: ImageItem): string {
  return image.sku || image.product_name || image.source_ref || image.id
}

export const APPROVABLE: ImageItem['status'][] = ['done', 'review', 'approved']
export const REPROCESSABLE: ImageItem['status'][] = ['done', 'review', 'failed', 'approved']
