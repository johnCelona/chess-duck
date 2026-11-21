import { formatEval, type Decision } from './playback'

type Props = {
  decision: Decision | null
  duckName: (id: string) => string
  /** What to say when there is no decision to show (start position, waiting, ...). */
  emptyText: string
}

function styleText(decision: Decision['candidates'][number]): string {
  if (decision.adjustments.length === 0) return '–'
  return decision.adjustments
    .map((a) => `${a.ruleId} ${a.deltaCp >= 0 ? '+' : ''}${(a.deltaCp / 100).toFixed(2)}`)
    .join(', ')
}

/**
 * "Why did the duck play that?" The box keeps one size; long content scrolls inside it,
 * so stepping through moves never makes the page jump.
 */
export function ThinkingPanel({ decision, duckName, emptyText }: Props) {
  return (
    <section className="panel thinking" aria-label="Why the duck played its move">
      <h3 title={decision ? undefined : emptyText}>
        {decision ? `Why ${duckName(decision.duckId)} played ${decision.san}` : 'Why this move?'}
      </h3>
      <div className="thinking-body">
        {!decision ? (
          <p className="hint">{emptyText}</p>
        ) : (
          <>
            <ul className="reasons">
              {decision.reasons.map((reason, index) => (
                <li key={`${reason.code}-${index}`}>{reason.text}</li>
              ))}
            </ul>
            {decision.candidates.length > 0 && (
              <table>
                <colgroup>
                  <col className="col-move" />
                  <col className="col-eval" />
                  <col className="col-style" />
                  <col className="col-chance" />
                </colgroup>
                <thead>
                  <tr>
                    <th scope="col">Move</th>
                    <th scope="col" title="The engine's evaluation, for the side to move">
                      Engine
                    </th>
                    <th scope="col" title="Bonuses from the duck's style and training">
                      Style
                    </th>
                    <th scope="col" title="How likely the duck was to pick this move">
                      Chance
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {decision.candidates.map((candidate) => (
                    <tr
                      key={candidate.move}
                      className={[
                        candidate.move === decision.move ? 'chosen' : '',
                        candidate.filtered ? 'filtered' : '',
                      ].join(' ')}
                    >
                      <th scope="row">{candidate.san}</th>
                      <td>{formatEval(candidate)}</td>
                      <td>{styleText(candidate)}</td>
                      <td>
                        {candidate.filtered
                          ? 'ruled out'
                          : `${(candidate.probabilityPpm / 10000).toFixed(1)}%`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </section>
  )
}
