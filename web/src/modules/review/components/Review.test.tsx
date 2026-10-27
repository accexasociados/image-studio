import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, vi } from 'vitest'
import type { Batch, ImageItem } from '@/shared/api/client'
import { ImageReviewer } from './ImageReviewer'
import { ReviewGrid } from './ReviewGrid'

afterEach(() => vi.unstubAllGlobals())

const batch: Batch = {
  id: 'b1',
  name: 'Lote',
  status: 'done',
  default_options: {
    presets: ['storefront'],
    layer_lines: 'keep',
    smooth_strength: 35,
    shadow: 'auto',
    shadow_intensity: 100,
    fill_ratio: null,
    upscale: 2,
    white_balance: true,
    generate_both_layer_variants: true,
    rotate: 0,
    crop: null,
  },
  created_at: '2026-01-01T00:00:00Z',
  counts: { total: 2, done: 2, review: 0, failed: 0 },
}

const item = (id: string, sku: string, status: ImageItem['status'] = 'done'): ImageItem => ({
  id,
  batch_id: 'b1',
  source: 'upload',
  original_path: `${id}.jpg`,
  sku,
  status,
  review_reasons: [],
  mask_edited: false,
  outputs: [
    { preset: 'storefront', path: `${id}.webp`, width: 2000, height: 2000, bytes: 1, variant: 'keep' },
    {
      preset: 'storefront',
      path: `${id}_smooth.webp`,
      width: 2000,
      height: 2000,
      bytes: 1,
      variant: 'smooth',
    },
  ],
})

function mockFetch(respond: (url: string, body: unknown) => unknown) {
  const fetchMock = vi.fn((url: string, init?: RequestInit) =>
    Promise.resolve(
      new Response(JSON.stringify(respond(url, init?.body ? JSON.parse(init.body as string) : undefined))),
    ),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>)
}

it('aprueba en bloque las fotos seleccionadas e informa las omitidas', async () => {
  const fetchMock = mockFetch((_url, body) =>
    (body as { image_ids: string[] }).image_ids.map((id) =>
      id === 'i2' ? item(id, 'B', 'pending') : item(id, 'A', 'approved'),
    ),
  )
  wrap(<ReviewGrid batchId="b1" images={[item('i1', 'A'), item('i2', 'B', 'pending')]} onOpen={vi.fn()} />)

  fireEvent.click(screen.getByLabelText('Seleccionar A'))
  fireEvent.click(screen.getByLabelText('Seleccionar B'))
  fireEvent.click(screen.getByRole('button', { name: 'Aprobar' }))

  expect(await screen.findByRole('status')).toHaveTextContent(
    '1 foto aprobada. 1 se omitió porque sigue en proceso.',
  )
  const [url, init] = fetchMock.mock.calls[0]
  expect(url).toBe('/api/v1/batches/b1/images/approve')
  expect(JSON.parse(init?.body as string)).toEqual({ image_ids: ['i1', 'i2'] })
})

it('el visor aprueba con A, navega con las flechas y elige una variante', async () => {
  const fetchMock = mockFetch((url, body) => ({
    ...item('i1', 'A', 'approved'),
    selected_variant: (body as { variant?: string } | null)?.variant ?? null,
    url,
  }))
  const onIndexChange = vi.fn()
  wrap(
    <ImageReviewer
      batch={batch}
      images={[item('i1', 'A'), item('i2', 'B')]}
      index={0}
      onIndexChange={onIndexChange}
      onClose={vi.fn()}
    />,
  )

  fireEvent.keyDown(window, { key: 'ArrowRight' })
  expect(onIndexChange).toHaveBeenCalledWith(1)

  fireEvent.keyDown(window, { key: 'a' })
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
  expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/images/i1/approve')

  fireEvent.click(screen.getByRole('tab', { name: 'Variante' }))
  fireEvent.click(screen.getAllByRole('button', { name: 'Aprobar con esta' })[1])
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  expect(JSON.parse(fetchMock.mock.calls[1][1]?.body as string)).toEqual({ variant: 'smooth' })
})
