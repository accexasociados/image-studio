import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  apiDelete,
  apiPatch,
  apiPost,
  apiUpload,
  type ImageItem,
  type LayerLines,
  type ProcessOptions,
} from '@/shared/api/client'
import { batchImagesKey } from './useBatchImages'

type BulkAction = 'approve' | 'reprocess'

/** Acciones de revisión; cada una deja la lista del lote al día con la respuesta de la API. */
export function useImageActions(batchId: string) {
  const queryClient = useQueryClient()
  const replace = (updated: ImageItem[]) => {
    queryClient.setQueryData<ImageItem[]>(batchImagesKey(batchId), (current) =>
      current?.map((image) => updated.find((item) => item.id === image.id) ?? image),
    )
    void queryClient.invalidateQueries({ queryKey: ['batches'] })
  }

  const approve = useMutation({
    mutationFn: ({ id, variant }: { id: string; variant?: LayerLines }) =>
      apiPost<ImageItem>(`/images/${id}/approve`, variant ? { variant } : null),
    onSuccess: (image) => replace([image]),
  })
  const reprocess = useMutation({
    mutationFn: ({ id, options }: { id: string; options?: ProcessOptions }) =>
      apiPost<ImageItem>(`/images/${id}/reprocess`, options ?? null),
    onSuccess: (image) => replace([image]),
  })
  const resetOptions = useMutation({
    mutationFn: async (id: string) => {
      await apiPatch<ImageItem>(`/images/${id}`, { options_override: null })
      return apiPost<ImageItem>(`/images/${id}/reprocess`, null)
    },
    onSuccess: (image) => replace([image]),
  })
  const bulk = useMutation({
    mutationFn: ({ action, ids }: { action: BulkAction; ids: string[] }) =>
      apiPost<ImageItem[]>(`/batches/${batchId}/images/${action}`, { image_ids: ids }),
    onSuccess: replace,
  })
  const saveMask = useMutation({
    mutationFn: ({ id, mask }: { id: string; mask: Blob }) =>
      apiUpload<ImageItem>(
        `/images/${id}/mask`,
        [new File([mask], 'mask.png', { type: 'image/png' })],
        () => undefined,
        'file',
        'PUT',
      ),
    onSuccess: (image) => replace([image]),
  })

  const discardMask = useMutation({
    mutationFn: (id: string) => apiDelete<ImageItem>(`/images/${id}/mask`),
    onSuccess: (image) => replace([image]),
  })

  return { approve, reprocess, resetOptions, bulk, saveMask, discardMask }
}
