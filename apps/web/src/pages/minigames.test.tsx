// Minigame tests: the list, playing a run, and the animation before a board.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import App from '../App'
import type { MinigameRun } from '../minigames/useMinigame'
import { stubApi } from '../test/api'

const info = {
  id: 'tuck-in',
  title: 'Tuck the Duckling In',
  blurb: 'Can the king castle?',
  teaches: 'Castling',
  howTo: 'Pick a side.',
  levels: [],
}

function aRun(overrides: Partial<MinigameRun> = {}): MinigameRun {
  return {
    id: 'mini_1',
    kind: 'tuck-in',
    seed: 7,
    level: '',
    version: 0,
    phase: 'play',
    round: 1,
    rounds: 8,
    score: 0,
    hearts: 3,
    remainingMs: null,
    timeLimitMs: null,
    banner: null,
    headline: '',
    feedback: null,
    frames: [],
    prompt: 'Where may the king castle?',
    board: {
      fen: '4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1',
      orientation: 'white',
      check: false,
      lastMove: null,
      coordinates: true,
    },
    moves: [],
    squares: [],
    marks: [],
    arrows: [],
    choices: [{ id: 'both', label: 'Either side', detail: '' }],
    notes: [],
    canHint: false,
    ...overrides,
  }
}

afterEach(() => {
  window.location.hash = ''
})

test('the list shows every minigame and opens one', async () => {
  stubApi({
    'GET /api/v1/minigames': () => Response.json([info]),
    'POST /api/v1/minigame-runs': () => Response.json(aRun(), { status: 201 }),
  })
  window.location.hash = '#/minigame-tests'
  render(<App />)
  await userEvent.click(await screen.findByRole('link', { name: /Tuck the Duckling In/ }))
  expect(await screen.findByText('Where may the king castle?')).toBeInTheDocument()
})

test('a choice is sent to the server and the result offers the next round', async () => {
  const calls = stubApi({
    'GET /api/v1/minigames': () => Response.json([info]),
    'POST /api/v1/minigame-runs': () => Response.json(aRun(), { status: 201 }),
    'POST /api/v1/minigame-runs/mini_1/actions': () =>
      Response.json(
        aRun({
          version: 1,
          phase: 'review',
          score: 2,
          choices: [],
          feedback: { tone: 'good', text: 'Right!' },
        }),
      ),
  })
  window.location.hash = '#/minigame-tests/tuck-in'
  render(<App />)
  await userEvent.click(await screen.findByRole('button', { name: 'Either side' }))
  expect(await screen.findByText('Right!')).toBeInTheDocument()
  expect(calls.at(-1)?.body).toEqual({ type: 'choice', value: 'both' })
  expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()
})

test('frames play before the board opens, and can be skipped', async () => {
  const frame = { fen: '8/8/8/8/8/8/8/K6k w - - 0 1', lastMove: null, caption: 'Watch this' }
  stubApi({
    'GET /api/v1/minigames': () => Response.json([info]),
    'POST /api/v1/minigame-runs': () =>
      Response.json(aRun({ frames: [frame, frame, frame] }), { status: 201 }),
  })
  window.location.hash = '#/minigame-tests/tuck-in'
  render(<App />)
  expect(await screen.findByText('Watch this')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Either side' })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Skip' }))
  expect(screen.getByRole('button', { name: 'Either side' })).toBeInTheDocument()
})

test('a timed run claims the timeout when its clock reaches zero', async () => {
  const done = vi.fn(() => Response.json(aRun({ version: 1, phase: 'done', remainingMs: 0 })))
  stubApi({
    'GET /api/v1/minigames': () => Response.json([info]),
    'POST /api/v1/minigame-runs': () => Response.json(aRun({ remainingMs: 100 }), { status: 201 }),
    'POST /api/v1/minigame-runs/mini_1/actions': done,
  })
  window.location.hash = '#/minigame-tests/tuck-in'
  render(<App />)
  expect(await screen.findByText(/Run over/)).toBeInTheDocument()
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1))
})

const levels = [
  { id: 'easy', label: 'Easy', detail: 'Gentle' },
  { id: 'hard', label: 'Hard', detail: 'Fierce' },
]

test('a game with difficulties asks first, and the menu can be opened again', async () => {
  const calls = stubApi({
    'GET /api/v1/minigames': () => Response.json([{ ...info, levels }]),
    'POST /api/v1/minigame-runs': () => Response.json(aRun({ level: 'hard' }), { status: 201 }),
  })
  const started = () => calls.filter((call) => call.method === 'POST')
  window.location.hash = '#/minigame-tests/tuck-in'
  render(<App />)
  expect(await screen.findByRole('dialog', { name: 'Choose a difficulty' })).toBeInTheDocument()
  expect(started()).toHaveLength(0)

  await userEvent.click(screen.getByRole('button', { name: /Hard/ }))
  await userEvent.click(await screen.findByRole('button', { name: 'Difficulty: Hard' }))
  expect(started().map((call) => call.body)).toEqual([{ kind: 'tuck-in', level: 'hard' }])

  await userEvent.click(screen.getByRole('button', { name: 'Keep playing' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(started()).toHaveLength(1)
})

test('the timer is above the board, and a switch screen waits for the player', async () => {
  const banner = {
    title: 'Switching to Black',
    text: 'You found 5.',
    button: 'Go',
    turnsBoard: true,
  }
  const calls = stubApi({
    'GET /api/v1/minigames': () => Response.json([info]),
    'POST /api/v1/minigame-runs': () =>
      Response.json(aRun({ phase: 'review', banner, remainingMs: 0, timeLimitMs: 45000 }), {
        status: 201,
      }),
    'POST /api/v1/minigame-runs/mini_1/actions': () =>
      Response.json(aRun({ version: 1, remainingMs: 45000, timeLimitMs: 45000, headline: 'h2' })),
  })
  window.location.hash = '#/minigame-tests/tuck-in'
  render(<App />)
  expect(await screen.findByRole('dialog', { name: 'Switching to Black' })).toBeInTheDocument()
  const go = screen.getByRole('button', { name: 'Go' })
  expect(go).toBeDisabled()
  await waitFor(() => expect(go).toBeEnabled(), { timeout: 3000 })
  await userEvent.click(go)
  expect(await screen.findByRole('timer')).toHaveTextContent('45')
  expect(calls.at(-1)?.body).toEqual({ type: 'next', value: '' })
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('h2')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
