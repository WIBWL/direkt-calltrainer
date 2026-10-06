import { useState } from "react";

import type { SessionSummary } from "../protocol";
import { trainingsWith, type Variety } from "../utils/progressStats";
import TrainingLinks from "./TrainingLinks";

/** About as tall as the calendar beside it. */
const COLLAPSED_ROWS = 5;

/** Scenario against Persona (F-13), played combinations only; a real table. */
export default function VarietyGrid({
  variety,
  sessions,
}: {
  variety: Variety;
  sessions: SessionSummary[];
}) {
  const [expanded, setExpanded] = useState(false);
  // A pair, not an index: the rows re-sort.
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
                        // Only played cells are controls.
                        <button
                          type="button"
                          className={`variety-cell is-played${isOpen ? " is-open" : ""}`}
                          // Never the sole carrier of the value.
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

      {hidden > 0 && (
        <button
          type="button"
          className="session-more"
          aria-expanded={expanded}
          onClick={() => {
            // Its list would stand under a grid that no longer shows it.
            setOpened(null);
            setExpanded((open) => !open);
          }}
        >
          {expanded
            ? "Weniger anzeigen"
            : `${hidden} weitere${hidden === 1 ? "s Szenario" : " Szenarien"} anzeigen`}
        </button>
      )}
    </>
  );
}
