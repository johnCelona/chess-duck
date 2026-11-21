// The only place the web app talks to the backend. Types come from the generated
// schema (never edit src/api/generated); this file adds error handling on top.
import createClient from 'openapi-fetch'
import type { components, paths } from './generated/schema'

export type Schemas = components['schemas']
export type Duck = Schemas['DuckOut']
export type Engine = Schemas['EngineOut']
export type EngineProfile = Schemas['EngineProfileOut']
export type Analysis = Schemas['AnalysisOut']
export type Match = Schemas['MatchOut']
export type Game = Schemas['GameOut']
export type Job = Schemas['JobOut']
export type Arena = Schemas['ArenaModel']
export type Problem = Schemas['Problem']
export type EventEnvelope = Schemas['EventPage']['events'][number]
export type EventOf<T extends EventEnvelope['type']> = Extract<EventEnvelope, { type: T }>
export type Candidate = Schemas['CandidateModel']
export type Reason = Schemas['ReasonModel']

export const API_BASE = '/api/v1'

/** An error reported by the API as an RFC 9457 problem document. */
export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly problem: Problem

  constructor(problem: Problem) {
    const fields = (problem.errors ?? []).map((e) => `${e.location}: ${e.message}`).join('; ')
    super([problem.detail ?? problem.title, fields].filter(Boolean).join(' — '))
    this.name = 'ApiError'
    this.code = problem.code
    this.status = problem.status
    this.problem = problem
  }
}

// Every write must be JSON, even without a body: the backend refuses anything a
// cross-site form could send (ADR-0011).
export const api = createClient<paths>({
  // Same origin as the page: the dev server proxies /api to the backend.
  baseUrl: globalThis.location?.origin ?? '',
  headers: { 'Content-Type': 'application/json' },
  // Looked up on every call rather than captured once, so tests can replace it.
  fetch: (request) => globalThis.fetch(request),
})

type Result<T> = { data?: T; error?: unknown; response: Response }

/** Unwraps an openapi-fetch result, throwing ApiError for any problem response. */
export async function unwrap<T>(request: Promise<Result<T>>): Promise<T> {
  let result: Result<T>
  try {
    result = await request
  } catch {
    throw new ApiError({
      type: 'about:blank',
      title: 'The backend is not reachable',
      status: 0,
      code: 'client.network',
      detail: 'The backend is not reachable. Is it running?',
      errors: [],
    })
  }
  if (result.error !== undefined || !result.response.ok) {
    const body = result.error as Partial<Problem> | undefined
    throw new ApiError({
      type: 'about:blank',
      title: body?.title ?? result.response.statusText ?? 'Request failed',
      status: body?.status ?? result.response.status,
      code: body?.code ?? 'client.unexpected',
      detail: body?.detail ?? null,
      errors: body?.errors ?? [],
    })
  }
  return result.data as T
}

export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

export function pgnUrl(gameId: string): string {
  return `${API_BASE}/games/${encodeURIComponent(gameId)}/pgn`
}

export function duckFileUrl(duckId: string): string {
  return `${API_BASE}/ducks/${encodeURIComponent(duckId)}/export`
}
