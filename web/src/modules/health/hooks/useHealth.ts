import { useQuery } from '@tanstack/react-query'
import { apiGet, type Health } from '@/shared/api/client'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<Health>('/health'),
    refetchInterval: 15_000,
  })
}
