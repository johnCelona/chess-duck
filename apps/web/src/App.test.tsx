import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import App from './App'

test('shows the engines from the API', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      Response.json([
        {
          id: 'stockfish',
          name: 'Stockfish',
          version: '19',
          license: 'GPL-3.0',
          source_url: 'https://github.com/official-stockfish/Stockfish',
          status: 'not_installed',
        },
      ]),
    ),
  )

  render(<App />)

  expect(await screen.findAllByRole('heading', { name: 'Stockfish', level: 2 })).not.toHaveLength(0)
  expect(screen.getByRole('button', { name: 'Install' })).toBeEnabled()
})
