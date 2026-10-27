import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, vi } from 'vitest'
import { withQuery } from '@/test/withQuery'
import { ProcessOptionsFields } from './ProcessOptionsFields'
import { FALLBACK_OPTIONS } from './processOptions'

afterEach(() => vi.unstubAllGlobals())

it('permite elegir el fondo y una foto de la biblioteca por lote o foto', async () => {
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
  render(withQuery(<Form />))

  const style = screen.getByLabelText('Fondo')
  expect(style).toHaveValue('')
  expect(screen.getByRole('option', { name: 'Usar el de Ajustes' })).toBeInTheDocument()
  expect(screen.queryByLabelText('Foto de fondo')).not.toBeInTheDocument()

  fireEvent.change(style, { target: { value: 'photo' } })
  expect(await screen.findByRole('option', { name: 'Mesa' })).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Foto de fondo'), { target: { value: 'bg-1' } })
  expect(onChange).toHaveBeenLastCalledWith(
    expect.objectContaining({ scene: 'photo', background_id: 'bg-1' }),
  )
})
