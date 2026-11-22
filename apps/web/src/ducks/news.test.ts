import { expect, test } from 'vitest'
import { envelope } from '../test/matchEvents'
import { newsFor } from './usePond'

test('XP and level-ups become short news; other events do not', () => {
  const xp = envelope(
    'XpGained',
    { duckId: 'd', amount: 25, source: 'match', xpAfter: 125, level: 2, xpForNextLevel: 300 },
    'duck:d',
  )
  const levelUp = (stageAdvanced: boolean) =>
    envelope(
      'DuckLeveledUp',
      { duckId: 'd', level: 5, stage: 'duckling', statBudget: 264, stageAdvanced },
      'duck:d',
    )

  expect(newsFor(xp)).toBe('+25 XP')
  expect(newsFor(levelUp(false))).toBe('Level 5!')
  expect(newsFor(levelUp(true))).toBe('Level 5! Now a duckling.')
  expect(newsFor(envelope('MatchStarted', { matchId: 'm' }))).toBeNull()
})
