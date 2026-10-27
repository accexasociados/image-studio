import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { SettingsPage } from './SettingsPage'
import { FALLBACK_OPTIONS } from '@/shared/components/processOptions'
import { ProcessOptionsFields } from '@/shared/components/ProcessOptionsFields'

afterEach(() => vi.unstubAllGlobals())

it('muestra el selector de modelo y deshabilita los modelos no instalados', async () => {
  const settings = {
    general: { language: 'es', public_base_url: 'http://localhost:5180' },
    processing_defaults: FALLBACK_OPTIONS,
    export: { presets: {}, background_hex: '#FFFFFF', filename_strategy: 'sku_then_slug' },
    telegram: {
      enabled: false,
      bot_token: { configured: false },
      allowed_chat_ids: [],
      notify_chat_ids: [],
      notify_on_start: true,
      notify_progress_step: 25,
      notify_on_finish: true,
      input_bot_enabled: false,
      send_results_as: 'zip',
    },
    notifications: { windows_toast: true, browser: true },
    hot_folder: { enabled: false, inbox_dir: null, outbox_dir: null, poll_seconds: 5 },
    importers: {
      google_drive_api_key: { configured: false },
      max_download_mb: 40,
      max_images_per_import: 300,
    },
    quality: {
      min_object_area: 0.05,
      max_object_area: 0.95,
      flag_touching_border: true,
      flag_multiple_objects: true,
      low_confidence_edge_ratio: 0.6,
    },
    pipeline: {
      segmentation_model: 'birefnet',
      segmentation_size: 1024,
      upscale_model: 'nmkd_siax',
      tile_size: 512,
      tile_overlap: 32,
      half_precision: false,
      detail_reinjection: 0.5,
    },
  }
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(settings)))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([{ id: 'nmkd_siax', scale: 4, size_mb: 10, license: 'MIT', installed: false }]),
        ),
      ),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <SettingsPage onClose={() => undefined} />
    </QueryClientProvider>,
  )
  fireEvent.click(await screen.findByRole('button', { name: 'Modelos' }))
  expect(await screen.findByRole('option', { name: /Siax 4×/ })).toBeDisabled()
  // Los demás campos de la sección siguen siendo editables.
  expect(screen.getByLabelText('Tamaño de segmentación')).toHaveValue(1024)
  expect(screen.getByLabelText('Media precisión')).not.toBeChecked()
})

it('permite usar la fidelidad de Ajustes o fijarla por imagen', () => {
  const onChange = vi.fn()
  render(<ProcessOptionsFields value={FALLBACK_OPTIONS} onChange={onChange} />)
  expect(screen.getByText('Usar la fidelidad de Ajustes')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Usar la fidelidad de Ajustes' }))
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ upscale_fidelity: 50 }))
})

it('trata las opciones sin fidelidad (guardadas antes) como "usar la de Ajustes"', () => {
  const { upscale_fidelity: _omit, ...legacy } = FALLBACK_OPTIONS
  render(<ProcessOptionsFields value={legacy} onChange={vi.fn()} />)
  expect(screen.getByRole('checkbox', { name: 'Usar la fidelidad de Ajustes' })).toBeChecked()
  expect(screen.getByRole('slider', { name: /Fidelidad al agrandar/ })).toBeDisabled()
})
