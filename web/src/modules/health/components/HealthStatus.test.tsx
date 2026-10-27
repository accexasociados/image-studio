import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { HealthStatus } from './HealthStatus'

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <HealthStatus />
    </QueryClientProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

it('muestra la GPU cuando la API responde', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: 'ok',
          version: '0.1.0',
          pipeline_mode: 'stub',
          device: 'cuda',
          gpu: { available: true, name: 'NVIDIA GeForce GTX 1660', vram_mb: 6143 },
        }),
      ),
    ),
  )
  renderWithClient()
  expect(await screen.findByText('NVIDIA GeForce GTX 1660 · 6143 MB')).toBeInTheDocument()
  expect(screen.getByText('Simulado (sin IA)')).toBeInTheDocument()
})

it('avisa cuando no hay conexión con la API', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('down', { status: 502 })))
  renderWithClient()
  expect(await screen.findByText('Sin conexión con la API')).toBeInTheDocument()
})
