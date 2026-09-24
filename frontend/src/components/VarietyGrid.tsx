import { useState } from "react";

import type { SessionSummary } from "../protocol";
import { trainingsWith, type Variety } from "../utils/progressStats";
import TrainingLinks from "./TrainingLinks";

/** How many Scenarios the grid shows before the show-more button. Five: enough to
 *  say where the training has gone, few enough that the card stays about as
 *  tall as the month calendar beside it. */
const COLLAPSED_ROWS = 5;

/**
 * Which Scenario was played against which Persona (F-13, training variety). A real table, so it is its own
 * accessible form. Played combinations only — empty cells would read as homework. Most played first
 * (`progressStats.variety`), cut after `COLLAPSED_ROWS` with a show-more button.
 */
export default function VarietyGrid({
  variety,
  sessions,
}: {
  variety: Variety;
  /** The trainings the grid was counted from, so a cell can list the ones
   *  behind it. */
  sessions: SessionSummary[];
}) {
  const [expanded, setExpanded] = useState(false);
  // The pairing whose trainings are listed under the grid, or null. A pair and
  // not an index: the rows re-sort when a training is added, and an index would
  // then open a different cell than the one that was pressed.
  const [opened, setOpened] = useState<{ scenario: string; persona: string } | null>(null);
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
                  const isOpen =
                    opened?.scenario === scenario && opened.persona === persona;
                  return (
                    <td key={persona}>
                      {count > 0 ? (
                        // A played cell opens the trainings behind it. An empty
                        // one stays a plain cell: there is nothing to open, and
                        // a grid where every cell is a control puts most of the
                        // tab order on combinations nobody played.
                        <button
                          type="button"
                          className={`variety-cell is-played${isOpen ? " is-open" : ""}`}
                          // The fill only repeats the number it sits behind; it
                          // is never the sole carrier of the value.
                          style={{ opacity: 0.35 + (count / peak) * 0.65 }}
                          aria-expanded={isOpen}
                          aria-label={
                            `${scenario} mit ${persona}: ${count} ` +
                            `${count === 1 ? "Training" : "Trainings"}`
                          }
                          onClick={() =>
                            setOpened((current) =>
                              current?.scenario === scenario && current.persona === persona
                                ? null
                                : { scenario, persona },
                            )
                          }
                        >
                          {count}
                        </button>
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

      {opened && (
        <TrainingLinks
          title={`${opened.scenario} mit ${opened.persona}`}
          sessions={trainingsWith(sessions, opened.scenario, opened.persona)}
        />
      )}

      {/* Only where something is actually cut off, and it says how much: a
          button that reveals one row is not worth a guess about what it
          opens. */}
      {hidden > 0 && (
        <button
          type="button"
          className="session-more"
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
