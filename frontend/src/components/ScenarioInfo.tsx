import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../api";
import {
  CATEGORY_LABELS,
  getScenario,
  type ScenarioCategory,
  type ScenarioDetail,
} from "../scenarioLibrary";

interface ScenarioInfoProps {
  /** The Scenario to describe — its `extern_id` (ADR 0050). */
  scenarioId: string;
  /** Shown as the heading until the fetch lands, so the panel never opens
   * nameless: the card the user just clicked already knows the name. */
  scenarioName: string;
  onClose: () => void;
  /** Switch to the editor on this Scenario. Offered only when the server says
   * the caller may edit it (ADR 0076). */
  onEdit: (id: string) => void;
  /** Delete this Scenario. Offered only on a reverse (ADR 0070), which is the
   * one kind that cannot reach the editor, where every other row of the
   * caller's is deleted. */
  onDelete: (id: string) => void;
}

/** The text rows, in the editor's own order so the two panels read the same
 * way round. A field that is empty or withheld is left out entirely rather
 * than shown as a heading with nothing under it. */
const SECTIONS: { key: keyof ScenarioDetail; label: string }[] = [
  { key: "short_description", label: "Kurzbeschreibung" },
  { key: "briefing", label: "Briefing für Sie" },
  { key: "description", label: "Situation" },
  { key: "case_facts", label: "Fakten des Falls" },
  { key: "call_goal", label: "Ziel des Anrufs" },
  { key: "success_condition", label: "Erfolgsbedingung" },
];

/**
 * Read-only view of a Scenario, opened by the "i" on its card.
 *
 * Same modal shell as ScenarioEditor and PersonaInfo (`editor-backdrop` /
 * `editor-panel` / `editor-scroll`, Escape and click-outside to dismiss), and
 * the same field order as the editor — so the panel a user reads and the form
 * they then edit are recognisably the same thing.
 *
 * Reading comes before writing for every Scenario (ADR 0076): the card has no
 * edit affordance any more, and "Bearbeiten" appears here instead, only on a
 * row the *server* marked `editable`. A built-in serves no `call_goal` and no
 * `success_condition` — the caller's intent is the answer key to the exercise —
 * so those two rows simply do not appear for one.
 *
 * A reverse (ADR 0070) is the one row that is the caller's and still not
 * editable, so the editor — where a Folgeszenario and every other authored row
 * is deleted — is closed to it. Its "Löschen" is here instead, in the same
 * corner of the same actions row, asking the same question. Deleting is the
 * only thing this otherwise read-only panel does, which is why it sits apart
 * from "Schließen" rather than beside it.
 */
export default function ScenarioInfo({
  scenarioId,
  scenarioName,
  onClose,
  onEdit,
  onDelete,
}: ScenarioInfoProps) {
  const [detail, setDetail] = useState<ScenarioDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const dismiss = useCallback(() => onClose(), [onClose]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") dismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dismiss]);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setError(null);
    getScenario(scenarioId)
      .then((d) => !cancelled && setDetail(d))
      .catch((e: unknown) =>
        !cancelled &&
        setError(
          e instanceof ApiError && e.status === 404
            ? "Dieses Szenario gibt es nicht mehr."
            : "Die Angaben konnten nicht geladen werden.",
        ),
      );
    return () => {
      cancelled = true;
    };
  }, [scenarioId]);

  const category = detail?.category
    ? CATEGORY_LABELS[detail.category as ScenarioCategory]
    : null;

  return (
    <div
      className="editor-backdrop"
      role="presentation"
      onMouseDown={(e) => {
        // Same rule as the editor: only a press that starts and ends on the
        // backdrop counts, so selecting text and dragging out does not close.
        if (e.target === e.currentTarget) dismiss();
      }}
    >
      <div
        className="editor-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="scenario-info-title"
      >
        <div className="editor-scroll">
          <h2 id="scenario-info-title">{detail?.name ?? scenarioName}</h2>

          {error && <p className="error">{error}</p>}

          {!detail && !error && <p>Wird geladen …</p>}

          {detail && (
            <>
              {category && <p className="persona-info-language">{category}</p>}

              <div className="persona-info-sections">
                {SECTIONS.map((section) => {
                  const value = detail[section.key];
                  if (typeof value !== "string" || value.length === 0) return null;
                  return (
                    <section className="persona-info-section" key={section.key}>
                      <h3>{section.label}</h3>
                      <p>{value}</p>
                    </section>
                  );
                })}
              </div>
            </>
          )}

          <div className="editor-actions">
            {detail?.editable && (
              <button
                type="button"
                className="editor-edit"
                onClick={() => onEdit(detail.id)}
              >
                Bearbeiten
              </button>
            )}
            {detail?.reverse && (
              <button
                type="button"
                className="editor-delete"
                onClick={() => {
                  // The editor's own wording, because it is the same act: one
                  // slip costs a row that can only be recreated from the
                  // training it came from, at the price of a model call.
                  if (window.confirm("Diesen Rollentausch wirklich löschen?")) {
                    onDelete(detail.id);
                  }
                }}
              >
                Löschen
              </button>
            )}
            <span className="editor-actions-spacer" />
            <button type="button" onClick={onClose}>
              Schließen
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
