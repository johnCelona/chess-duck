// A stubbed backend for page tests: routes keyed by "METHOD /path", every call recorded.
import { vi } from 'vitest'
import type { Duck } from '../api/client'

export type Call = { method: string; path: string; body: unknown; contentType: string | null }

export function stubApi(routes: Record<string, (call: Call) => Response>): Call[] {
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

export function aDuck(overrides: Partial<Duck> & { id: string; name: string }): Duck {
  return {
    avatar: { species: 'mallard', skin: 'classic', accessories: [] },
    growth: {
      stage: 'hatchling',
      level: 1,
      xp: 0,
      xpForNextLevel: 100,
      statBudget: 240,
      statCap: 60,
    },
    stats: { calculation: 40, memory: 40, aggression: 40, solidity: 40, creativity: 40, speed: 40 },
    care: { hunger: 0, energy: 1, mood: 1, lastFedAt: null },
    knowledge: { repertoireSize: 0, puzzleMemorySize: 0, principles: [], motifs: {} },
    rating: { value: 1500, deviation: 350, games: 0, provisional: true, contextId: null },
    createdAt: '2026-11-21T12:00:00Z',
    origin: null,
    eggSeed: null,
    stream: `duck:${overrides.id}`,
    ...overrides,
  }
}

export const profile = (activeDuckId: string | null) => ({
  id: 'prof_local',
  name: 'Local player',
  activeDuckId,
})

/** jsdom has no EventSource; pages that subscribe get one that never sends anything. */
export class SilentEventSource {
  url: string
  onerror: (() => void) | null = null
  constructor(url: string) {
    this.url = url
  }
  addEventListener() {}
  close() {}
}
