import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, type ImageItem } from '@/shared/api/client'

const EVENT_TYPES = ['image.updated', 'batch.progress', 'batch.finished'] as const

export const batchImagesKey = (batchId: string) => ['batch-images', batchId] as const

/** Imágenes del lote, refrescadas por SSE solo con eventos de este lote (agrupados cada 400 ms). */
export function useBatchImages(batchId: string) {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: batchImagesKey(batchId),
    queryFn: () => apiGet<ImageItem[]>(`/batches/${batchId}/images`),
  })

  useEffect(() => {
    const stream = new EventSource('/api/v1/events')
    let timer: number | undefined
    const refresh = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as { batch_id?: string }
        if (payload.batch_id && payload.batch_id !== batchId) return
      } catch {
        // Evento sin JSON: se refresca por si acaso.
      }
      window.clearTimeout(timer)
      timer = window.setTimeout(() => {
        void queryClient.invalidateQueries({ queryKey: batchImagesKey(batchId) })
        void queryClient.invalidateQueries({ queryKey: ['batches'] })
      }, 400)
    }
    EVENT_TYPES.forEach((type) => stream.addEventListener(type, refresh))
    return () => {
      window.clearTimeout(timer)
      stream.close()
    }
  }, [batchId, queryClient])

  return query
}
