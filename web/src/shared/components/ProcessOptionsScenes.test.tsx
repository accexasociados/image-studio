import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, vi } from 'vitest'
import { ProcessOptionsFields } from './ProcessOptionsFields'
import { FALLBACK_OPTIONS } from './processOptions'

afterEach(() => vi.unstubAllGlobals())

it('permite elegir una escena y un fondo de la biblioteca', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify([
            { id: 'bg-1', name: 'Mesa', url: '/mesa.jpg', floor_y: 0.8, center_x: 0.5, piece_height: 0.6 },
          ]),
        ),
      ),
  )
  const onChange = vi.fn()
  function Form() {
    const [value, setValue] = useState(FALLBACK_OPTIONS)
    return (
      <ProcessOptionsFields
        value={value}
        onChange={(next) => {
          setValue(next)
          onChange(next)
        }}
      />
    )
  }
  render(<Form />)
  fireEvent.change(screen.getByLabelText('Estilo de escena'), { target: { value: 'photo' } })
  await waitFor(() => expect(screen.getByRole('option', { name: 'Mesa' })).toBeInTheDocument())
  fireEvent.change(screen.getByLabelText('Fondo predeterminado'), { target: { value: 'bg-1' } })
  expect(onChange).toHaveBeenLastCalledWith(
    expect.objectContaining({ scene: 'photo', background_id: 'bg-1' }),
  )
})
