import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

const duck = {
  id: 'duck_1',
  name: 'Sir Quackalot',
  avatar: { species: 'mallard', skin: 'default', accessories: [] },
  growth: { stage: 'hatchling', level: 1, xp: 0, statBudget: 240, statCap: 60 },
  stats: { calculation: 40, memory: 40, aggression: 40, solidity: 40, creativity: 40, speed: 40 },
  care: { hunger: 0, energy: 1, mood: 1, lastFedAt: null },
  knowledge: { repertoireSize: 0, puzzleMemorySize: 0, principles: [], motifs: {} },
  rating: { value: 1500, deviation: 350, games: 0, provisional: true, contextId: null },
  createdAt: '2026-11-21T12:00:00Z',
  origin: null,
  stream: 'duck:duck_1',
}

type Call = { method: string; path: string; body: unknown; contentType: string | null }

function stubApi(routes: Record<string, (call: Call) => Response>) {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: Request) => {
      const call: Call = {
        method: input.method,
        path: new URL(input.url, 'http://localhost').pathname,
        body:
          input.method === 'GET'
            ? null
            : await input
                .clone()
                .json()
                .catch(() => null),
        contentType: input.headers.get('content-type'),
      }
      calls.push(call)
      const handler = routes[`${call.method} ${call.path}`]
      return handler ? handler(call) : Response.json([], { status: 200 })
    }),
  )
  return calls
}

afterEach(() => {
  window.location.hash = ''
})

test('hatching a duck posts its name as JSON and shows it with a provisional rating', async () => {
  let ducks: unknown[] = []
  const calls = stubApi({
    'GET /api/v1/ducks': () => Response.json(ducks),
    'POST /api/v1/ducks': () => {
      ducks = [duck]
      return Response.json(duck, { status: 201 })
    },
  })
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
  window.location.hash = '#/engines'
  const user = userEvent.setup()
  render(<App />)

  const source = await screen.findByRole('link', { name: /licensed under GPL-3.0/ })
  expect(source).toHaveAttribute('href', engine.sourceUrl)
  await user.click(screen.getByRole('button', { name: 'Install' }))

  await waitFor(() => {
    const put = calls.find((call) => call.method === 'PUT')
    expect(put?.contentType).toBe('application/json')
  })
})

test('the match page explains what is missing before a match can start', async () => {
  stubApi({ 'GET /api/v1/ducks': () => Response.json([duck]) })
  window.location.hash = '#/match'
  render(<App />)

  expect(await screen.findByText(/A match needs two ducks and an installed engine/)).toBeVisible()
  expect(screen.getByRole('button', { name: 'Start match' })).toBeDisabled()
})
