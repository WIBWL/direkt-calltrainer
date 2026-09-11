import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../api";
import ConfirmDialog from "./ConfirmDialog";
import { getScenario, type ScenarioDetail } from "../scenarioLibrary";

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
  /** Delete this Scenario. Offered on the two kinds built from a Session —
   * a reverse (ADR 0070) and a follow-up (ADR 0069) — which are the rows that
   * cannot reach the editor, where every hand-authored row is deleted. */
  onDelete: (id: string) => void;
}

/** The text rows, in the editor's own order so the two panels read the same
 * way round. A field that is empty or withheld is left out entirely rather
 * than shown as a heading with nothing under it.
 *
 * `call_goal` is deliberately not among them, for any kind of Scenario: it
 * says what the caller wants and the bar that settles the call, which is the
 * answer key to the exercise. It was withheld from built-ins for exactly that
 * reason (ADR 0043/0045) and reading it in advance spoils an authored one just
 * as thoroughly — the editor is where its author sees it again. */
const SECTIONS: { key: keyof ScenarioDetail; label: string }[] = [
  { key: "briefing", label: "Briefing" },
  { key: "case_facts", label: "Fakten des Falls" },
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
 * row the *server* marked `editable`. What the panel shows is the case as the
 * trainee may know it going in — the situation, their own briefing and the
 * facts — and nothing of what the caller is after. The teaser is not among
 * them either: it is the card this panel was opened from, and repeating it
 * under the same title says nothing the reader has not just read.
 *
 * A reverse (ADR 0070) and a follow-up (ADR 0069) are the rows that are the
 * caller's and still not editable, so the editor — where every hand-authored
 * row is deleted — is closed to both. Their "Löschen" is here instead, in the
 * same corner of the same actions row, asking the same question of each.
 * Deleting is the only thing this otherwise read-only panel does, which is why
 * it sits apart from "Schließen" rather than beside it.
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
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const dismiss = useCallback(() => onClose(), [onClose]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      // The question first, the panel behind it second — see ConfirmDialog on
      // why the escape key is handled out here rather than in there.
      if (confirmingDelete) setConfirmingDelete(false);
      else dismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dismiss, confirmingDelete]);

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

  return (
    <div
      className="editor-backdrop"
      role="presentation"
      onMouseDown={(e) => {
        // Same rule as the editor: only a press that starts and ends on the
        // backdrop counts, so selecting text and dragging out does not close —
        // and never while a question is open over it.
        if (e.target === e.currentTarget && !confirmingDelete) dismiss();
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
              {/* No category line: it is a filter, and the filter row on the
                  selection screen is where it belongs. Here it said only
                  which chip this card sits under, which the reader had just
                  used to find it. */}
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
            {detail && (detail.reverse || detail.follow_up) && (
              <button
                type="button"
                className="editor-delete"
                onClick={() => setConfirmingDelete(true)}
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

      {/* The whole phrase per kind, not a noun slotted into one sentence: der
          Rollentausch and das Folgeszenario do not take the same article. It
          asks at all because one slip costs a row that can only be recreated
          from the training it came from, at the price of a model call — if
          that training is even still stored. */}
      {confirmingDelete && detail && (
        <ConfirmDialog
          title={
            detail.reverse
              ? "Diesen Rollentausch wirklich löschen?"
              : "Dieses Folgeszenario wirklich löschen?"
          }
          body={
            detail.reverse
              ? "Neu erstellen lässt er sich nur aus dem Gespräch, das er vertauscht — solange es noch gespeichert ist."
              : "Neu erstellen lässt es sich nur aus dem Gespräch, aus dem es entstanden ist — solange es noch gespeichert ist."
          }
          cancelLabel="Behalten"
          confirmLabel="Löschen"
          destructive
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={() => {
            setConfirmingDelete(false);
            onDelete(detail.id);
          }}
        />
      )}
    </div>
  );
}
