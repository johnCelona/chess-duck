import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { EventEnvelope } from '../api/client'
import { aDuck } from '../test/api'
import { AFTER_D4, AFTER_E4, AFTER_E5, START, twoGameEvents } from '../test/matchEvents'
import { MatchPage } from './MatchPage'

/** Stands in for the browser's EventSource so a test can push events. */
class FakeEventSource {
  static last: FakeEventSource | null = null
  listeners = new Map<string, (message: MessageEvent<string>) => void>()
  onerror: (() => void) | null = null
  url: string
  constructor(url: string) {
    this.url = url
    FakeEventSource.last = this
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
  duckIds: ['duck_a', 'duck_b'],
  arena: { games: 2 },
  mode: 'duck-vs-duck',
  rated: true,
  state: 'running',
  contextId: 'ctx_1',
  jobId: 'job_1',
  scores: [],
  createdAt: '2026-11-21T12:00:00Z',
  finishedAt: null,
  stream: 'match:mat_1',
}

const ducks = [
  aDuck({ id: 'duck_a', name: 'Sir Quackalot' }),
  aDuck({ id: 'duck_b', name: 'Bill the Solid' }),
]

beforeEach(() => {
  vi.stubGlobal('EventSource', FakeEventSource)
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const path = new URL(request.url, 'http://localhost').pathname
      if (path === '/api/v1/matches/mat_1') return Response.json(match)
      if (path === '/api/v1/ducks') return Response.json(ducks)
      return Response.json([])
    }),
  )
})

afterEach(() => {
  FakeEventSource.last = null
})

const boardFen = () => screen.getByTestId('board').getAttribute('data-fen')

async function watchTwoGames() {
  const user = userEvent.setup()
  render(
    <MemoryRouter>
      <MatchPage matchId="mat_1" />
    </MemoryRouter>,
  )
  await screen.findByRole('group', { name: 'Move through the game' })
  // Show events as they arrive instead of pacing them by think time.
  await user.click(screen.getByRole('button', { name: 'Instant' }))
  act(() => {
    for (const event of twoGameEvents()) FakeEventSource.last!.emit(event)
  })
  return user
}

test('arrow keys step back and forward through the moves, across games', async () => {
  await watchTwoGames()

  expect(boardFen()).toBe(AFTER_D4)
  expect(screen.getByText('Game 2 · Move 1 of 1 · Live')).toBeInTheDocument()

  fireEvent.keyDown(window, { key: 'ArrowLeft' })
  expect(boardFen()).toBe(START)
  fireEvent.keyDown(window, { key: 'ArrowLeft' })
  expect(boardFen()).toBe(AFTER_E5)
  expect(screen.getByRole('heading', { name: 'Why Bill the Solid played e5' })).toBeInTheDocument()

  fireEvent.keyDown(window, { key: 'Home' })
  expect(boardFen()).toBe(START)
  expect(screen.getByText(/Start position/)).toBeInTheDocument()

  fireEvent.keyDown(window, { key: 'ArrowRight' })
  expect(boardFen()).toBe(AFTER_E4)

  fireEvent.keyDown(window, { key: 'End' })
  expect(boardFen()).toBe(AFTER_D4)
})

test('the buttons and the move list move the board too', async () => {
  const user = await watchTwoGames()

  await user.click(screen.getByRole('button', { name: 'Previous move' }))
  await user.click(screen.getByRole('button', { name: 'Previous move' }))
  expect(boardFen()).toBe(AFTER_E5)

  await user.click(screen.getByRole('button', { name: 'e4' }))
  expect(boardFen()).toBe(AFTER_E4)
  expect(screen.getByRole('button', { name: 'e4' })).toHaveAttribute('aria-current', 'true')

  await user.click(screen.getByRole('button', { name: 'Latest move' }))
  expect(boardFen()).toBe(AFTER_D4)
})

test('arrow keys do nothing while typing in a form field', async () => {
  await watchTwoGames()
  const seed = screen.getByLabelText('Seed')

  fireEvent.keyDown(seed, { key: 'ArrowLeft' })

  expect(boardFen()).toBe(AFTER_D4)
})
