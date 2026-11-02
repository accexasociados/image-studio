import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { SettingsPage } from './SettingsPage'

afterEach(() => vi.unstubAllGlobals())

it('muestra las secciones de ajustes recibidas desde la API', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          general: { language: 'es', public_base_url: 'http://localhost:5180' },
          processing_defaults: {
            presets: ['storefront'],
            layer_lines: 'keep',
            smooth_strength: 35,
            shadow: 'auto',
            shadow_intensity: 100,
            fill_ratio: null,
            upscale: 2,
            white_balance: true,
            generate_both_layer_variants: false,
          },
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
            upscale_model: 'lanczos',
            tile_size: 512,
            tile_overlap: 32,
            half_precision: false,
            detail_reinjection: 0.6,
          },
        }),
      ),
    ),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <SettingsPage onClose={() => undefined} />
    </QueryClientProvider>,
  )
  expect(await screen.findByText('Procesamiento por defecto')).toBeInTheDocument()
  expect(screen.getByText('URL pública')).toBeInTheDocument()
})

it('Formatos de salida conserva sus campos y agrega la escena debajo', async () => {
  const settings = {
    export: {
      presets: {},
      background_hex: '#FFFFFF',
      filename_strategy: 'sku_then_slug',
      scene: {
        style: 'studio',
        studio_wall_hex: '#FFFFFF',
        studio_floor_hex: '#ECEAE6',
        brand_hex: '#C9D9EA',
        pedestal_hex: '#E4DFD6',
        reflection: 14,
        default_background_id: null,
      },
    },
  }
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      Promise.resolve(new Response(url.endsWith('/settings') ? JSON.stringify(settings) : '[]')),
    ),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <SettingsPage onClose={() => undefined} />
    </QueryClientProvider>,
  )
  ;(await screen.findByRole('button', { name: 'Formatos de salida' })).click()

  expect(await screen.findByLabelText('Nombres de archivo')).toBeInTheDocument()
  expect(screen.getByLabelText('Color del fondo liso')).toHaveValue('#FFFFFF')
  expect(screen.getByLabelText('Fondo')).toHaveValue('studio')
  expect(screen.getByLabelText(/Reflejo en el piso/)).toHaveValue('14')
  expect(screen.getByText('Biblioteca de fondos')).toBeInTheDocument()
})

it('la sección IA elige el servicio y no reenvía una clave sin tocar', async () => {
  const ai = {
    provider: 'none',
    fal_api_key: { configured: true },
    fal_model: 'fal-ai/flux-pro/kontext',
    openai_api_key: { configured: false },
    openai_model: 'gpt-image-2',
    openai_quality: 'medium',
    extra_prompt: '',
    timeout_seconds: 120,
  }
  const fetchMock = vi.fn((url: string, init?: RequestInit) =>
    Promise.resolve(
      new Response(url.endsWith('/settings') || init?.method === 'PUT' ? JSON.stringify({ ai }) : '[]'),
    ),
  )
  vi.stubGlobal('fetch', fetchMock)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <SettingsPage onClose={() => undefined} />
    </QueryClientProvider>,
  )
  ;(await screen.findByRole('button', { name: 'IA' })).click()

  const provider = await screen.findByLabelText('Servicio de IA')
  expect(screen.getByRole('option', { name: 'Flux Kontext (fal.ai)' })).toBeInTheDocument()
  expect(screen.getByLabelText('Clave de fal.ai (Flux Kontext)')).toHaveAttribute(
    'placeholder',
    'Configurado · escribe para reemplazar',
  )
  fireEvent.change(provider, { target: { value: 'fal_flux_kontext' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }))

  await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(true))
  const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
  const body = JSON.parse(String(put?.[1]?.body)) as Record<string, unknown>
  expect(put?.[0]).toContain('/settings/ai')
  expect(body.provider).toBe('fal_flux_kontext')
  expect(body).not.toHaveProperty('fal_api_key')
})
