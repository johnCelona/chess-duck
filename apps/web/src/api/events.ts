// Live event streams (ADR-0002). The server pushes the persisted event log over SSE;
// the browser reconnects by itself and resumes from the last event id.
import { API_BASE, type EventEnvelope } from './client'

export const EVENT_TYPES = [
  'DuckHatched',
  'MatchCreated',
  'MatchStarted',
  'GameStarted',
  'MoveChosen',
  'MoveMade',
  'GameFinished',
  'MatchFinished',
  'SeriesUpdated',
  'RatingUpdated',
  'JobProgressed',
  'JobFinished',
] as const satisfies readonly EventEnvelope['type'][]

export type Unsubscribe = () => void

export function streamUrl(streams: string[], after = 0): string {
  const query = new URLSearchParams()
  for (const stream of streams) query.append('stream', stream)
  if (after > 0) query.set('after', String(after))
  return `${API_BASE}/events/stream?${query}`
}

/**
 * Subscribes to one or more streams from the beginning (replay) or from `after`.
 * Unknown event types are ignored, as the contract requires.
 */
export function subscribe(
  streams: string[],
  onEvent: (event: EventEnvelope) => void,
  options: { after?: number; onError?: () => void } = {},
): Unsubscribe {
  const source = new EventSource(streamUrl(streams, options.after))
  const handle = (message: MessageEvent<string>) => {
    try {
      onEvent(JSON.parse(message.data) as EventEnvelope)
    } catch {
      // A malformed message must not break the stream.
    }
  }
  for (const type of EVENT_TYPES) source.addEventListener(type, handle)
  if (options.onError) source.onerror = options.onError
  return () => source.close()
}
