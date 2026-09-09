import type { Variety } from "../utils/progressStats";

/**
 * Which Scenario the user played against which Persona (F-13, focus goal
 * "Trainingsvielfalt").
 *
 * A real table, not a drawing: the rows and columns carry names, screen readers
 * get the header association for free, and the same markup is the accessible
 * form of the information. The shading of a cell only repeats its number.
 *
 * It shows played combinations only. The concept flagged the risk that a full
 * library grid with empty cells reads as a list of homework, and it does: what
 * somebody has not trained yet is not a deficit, and nobody set them that task.
 * What this says instead is where their training has been concentrated, which
 * is the question the variety goal actually asks.
 */
export default function VarietyGrid({ variety }: { variety: Variety }) {
  if (variety.cells.length === 0) return null;

  const peak = Math.max(...variety.cells.map((c) => c.count));
  const countAt = (scenario: string, persona: string) =>
    variety.cells.find((c) => c.scenario === scenario && c.persona === persona)?.count ?? 0;

  return (
    <div className="variety-wrap">
      <table className="variety-grid">
        <thead>
          <tr>
            {/* Empty by design: the row headers below are the Scenarios, and a
                caption over them would repeat the section heading. */}
            <th scope="col" />
            {variety.personas.map((persona) => (
              <th scope="col" key={persona}>
                {persona}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {variety.scenarios.map((scenario) => (
            <tr key={scenario}>
              <th scope="row">{scenario}</th>
              {variety.personas.map((persona) => {
                const count = countAt(scenario, persona);
                return (
                  <td key={persona}>
                    {count > 0 ? (
                      <span
                        className="variety-cell is-played"
                        // The fill only repeats the number it sits behind; it is
                        // never the sole carrier of the value.
                        style={{ opacity: 0.35 + (count / peak) * 0.65 }}
                      >
                        {count}
                      </span>
                    ) : (
                      <span className="variety-cell">
                        <span className="variety-empty" aria-hidden="true" />
                        <span className="variety-empty-text">nicht gespielt</span>
                      </span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
