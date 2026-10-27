import { useQuery } from '@tanstack/react-query'
import { apiGet, type Batch } from '@/shared/api/client'

export function useBatches() {
  return useQuery({
    queryKey: ['batches'],
    queryFn: () => apiGet<Batch[]>('/batches'),
  })
}
