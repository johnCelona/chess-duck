// The player's journey (design 03): title → egg → Pond, the switcher, the tiles, the Arena.
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import type { Duck } from '../api/client'
import { hasPalette, SKINS } from '../ducks/skins'
import { aDuck, profile, SilentEventSource, stubApi, type Call } from '../test/api'
import { HATCH_MS } from './HatchPage'

const quackers = aDuck({
  id: 'duck_1',
  name: 'Quackers',
  eggSeed: 42,
  growth: {
    stage: 'hatchling',
    level: 2,
    xp: 130,
    xpForNextLevel: 300,
    statBudget: 246,
    statCap: 60,
  },
  stats: { calculation: 30, memory: 40, aggression: 45, solidity: 40, creativity: 45, speed: 40 },
})
const dotty = aDuck({
  id: 'duck_2',
  name: 'Dotty',
  avatar: { species: 'mallard', skin: 'terminal', accessories: [] },
})

/** A backend with these ducks whose active duck can be changed. */
function pond(ducks: Duck[], active: string | null = ducks[0]?.id ?? null) {
  let activeId = active
  const list = [...ducks]
  const calls = stubApi({
    'GET /api/v1/profile': () => Response.json(profile(activeId)),
    'GET /api/v1/ducks': () => Response.json(list),
    'PUT /api/v1/profile/active-duck': (call: Call) => {
      activeId = (call.body as { duckId: string }).duckId
      return Response.json(profile(activeId))
    },
    'POST /api/v1/ducks': (call: Call) => {
      const body = call.body as { name: string; eggSeed: number; avatar: { skin: string } }
      const hatched = aDuck({
        id: `duck_${list.length + 1}`,
        name: body.name,
        eggSeed: body.eggSeed,
        avatar: { species: 'mallard', skin: body.avatar.skin, accessories: [] },
      })
      list.push(hatched)
      return Response.json(hatched, { status: 201 })
    },
  })
  return calls
}

function reducedMotion(reduce: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: reduce, media: query }))
}

beforeEach(() => {
  vi.stubGlobal('EventSource', SilentEventSource)
  reducedMotion(true)
  sessionStorage.clear()
})

afterEach(() => {
  window.location.hash = ''
})

async function crackTheEgg(user: ReturnType<typeof userEvent.setup>) {
  for (let tap = 0; tap < 3; tap += 1) {
    await user.click(screen.getByRole('button', { name: /Tap the egg/ }))
  }
}

// ----- title -------------------------------------------------------------------------

test('Play on a first launch goes straight to the egg', async () => {
  pond([])
  const user = userEvent.setup()
  render(<App />)

  await user.click(await screen.findByRole('button', { name: 'Play' }))

  expect(await screen.findByRole('heading', { name: 'An egg!' })).toBeInTheDocument()
})

test('Play goes to the active duck, and the title always offers another egg', async () => {
  pond([quackers])
  const user = userEvent.setup()
  render(<App />)

  expect(screen.getByRole('link', { name: 'Hatch a new egg' })).toHaveAttribute('href', '#/hatch')
  await waitFor(() => expect(screen.getByRole('button', { name: 'Play' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: 'Play' }))

  expect(await screen.findByRole('button', { name: 'Quackers, switch duck' })).toBeInTheDocument()
})

// ----- hatching ----------------------------------------------------------------------

test('cracking the egg, naming the duck and picking a colour hatches it and opens the pond', async () => {
  const calls = pond([])
  window.location.hash = '#/hatch'
  const user = userEvent.setup()
  render(<App />)

  await crackTheEgg(user)
  expect(await screen.findByRole('heading', { name: 'Your duck hatched!' })).toBeInTheDocument()
  await user.type(screen.getByLabelText('Name your duck'), 'Speckles')
  await user.click(screen.getByRole('radio', { name: 'Terminal' }))
  await user.click(screen.getByRole('button', { name: 'Welcome to the pond' }))

  expect(await screen.findByRole('button', { name: 'Speckles, switch duck' })).toBeInTheDocument()
  const post = calls.find((call) => call.method === 'POST')
  const body = post?.body as { name: string; eggSeed: number; avatar: { skin: string } }
  expect(body.name).toBe('Speckles')
  expect(body.avatar).toEqual({ skin: 'terminal' })
  expect(Number.isSafeInteger(body.eggSeed) && body.eggSeed >= 0).toBe(true)
  const put = calls.find((call) => call.method === 'PUT')
  expect(put?.body).toEqual({ duckId: 'duck_1' })
  expect(window.location.hash).toBe('#/pond')
})

test('a reload in the middle of hatching keeps the same egg', async () => {
  const calls = pond([])
  window.location.hash = '#/hatch'
  const user = userEvent.setup()
  const first = render(<App />)
  await user.click(screen.getByRole('button', { name: /Tap the egg/ }))
  const kept = sessionStorage.getItem('duck-gambit.egg-seed')
  first.unmount()

  render(<App />)
  await crackTheEgg(user)
  await user.type(await screen.findByLabelText('Name your duck'), 'Same Egg')
  await user.click(screen.getByRole('button', { name: 'Welcome to the pond' }))

  await screen.findByRole('button', { name: 'Same Egg, switch duck' })
  const post = calls.find((call) => call.method === 'POST')
  expect(String((post!.body as { eggSeed: number }).eggSeed)).toBe(kept)
  expect(sessionStorage.getItem('duck-gambit.egg-seed')).toBeNull() // the next egg is new
})

test('with motion on, the duck appears after the shell splits', async () => {
  reducedMotion(false)
  pond([])
  window.location.hash = '#/hatch'
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
  render(<App />)

  await crackTheEgg(user)
  expect(screen.getByRole('heading', { name: 'It’s hatching!' })).toBeInTheDocument()
  act(() => {
    vi.advanceTimersByTime(HATCH_MS)
  })

  expect(screen.getByRole('heading', { name: 'Your duck hatched!' })).toBeInTheDocument()
  vi.useRealTimers()
})

test('every skin in the asset manifest has a placeholder look', () => {
  expect(SKINS.length).toBeGreaterThan(1)
  expect(SKINS.filter((skin) => !hasPalette(skin.id))).toEqual([])
})

// ----- the pond ----------------------------------------------------------------------

test('the top bar shows the active duck’s attributes from the API', async () => {
  pond([quackers, dotty])
  window.location.hash = '#/pond'
  render(<App />)

  const bar = await screen.findByRole('region', { name: "Quackers's attributes" })
  expect(within(bar).getByText('Level 2')).toBeInTheDocument()
  expect(within(bar).getByText('hatchling')).toBeInTheDocument()
  expect(within(bar).getByText('130 / 300 XP')).toBeInTheDocument()
  expect(within(bar).getByRole('progressbar', { name: 'Experience' })).toHaveAttribute(
    'value',
    '130',
  )
  expect(within(bar).getByText('1500?')).toBeInTheDocument()
  expect(within(bar).getByText('Provisional')).toBeInTheDocument()
  expect(within(bar).getByText('Calculation').nextSibling).toHaveTextContent('30')
  expect(within(bar).getByText('Stat points').nextSibling).toHaveTextContent('240 / 246')
})

test('choosing another duck saves it as active and the bar switches to it', async () => {
  const calls = pond([quackers, dotty])
  window.location.hash = '#/pond'
  const user = userEvent.setup()
  render(<App />)

  await user.click(await screen.findByRole('button', { name: 'Quackers, switch duck' }))
  const menu = screen.getByRole('menu', { name: 'Your ducks' })
  expect(within(menu).getByRole('menuitemradio', { name: /Quackers/ })).toHaveAttribute(
    'aria-checked',
    'true',
  )
  await user.click(within(menu).getByRole('menuitemradio', { name: /Dotty/ }))

  expect(await screen.findByRole('button', { name: 'Dotty, switch duck' })).toBeInTheDocument()
  expect(calls.find((call) => call.method === 'PUT')?.body).toEqual({ duckId: 'duck_2' })
})

test('the switcher can hatch another egg without replacing anyone', async () => {
  pond([quackers])
  window.location.hash = '#/pond'
  const user = userEvent.setup()
  render(<App />)

  await user.click(await screen.findByRole('button', { name: 'Quackers, switch duck' }))
  await user.click(screen.getByRole('menuitem', { name: '+ Hatch a new egg' }))

  expect(await screen.findByRole('heading', { name: 'An egg!' })).toBeInTheDocument()
})

test('the four tiles lead to the Arena and to placeholder screens', async () => {
  pond([quackers])
  window.location.hash = '#/pond'
  const user = userEvent.setup()
  render(<App />)

  const tiles = await screen.findByRole('navigation', { name: 'Activities' })
  const links = within(tiles).getAllByRole('link')
  expect(links.map((link) => link.getAttribute('href'))).toEqual([
    '#/pond/dojo',
    '#/arena',
    '#/pond/practice',
    '#/pond/school',
  ])
  await user.click(within(tiles).getByRole('link', { name: /Opening School/ }))

  expect(await screen.findByRole('heading', { name: 'Opening School' })).toBeInTheDocument()
  expect(screen.getByText('Coming soon.')).toBeInTheDocument()
})

test('the pond sends a player without ducks to the egg', async () => {
  pond([], null)
  window.location.hash = '#/pond'
  render(<App />)

  expect(await screen.findByRole('heading', { name: 'An egg!' })).toBeInTheDocument()
})

// ----- arena -------------------------------------------------------------------------

test('the Arena preselects the active duck and offers every duck on both sides', async () => {
  pond([quackers, dotty], 'duck_2')
  window.location.hash = '#/arena'
  render(<App />)

  expect(await screen.findByRole('heading', { name: 'Arena' })).toBeInTheDocument()
  const white = screen.getByLabelText('White in game 1') as HTMLSelectElement
  const black = screen.getByLabelText('Black in game 1') as HTMLSelectElement
  await waitFor(() => expect(white.value).toBe('duck_2'))
  expect(black.value).toBe('duck_1')
  expect(within(white).getAllByRole('option')).toHaveLength(2)
  expect(within(black).getAllByRole('option')).toHaveLength(2)
})
