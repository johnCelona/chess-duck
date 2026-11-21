import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'
import { aDuck, SilentEventSource, stubApi } from './test/api'

const duck = aDuck({ id: 'duck_1', name: 'Sir Quackalot' })

afterEach(() => {
  window.location.hash = ''
})

test('the Lab hatches a duck by posting its name as JSON and shows a provisional rating', async () => {
  let ducks: unknown[] = []
  const calls = stubApi({
    'GET /api/v1/ducks': () => Response.json(ducks),
    'POST /api/v1/ducks': () => {
      ducks = [duck]
      return Response.json(duck, { status: 201 })
    },
  })
  window.location.hash = '#/lab/ducks'
  const user = userEvent.setup()
  render(<App />)

  expect(await screen.findByText(/No ducks yet/)).toBeInTheDocument()
  await user.type(screen.getByLabelText('Name your duck'), 'Sir Quackalot')
  await user.click(screen.getByRole('button', { name: 'Hatch' }))

  expect(await screen.findByRole('heading', { name: 'Sir Quackalot' })).toBeInTheDocument()
  expect(screen.getByText('Rating 1500?')).toBeInTheDocument()
  const post = calls.find((call) => call.method === 'POST')
  expect(post?.body).toEqual({ name: 'Sir Quackalot' })
  expect(post?.contentType).toBe('application/json')
})

test('a problem from the API is shown to the player in plain words', async () => {
  stubApi({
    'GET /api/v1/ducks': () => Response.json([]),
    'POST /api/v1/ducks': () =>
      Response.json(
        {
          type: 'about:blank',
          title: 'Invalid request',
          status: 422,
          code: 'duck.invalid_name',
          detail: 'A duck needs a name of 1 to 40 characters',
          errors: [],
        },
        { status: 422, headers: { 'content-type': 'application/problem+json' } },
      ),
  })
  window.location.hash = '#/lab/ducks'
  const user = userEvent.setup()
  render(<App />)

  await user.type(await screen.findByLabelText('Name your duck'), 'x')
  await user.click(screen.getByRole('button', { name: 'Hatch' }))

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'A duck needs a name of 1 to 40 characters',
  )
})

test('the engines page lists engines with their license and installs with a JSON request', async () => {
  const engine = {
    id: 'stockfish',
    name: 'Stockfish',
    version: '19',
    license: 'GPL-3.0',
    homepage: 'https://stockfishchess.org/',
    sourceUrl: 'https://github.com/official-stockfish/Stockfish/tree/sf_19',
    status: 'not_installed',
    fingerprint: null,
  }
  const calls = stubApi({
    'GET /api/v1/engines': () => Response.json([engine]),
    'PUT /api/v1/engines/stockfish/installation': () =>
      Response.json({ ...engine, status: 'installed' }),
  })
  window.location.hash = '#/engines' // an address from before the Lab still works
  const user = userEvent.setup()
  render(<App />)

  const source = await screen.findByRole('link', { name: /licensed under GPL-3.0/ })
  expect(source).toHaveAttribute('href', engine.sourceUrl)
  expect(window.location.hash).toBe('#/lab/engines')
  await user.click(screen.getByRole('button', { name: 'Install' }))

  await waitFor(() => {
    const put = calls.find((call) => call.method === 'PUT')
    expect(put?.contentType).toBe('application/json')
  })
})

test('the match page explains what is missing before a match can start', async () => {
  stubApi({ 'GET /api/v1/ducks': () => Response.json([duck]) })
  window.location.hash = '#/lab/match'
  render(<App />)

  expect(await screen.findByText(/A match needs two ducks and an installed engine/)).toBeVisible()
  expect(screen.getByRole('button', { name: 'Start match' })).toBeDisabled()
})

test('an old match link opens that match in the Lab', async () => {
  vi.stubGlobal('EventSource', SilentEventSource)
  const calls = stubApi({
    'GET /api/v1/ducks': () => Response.json([duck]),
    'GET /api/v1/matches/mat_9': () =>
      Response.json({ id: 'mat_9', stream: 'match:mat_9', jobId: 'job_9', arena: { games: 1 } }),
  })
  window.location.hash = '#/match/mat_9'
  render(<App />)

  await waitFor(() => expect(window.location.hash).toBe('#/lab/match/mat_9'))
  await waitFor(() =>
    expect(calls.some((call) => call.path === '/api/v1/matches/mat_9')).toBe(true),
  )
})

test('an unknown address shows a friendly page with a way back', async () => {
  stubApi({})
  window.location.hash = '#/nowhere'
  render(<App />)

  expect(screen.getByRole('heading', { name: 'This pond is empty' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Back to the title' })).toHaveAttribute('href', '#/')
})
