import { useState } from "react";

import { deleteSession } from "../sessions";

/**
 * Deleting one stored training (ADR 0066): the request and its two states.
 *
 * A hook beside the prompt rather than inside it, because the two places that
 * offer the deletion — a row in the history and the training's own page — open
 * and close the question themselves, and the history's bin button has to know
 * whether a deletion is still in flight before it lets the question close.
 */
export function useSessionDeletion(sessionId: string | undefined, onDeleted: () => void) {
  const [deleting, setDeleting] = useState(false);
  const [failed, setFailed] = useState(false);

  const remove = async () => {
    // Unreachable without one on either screen, but the page's route param is
    // optional, and without this guard the request would go to
    // `/api/sessions/undefined`.
    if (!sessionId) return;
    setDeleting(true);
    setFailed(false);
    try {
      await deleteSession(sessionId);
      // Both callers leave the training behind here — the row disappears, the
      // page navigates away — so there is no state to reset afterwards.
      onDeleted();
    } catch (e) {
      console.debug("[delete session] failed", e);
      setFailed(true);
      setDeleting(false);
    }
  };

  return { deleting, failed, remove };
}

/**
 * The question on a training's own page, once it is open. It says what goes
 * with the training, because the deletion is final and reaches the wrap-up and
 * the figures too. The history asks the same thing with a check and a cross in
 * place of its bin (`SessionHistory`), where a paragraph per row would push the
 * list apart.
 */
export default function DeleteSessionPrompt({
  deleting,
  failed,
  onConfirm,
  onCancel,
}: {
  deleting: boolean;
  failed: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <>
      <p>
        <strong>Dieses Training löschen?</strong> Gesprächsprotokoll, Kennzahlen und
        Auswertung werden entfernt. Das lässt sich nicht rückgängig machen.
      </p>
      <div className="consent-confirm-actions">
        <button
          type="button"
          className="consent-button consent-button-danger"
          onClick={onConfirm}
          disabled={deleting}
        >
          {deleting ? "Wird gelöscht …" : "Endgültig löschen"}
        </button>
        <button
          type="button"
          className="consent-button consent-button-secondary"
          onClick={onCancel}
          disabled={deleting}
        >
          Abbrechen
        </button>
      </div>
      {failed && (
        <p className="consent-error">
          Das Training konnte nicht gelöscht werden. Bitte versuchen Sie es erneut.
        </p>
      )}
    </>
  );
}
