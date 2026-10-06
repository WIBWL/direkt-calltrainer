import { useEffect, useState } from "react";

import { ApiError } from "../api";
import { getScenario, type ScenarioDetail } from "../scenarioLibrary";
import ConfirmDialog from "./ConfirmDialog";
import Modal from "./Modal";
import { StructuredText } from "./ScenarioBriefing";

interface ScenarioInfoProps {
  scenarioId: string;
  /** The heading until the fetch lands. */
  scenarioName: string;
  onClose: () => void;
  /** Only where the server allows (ADR 0062). */
  onEdit: (id: string) => void;
  /** For reverses and follow-ups (ADR 0069, 0070), which cannot reach the editor. */
  onDelete: (id: string) => void;
}

/** Never `call_goal`, the answer key (ADR 0043/0045). A built-in shows its description alone (ADR 0054). */
const SECTIONS: { key: keyof ScenarioDetail; label: string; authoredOnly?: boolean }[] = [
  { key: "description", label: "Worum es geht" },
  { key: "briefing", label: "Ihr Wissensstand", authoredOnly: true },
  { key: "case_facts", label: "Fakten des Falls" },
];

/** Read-only view from the card's "i" (ADR 0062): what the trainee may know going in. */
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
        // Confirmed: the row can only be recreated from its training, with a model call.
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

      {/* No category line: that is the filter row's business. */}
      {detail && (
        <div className="persona-info-sections">
          {SECTIONS.map((section) => {
            const value = detail[section.key];
            if (typeof value !== "string" || value.length === 0) return null;
            if (section.authoredOnly && detail.case_facts === null) return null;
            return (
              <section className="persona-info-section" key={section.key}>
                <h3>{section.label}</h3>
                <StructuredText text={value} />
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
