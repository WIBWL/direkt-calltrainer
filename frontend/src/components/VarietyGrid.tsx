import { useState } from "react";

import type { Variety } from "../utils/progressStats";

/** How many Scenarios the grid shows before the show-more button. Five: enough to
 *  say where the training has gone, few enough that the card stays about as
 *  tall as the month calendar beside it. */
const COLLAPSED_ROWS = 5;

/**
 * Which Scenario the user played against which Persona (F-13, the
 * training-variety focus goal).
 *
 * A real table, not a drawing: the rows and columns carry names, screen readers
 * get the header association for free, and the same markup is the accessible
 * form of the information. The shading of a cell only repeats its number.
 *
 * Played combinations only: a full library grid with empty cells reads as a
 * list of homework, and what somebody has not trained yet is not a deficit.
 * What this says instead is where their training has concentrated, which is
 * what the variety goal asks.
 *
 * Rows and columns come most played first (`progressStats.variety`), cut after
 * `COLLAPSED_ROWS` with a show-more button under the table — the same idiom the
 * training history and the Scenario grid use. With a dozen Scenarios played the
 * card had become the longest thing on the page, beside a calendar a third of
 * its height.
 */
export default function VarietyGrid({ variety }: { variety: Variety }) {
  const [expanded, setExpanded] = useState(false);
  if (variety.cells.length === 0) return null;

  const peak = Math.max(...variety.cells.map((c) => c.count));
  const countAt = (scenario: string, persona: string) =>
    variety.cells.find((c) => c.scenario === scenario && c.persona === persona)?.count ?? 0;
  const hidden = variety.scenarios.length - COLLAPSED_ROWS;
  const rows = expanded ? variety.scenarios : variety.scenarios.slice(0, COLLAPSED_ROWS);

  return (
    <>
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
            {rows.map((scenario) => (
              <tr key={scenario}>
                <th scope="row">{scenario}</th>
                {variety.personas.map((persona) => {
                  const count = countAt(scenario, persona);
                  return (
                    <td key={persona}>
                      {count > 0 ? (
                        <span
                          className="variety-cell is-played"
                          // The fill only repeats the number it sits behind; it
                          // is never the sole carrier of the value.
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

      {/* Only where something is actually cut off, and it says how much: a
          button that reveals one row is not worth a guess about what it
          opens. */}
      {hidden > 0 && (
        <button
          type="button"
          className="session-more variety-more"
          aria-expanded={expanded}
          onClick={() => setExpanded((open) => !open)}
        >
          {expanded
            ? "Weniger anzeigen"
            : `${hidden} weitere${hidden === 1 ? "s Szenario" : " Szenarien"} anzeigen`}
        </button>
      )}
    </>
  );
}
