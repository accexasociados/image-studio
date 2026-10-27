import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { BatchDetailPanel } from './BatchDetailPanel'

class FakeEventSource {
  addEventListener() {}
  close() {}
}

afterEach(() => vi.unstubAllGlobals())

it('carga imágenes desde la API y filtra las fallidas', async () => {
  vi.stubGlobal('EventSource', FakeEventSource)
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: '1',
            batch_id: 'b1',
            source: 'upload',
            original_path: 'one.jpg',
            status: 'done',
            product_name: 'Pieza uno',
          },
          {
            id: '2',
            batch_id: 'b1',
            source: 'upload',
            original_path: 'two.jpg',
            status: 'failed',
            product_name: 'Pieza dos',
          },
        ]),
      ),
    ),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <BatchDetailPanel
        batch={{
          id: 'b1',
          name: 'Lote',
          status: 'processing',
          default_options: {} as never,
          created_at: '2026-01-01T00:00:00Z',
          counts: { total: 2, done: 1, review: 0, failed: 1 },
        }}
        onBack={() => undefined}
      />
    </QueryClientProvider>,
  )
  expect(await screen.findByText('Pieza uno')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /Fallidas/ }))
  expect(screen.getByText('Pieza dos')).toBeInTheDocument()
  await waitFor(() => expect(screen.queryByText('Pieza uno')).not.toBeInTheDocument())
})
