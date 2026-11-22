import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { api, messageOf, unwrap, type Schemas } from '../api/client'
import { subscribe } from '../api/events'
import { useResource } from '../api/useResource'
import { SparringGameView } from '../play/SparringGameView'
import { GameHeader } from './GameHeader'

type Series = Schemas['SparringSeriesOut']

async function loadDucks() {
  const [ducks, challengers] = await Promise.all([
    unwrap(api.GET('/api/v1/ducks')),
    unwrap(api.GET('/api/v1/challengers')),
  ])
  return [...ducks, ...challengers.map((challenger) => challenger.duck)]
}

const points = (value: number) => (value % 1 === 0 ? String(value) : value.toFixed(1))

/** "You play" in Super Bullet Arena: you against a duck, 30 seconds each, best of N. */
export function YouPlaySeriesPage() {
  const { seriesId = '' } = useParams()
  const ducks = useResource(loadDucks).data ?? []
  const [series, setSeries] = useState<Series | null>(null)
  const [error, setError] = useState('')
  const [finishedGame, setFinishedGame] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setSeries(
        await unwrap(
          api.GET('/api/v1/sparring-series/{series_id}', {
            params: { path: { series_id: seriesId } },
          }),
        ),
      )
    } catch (requestError) {
      setError(messageOf(requestError))
    }
  }, [seriesId])

  useEffect(() => {
    void load()
    return subscribe([`sparring-series:${seriesId}`], () => void load())
  }, [seriesId, load])

  const nextGame = async () => {
    setError('')
    try {
      setSeries(
        await unwrap(
          api.POST('/api/v1/sparring-series/{series_id}/games', {
            params: { path: { series_id: seriesId } },
          }),
        ),
      )
    } catch (requestError) {
      setError(messageOf(requestError))
    }
  }

  const duck = ducks.find((candidate) => candidate.id === series?.duckId) ?? null
  const duckName = duck?.name ?? 'Your opponent'
  const current = series?.currentGameId ?? null

  return (
    <section className="you-play" aria-labelledby="you-play-title">
      <GameHeader back={{ to: '/arena/super-bullet', label: 'Super Bullet Arena' }} />
      <h1 id="you-play-title">Super Bullet Arena · You play</h1>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      {series && (
        <div className="panel series" aria-label="Series score">
          <p className="series-score">
            <span>You</span>
            <strong>
              {points(series.humanPoints)} – {points(series.duckPoints)}
            </strong>
            <span>{duckName}</span>
          </p>
          <p className="hint">
            Best of {series.bestOf} · game {series.gameIds.length}
            {series.state === 'decided' &&
              ` · ${series.winner === 'human' ? 'You win' : `${duckName} wins`} the series${
                series.decidedBy === 'armageddon' ? ' in Armageddon' : ''
              }`}
          </p>
          {series.state === 'armageddon' && (
            <p className="armageddon" role="status">
              Armageddon! You play {series.armageddonHumanColor}. A draw wins the series for Black.
            </p>
          )}
          {series.state !== 'decided' && finishedGame === current && (
            <div className="actions">
              <button type="button" className="primary" onClick={() => void nextGame()}>
                Next game
              </button>
            </div>
          )}
        </div>
      )}
      {current && (
        <SparringGameView
          key={current}
          gameId={current}
          ducks={ducks}
          onFinished={(game) => {
            setFinishedGame(game.id)
            void load()
          }}
        />
      )}
    </section>
  )
}
