// Super Bullet Arena: the Arena hub, setting up a series, and the series scoreboard.
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import type { EventEnvelope } from '../api/client'
import { envelope, started } from '../test/matchEvents'
import { aDuck, profile, stubApi, type Call } from '../test/api'

const speckles = aDuck({ id: 'duck_1', name: 'Speckles' })
const dotty = aDuck({ id: 'duck_2', name: 'Dotty' })
const rookie = aDuck({ id: 'chal_rookie', name: 'Puddle Rookie' })
const wall = aDuck({
  id: 'chal_wall',
  name: 'The Wall',
  growth: {
    stage: 'duck',
    level: 25,
    xp: 30000,
    xpForNextLevel: 32500,
    statBudget: 384,
    statCap: 90,
  },
})
const challengers = [
  { duck: rookie, blurb: 'Just hatched.', difficulty: 1 },
  { duck: wall, blurb: 'Very hard to break.', difficulty: 3 },
]
const engine = { id: 'stockfish', name: 'Stockfish', version: '19', status: 'installed' }

/** Stands in for EventSource so a test can push series events. */
class PushEventSource {
  static last: PushEventSource | null = null
  listeners = new Map<string, (message: MessageEvent<string>) => void>()
  onerror: (() => void) | null = null
  url: string
  constructor(url: string) {
    this.url = url
    PushEventSource.last = this
  }
  addEventListener(type: string, listener: (message: MessageEvent<string>) => void) {
    this.listeners.set(type, listener)
  }
  close() {}
  emit(event: EventEnvelope) {
    this.listeners.get(event.type)?.({ data: JSON.stringify(event) } as MessageEvent<string>)
  }
}

const match = {
  id: 'mat_1',
  duckIds: ['duck_1', 'chal_wall'],
  arena: { games: 5 },
  mode: 'duck-vs-duck',
  rated: true,
  state: 'running',
  contextId: 'ctx_1',
  jobId: 'job_1',
  scores: [],
  createdAt: '2026-11-21T12:00:00Z',
  finishedAt: null,
  series: { type: 'best-of', bestOf: 5 },
  stream: 'match:mat_1',
}

function arena() {
  return stubApi({
    'GET /api/v1/profile': () => Response.json(profile('duck_1')),
    'GET /api/v1/ducks': () => Response.json([speckles, dotty]),
    'GET /api/v1/challengers': () => Response.json(challengers),
    'GET /api/v1/engines': () => Response.json([engine]),
    'POST /api/v1/matches': () => Response.json(match, { status: 201 }),
    'GET /api/v1/matches/mat_1': () => Response.json(match),
  })
}

beforeEach(() => {
  vi.stubGlobal('EventSource', PushEventSource)
})

afterEach(() => {
  window.location.hash = ''
  PushEventSource.last = null
})

test('the Arena offers Super Bullet Arena and a custom match', async () => {
  arena()
  window.location.hash = '#/arena'
  render(<App />)

  const modes = screen.getByRole('navigation', { name: 'Arena modes' })
  expect(within(modes).getByRole('link', { name: /Super Bullet Arena/ })).toHaveAttribute(
    'href',
    '#/arena/super-bullet',
  )
  expect(within(modes).getByRole('link', { name: /Custom match/ })).toHaveAttribute(
    'href',
    '#/arena/custom',
  )
})

test('your duck challenges a house duck to a rated 30-second best of 7', async () => {
  const calls = arena()
  window.location.hash = '#/arena/super-bullet'
  const user = userEvent.setup()
  render(<App />)

  await user.click(await screen.findByRole('radio', { name: /The Wall/ }))
  await user.click(screen.getByRole('radio', { name: 'Best of 7' }))
  expect(screen.getByRole('radio', { name: /You play/ })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: 'Start the series' }))

  await waitFor(() => expect(window.location.hash).toBe('#/arena/super-bullet/mat_1'))
  const post = calls.find((call: Call) => call.method === 'POST')
  const body = post?.body as {
    duckIds: string[]
    rated: boolean
    series: unknown
    arena: { limit: unknown; games: number }
  }
  expect(body.duckIds).toEqual(['duck_1', 'chal_wall'])
  expect(body.rated).toBe(true)
  expect(body.series).toEqual({ type: 'best-of', bestOf: 7 })
  expect(body.arena.limit).toEqual({
    type: 'virtual-clock',
    timeControl: { baseSeconds: 30, incrementSeconds: 0 },
    virtualNps: 200000,
  })
})

test('the series viewer shows the score and announces Armageddon', async () => {
  arena()
  window.location.hash = '#/arena/super-bullet/mat_1'
  const user = userEvent.setup()
  render(<App />)

  expect(await screen.findByRole('heading', { name: 'Super Bullet Arena' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Start match' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Instant' }))
  const series = (data: object) =>
    envelope('SeriesUpdated', {
      matchId: 'mat_1',
      bestOf: 5,
      gamesPlayed: 5,
      winnerDuckId: null,
      decidedBy: null,
      armageddonWhiteDuckId: null,
      state: 'playing',
      scores: [
        { duckId: 'duck_1', points: 2.5 },
        { duckId: 'chal_wall', points: 2.5 },
      ],
      ...data,
    } as never)
  act(() => {
    PushEventSource.last!.emit(envelope('MatchStarted', { matchId: 'mat_1' }))
    PushEventSource.last!.emit(started('game_1', 0))
    PushEventSource.last!.emit(series({ state: 'armageddon', armageddonWhiteDuckId: 'chal_wall' }))
  })

  const score = await screen.findByLabelText('Series score')
  expect(score).toHaveTextContent('Speckles2.5 – 2.5The Wall')
  expect(within(score).getByRole('status')).toHaveTextContent(
    'Armageddon! The Wall has White. A draw wins the series for Black.',
  )

  act(() => {
    PushEventSource.last!.emit(
      series({ state: 'decided', gamesPlayed: 6, winnerDuckId: 'duck_1', decidedBy: 'armageddon' }),
    )
  })
  expect(score).toHaveTextContent('Speckles wins the series in Armageddon')
})
