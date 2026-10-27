import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, vi } from 'vitest'
import type { SceneBackground, SceneSettings } from '@/shared/api/client'
import * as client from '@/shared/api/client'
import { withQuery } from '@/test/withQuery'
import { SceneSettingsSection } from './SceneSettingsSection'

const SCENE: SceneSettings = {
  style: 'studio',
  studio_wall_hex: '#FFFFFF',
  studio_floor_hex: '#ECEAE6',
  brand_hex: '#C9D9EA',
  pedestal_hex: '#E4DFD6',
  reflection: 14,
  default_background_id: null,
}

const MESA: SceneBackground = {
  id: 'bg-1',
  name: 'Mesa',
  url: '/api/v1/files/backgrounds/bg-1.jpg',
  width: 800,
  height: 600,
  floor_y: 0.8,
  center_x: 0.5,
  piece_height: 0.55,
  created_at: '2026-10-27T00:00:00Z',
}

let library: SceneBackground[] = []
const onChange = vi.fn()

function Harness({ initial }: { initial: SceneSettings }) {
  const [value, setValue] = useState(initial)
  return (
    <SceneSettingsSection
      value={value}
      onChange={(next) => {
        setValue(next)
        onChange(next)
      }}
    />
  )
}

beforeEach(() => {
  library = []
  onChange.mockReset()
  vi.spyOn(client, 'apiGet').mockImplementation(async () => library as never)
})

afterEach(() => vi.restoreAllMocks())

it('al subir el primer fondo lo deja como predeterminado también en el borrador', async () => {
  vi.spyOn(client, 'apiUpload').mockImplementation(async () => {
    library = [MESA]
    return MESA as never
  })
  render(withQuery(<Harness initial={SCENE} />))
  expect(await screen.findByText('Todavía no hay fondos.')).toBeInTheDocument()

  const file = new File(['x'], 'mesa.jpg', { type: 'image/jpeg' })
  fireEvent.change(screen.getByLabelText('Subir fondo'), { target: { files: [file] } })

  await waitFor(() =>
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ default_background_id: 'bg-1' })),
  )
  expect(await screen.findByRole('img', { name: 'Mesa' })).toBeInTheDocument()
})

it('muestra un error si la subida falla', async () => {
  vi.spyOn(client, 'apiUpload').mockRejectedValue(new client.ApiError(415, 'no'))
  render(withQuery(<Harness initial={SCENE} />))
  const file = new File(['x'], 'mesa.txt', { type: 'text/plain' })
  fireEvent.change(screen.getByLabelText('Subir fondo'), { target: { files: [file] } })
  expect(await screen.findByRole('alert')).toHaveTextContent('No pudimos subir el fondo')
})

it('marca el punto de apoyo con un clic, dentro de los límites de la API', async () => {
  library = [MESA]
  const patch = vi.spyOn(client, 'apiPatch').mockResolvedValue(MESA as never)
  render(withQuery(<Harness initial={{ ...SCENE, default_background_id: 'bg-1' }} />))
  const image = await screen.findByRole('img', { name: 'Mesa' })
  vi.spyOn(image, 'getBoundingClientRect').mockReturnValue({
    left: 0,
    top: 0,
    width: 400,
    height: 300,
  } as DOMRect)

  fireEvent.click(image, { clientX: 100, clientY: 297 })

  await waitFor(() =>
    expect(patch).toHaveBeenCalledWith('/backgrounds/bg-1', { center_x: 0.25, floor_y: 0.98 }),
  )
})

it('al borrar el fondo predeterminado lo quita del borrador', async () => {
  library = [MESA]
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const remove = vi.spyOn(client, 'apiDelete').mockImplementation(async () => {
    library = []
    return undefined as never
  })
  render(withQuery(<Harness initial={{ ...SCENE, default_background_id: 'bg-1' }} />))
  fireEvent.click(await screen.findByRole('button', { name: 'Borrar' }))

  await waitFor(() => expect(remove).toHaveBeenCalledWith('/backgrounds/bg-1'))
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ default_background_id: null }))
  expect(await screen.findByText('Todavía no hay fondos.')).toBeInTheDocument()
})
