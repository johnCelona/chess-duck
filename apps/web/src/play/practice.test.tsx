// Practice Pond and "You play": the server holds the game; the client sends moves.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { destinationsFrom } from '../components/boardMoves'
import { aDuck, profile, SilentEventSource, stubApi, type Call } from '../test/api'

const sparky = aDuck({ id: 'duck_1', name: 'Sparky' })
const rookie = aDuck({ id: 'chal_rookie', name: 'Puddle Rookie' })
const engine = { id: 'fake', name: 'Fake', version: '1', status: 'installed' }
const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
const AFTER_E4 = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1'

function aGame(overrides: object = {}) {
  return {
    id: 'spar_1',
    duckId: 'duck_1',
    engineId: 'fake',
    humanColor: 'white',
    timeControl: null,
    state: 'running',
    result: null,
    termination: null,
    winner: null,
    initialFen: START,
    fen: START,
    turn: 'white',
    check: false,
    moves: [],
    legalMoves: ['e2e3', 'e2e4', 'g1f3'],
    duckThinking: false,
    whiteClockMs: null,
    blackClockMs: null,
    seriesId: null,
    seriesIndex: null,
    createdAt: '2026-11-21T12:00:00Z',
    stream: 'sparring:spar_1',
    ...overrides,
  }
}

function pond(routes: Record<string, (call: Call) => Response> = {}) {
  return stubApi({
    'GET /api/v1/profile': () => Response.json(profile('duck_1')),
    'GET /api/v1/ducks': () => Response.json([sparky]),
    'GET /api/v1/challengers': () =>
      Response.json([{ duck: rookie, blurb: 'Just hatched.', difficulty: 1 }]),
    'GET /api/v1/engines': () => Response.json([engine]),
    'GET /api/v1/sparring': () => Response.json([]),
    ...routes,
  })
}

beforeEach(() => {
  vi.stubGlobal('EventSource', SilentEventSource)
})

afterEach(() => {
  window.location.hash = ''
})

test('legal moves become board destinations without any chess rules', () => {
  const dests = destinationsFrom(['e2e4', 'e2e3', 'g1f3', 'e7e8q', 'e7e8n'])

  expect(dests.get('e2')).toEqual(['e4', 'e3'])
  expect(dests.get('g1')).toEqual(['f3'])
  expect(dests.get('e7')).toEqual(['e8'])
})

test('practice starts untimed by default against your active duck', async () => {
  const calls = pond({
    'POST /api/v1/sparring': () => Response.json(aGame(), { status: 201 }),
    'GET /api/v1/sparring/spar_1': () => Response.json(aGame()),
  })
  window.location.hash = '#/pond/practice'
  const user = userEvent.setup()
  render(<App />)

  await user.click(await screen.findByRole('button', { name: 'Play' }))

  await waitFor(() => expect(window.location.hash).toBe('#/pond/practice/spar_1'))
  const post = calls.find((call) => call.method === 'POST')
  expect(post?.body).toEqual({
    duckId: 'duck_1',
    engineId: 'fake',
    humanColor: 'white',
    timeControl: null,
  })
})

test('you play a move; untimed games show no clocks; the duck thinks', async () => {
  let current = aGame()
  const calls = pond({
    'GET /api/v1/sparring/spar_1': () => Response.json(current),
    'POST /api/v1/sparring/spar_1/moves': () => {
      current = aGame({
        fen: AFTER_E4,
        turn: 'black',
        legalMoves: [],
        duckThinking: true,
        moves: [
          { ply: 1, color: 'white', by: 'human', uci: 'e2e4', san: 'e4', fenAfter: AFTER_E4 },
        ],
      })
      return Response.json(current)
    },
  })
  window.location.hash = '#/pond/practice/spar_1'
  const user = userEvent.setup()
  render(<App />)

  expect(await screen.findByRole('heading', { name: 'Your move' })).toBeInTheDocument()
  expect(document.querySelector('.clock')).toBeNull()
  const input = screen.getByLabelText('Type a move')
  await user.type(input, 'e2e5')
  expect(screen.getByRole('button', { name: 'Play' })).toBeDisabled() // not a legal move
  await user.clear(input)
  await user.type(input, 'e2e4')
  await user.click(screen.getByRole('button', { name: 'Play' }))

  expect(await screen.findByRole('heading', { name: 'Sparky is thinking…' })).toBeInTheDocument()
  expect(calls.find((call) => call.method === 'POST')?.body).toEqual({ uci: 'e2e4' })
  expect(screen.getByTestId('board')).toHaveAttribute('data-fen', AFTER_E4)
})

test('a timed game shows both clocks and a finished game shows the result', async () => {
  pond({
    'GET /api/v1/sparring/spar_1': () =>
      Response.json(
        aGame({
          timeControl: { baseSeconds: 30, incrementSeconds: 0 },
          whiteClockMs: 12000,
          blackClockMs: 30000,
          state: 'finished',
          result: '0-1',
          termination: 'resignation',
          winner: 'duck',
          legalMoves: [],
        }),
      ),
  })
  window.location.hash = '#/pond/practice/spar_1'
  render(<App />)

  expect(await screen.findByRole('heading', { name: 'Sparky wins (resignation)' })).toBeVisible()
  const clocks = [...document.querySelectorAll('.clock')].map((clock) => clock.textContent)
  expect(clocks).toEqual(['0:30', '0:12'])
  expect(screen.queryByRole('button', { name: 'Resign' })).not.toBeInTheDocument()
})

test('you can play a Super Bullet series yourself against a challenger', async () => {
  const series = {
    id: 'sser_1',
    duckId: 'chal_rookie',
    bestOf: 3,
    state: 'playing',
    humanPoints: 0,
    duckPoints: 1,
    winner: null,
    decidedBy: null,
    armageddonHumanColor: null,
    gameIds: ['spar_1'],
    currentGameId: 'spar_1',
    stream: 'sparring-series:sser_1',
  }
  const calls = pond({
    'POST /api/v1/sparring-series': () => Response.json(series, { status: 201 }),
    'GET /api/v1/sparring-series/sser_1': () => Response.json(series),
    'GET /api/v1/sparring/spar_1': () =>
      Response.json(
        aGame({ duckId: 'chal_rookie', timeControl: { baseSeconds: 30, incrementSeconds: 0 } }),
      ),
  })
  window.location.hash = '#/arena/super-bullet'
  const user = userEvent.setup()
  render(<App />)

  await user.click(await screen.findByRole('radio', { name: /You play/ }))
  await user.click(screen.getByRole('radio', { name: 'Best of 3' }))
  await user.click(screen.getByRole('button', { name: 'Start the series' }))

  await waitFor(() => expect(window.location.hash).toBe('#/arena/super-bullet/you/sser_1'))
  expect(calls.find((call) => call.method === 'POST')?.body).toEqual({
    duckId: 'chal_rookie',
    engineId: 'fake',
    bestOf: 3,
  })
  const score = await screen.findByLabelText('Series score')
  expect(score).toHaveTextContent('You0 – 1Puddle Rookie')
  expect(within(score).queryByRole('button', { name: 'Next game' })).not.toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: 'Your move' })).toBeInTheDocument()
})
