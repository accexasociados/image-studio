import type { ImageItem } from '@/shared/api/client'
import { emptyHistory, interpolate, pushStroke, redo, undo, type Stroke } from './maskHistory'
import { outputVariants, pickOutput } from './outputs'

const stroke = (x: number): Stroke => ({ mode: 'add', radius: 5, hardness: 50, points: [{ x, y: 0 }] })

it('deshace y rehace trazos, y un trazo nuevo borra lo deshecho', () => {
  const first = pushStroke(emptyHistory, stroke(1))
  const second = pushStroke(first, stroke(2))
  const undone = undo(second)
  expect(undone.done).toHaveLength(1)
  expect(redo(undone).done).toEqual(second.done)
  expect(pushStroke(undone, stroke(3)).undone).toEqual([])
  expect(undo(emptyHistory)).toBe(emptyHistory)
  expect(pushStroke(emptyHistory, { ...stroke(1), points: [] })).toBe(emptyHistory)
})

it('interpola puntos para que un trazo rápido no deje huecos', () => {
  const points = interpolate({ x: 0, y: 0 }, { x: 10, y: 0 }, 2)
  expect(points).toHaveLength(5)
  expect(points.at(-1)).toEqual({ x: 10, y: 0 })
})

const image = (selected: ImageItem['selected_variant'] = null): ImageItem => ({
  id: 'i1',
  batch_id: 'b1',
  source: 'upload',
  original_path: 'o.jpg',
  status: 'done',
  selected_variant: selected,
  mask_edited: false,
  outputs: [
    { preset: 'instagram_feed', path: 'feed.jpg', width: 1, height: 1, bytes: 1, variant: 'keep' },
    { preset: 'storefront', path: 'keep.webp', width: 1, height: 1, bytes: 1, variant: 'keep' },
    { preset: 'storefront', path: 'smooth.webp', width: 1, height: 1, bytes: 1, variant: 'smooth' },
  ],
})

it('elige la salida de la tienda y la variante aprobada', () => {
  expect(pickOutput(image())?.path).toBe('keep.webp')
  expect(pickOutput(image('smooth'))?.path).toBe('smooth.webp')
  expect(pickOutput(image(), 'instagram_feed', 'smooth')?.path).toBe('feed.jpg')
  expect(outputVariants(image(), 'storefront')).toEqual(['keep', 'smooth'])
})
