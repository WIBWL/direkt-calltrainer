import { useEffect, useState } from "react";

import { ApiError } from "../api";
import { getScenario, type ScenarioDetail } from "../scenarioLibrary";
import ConfirmDialog from "./ConfirmDialog";
import Modal from "./Modal";

interface ScenarioInfoProps {
  /** The Scenario to describe — its `extern_id` (ADR 0050). */
  scenarioId: string;
  /** Shown as the heading until the fetch lands, so the panel never opens
   * nameless: the card the user just clicked already knows the name. */
  scenarioName: string;
  onClose: () => void;
  /** Switch to the editor on this Scenario. Offered only when the server says
   * the caller may edit it (ADR 0062). */
  onEdit: (id: string) => void;
  /** Delete this Scenario. Offered on the two kinds built from a Session —
   * a reverse (ADR 0070) and a follow-up (ADR 0069) — which are the rows that
   * cannot reach the editor, where every hand-authored row is deleted. */
  onDelete: (id: string) => void;
}

/** Text rows in the editor's order; empty or withheld fields are left out. `call_goal` is never shown: it is
 * the answer key to the exercise (ADR 0043/0045), for built-in and authored Scenarios alike. */
const SECTIONS: { key: keyof ScenarioDetail; label: string }[] = [
  { key: "briefing", label: "Briefing" },
  { key: "case_facts", label: "Fakten des Falls" },
];

/**
 * Read-only Scenario view from the card's "i" (ADR 0062): the editor's `Modal` and field order, edit button only
 * where the server set `editable`. Shows only what the trainee may know going in. Reverses (ADR 0070) and
 * follow-ups (ADR 0069) are not editable, so their delete control lives here.
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

  // The question first, the panel behind it second (see `Modal`).
  const dismiss = () => {
    if (confirmingDelete) setConfirmingDelete(false);
    else onClose();
  };

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
    <Modal
      labelledBy="scenario-info-title"
      onDismiss={dismiss}
      overlay={
        // A whole phrase per kind: the two take different articles. Confirmed because the row can only be
        // recreated from its training, with a model call, if that training is still stored.
        confirmingDelete &&
        detail && (
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
        )
      }
    >
      <h2 id="scenario-info-title">{detail?.name ?? scenarioName}</h2>

      {error && <p className="error">{error}</p>}

      {!detail && !error && <p>Wird geladen …</p>}

      {/* No category line: it is a filter, and the filter row on the selection
          screen is where it belongs. Here it said only which chip this card
          sits under, which the reader had just used to find it. */}
      {detail && (
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
      )}

      <div className="editor-actions">
        {detail?.editable && (
          <button type="button" className="editor-edit" onClick={() => onEdit(detail.id)}>
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
    </Modal>
  );
}
