import { useEffect, type ReactNode } from "react";

/**
 * The app's modal shell: a backdrop, a panel, and the two ways out of it —
 * Escape and a press on the backdrop.
 *
 * Shared by the Scenario editor and the two read-only info panels, so the
 * panels on the setup screen read as one thing and close the same way.
 *
 * `onDismiss` answers both. An owner with a question open over its panel
 * (`overlay`, a `ConfirmDialog`) closes that question first rather than the
 * panel: the question handles no Escape of its own, because two `window`
 * listeners fire in registration order and the panel's would win (see
 * `ConfirmDialog`). A press on the backdrop cannot reach the owner while the
 * question is open anyway — the question covers the backdrop and keeps its own
 * presses to itself.
 */
export default function Modal({
  labelledBy,
  onDismiss,
  overlay,
  children,
}: {
  /** The id of the panel's heading, for `aria-labelledby`. */
  labelledBy: string;
  onDismiss: () => void;
  /** Laid over the panel, inside the backdrop — where `ConfirmDialog` has to
   *  mount to cover it. */
  overlay?: ReactNode;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onDismiss]);

  return (
    <div
      className="editor-backdrop"
      role="presentation"
      onMouseDown={(e) => {
        // Only a press that starts on the backdrop itself — not a text
        // selection dragged out of the panel — counts as "click outside".
        if (e.target === e.currentTarget) onDismiss();
      }}
    >
      <div className="editor-panel" role="dialog" aria-modal="true" aria-labelledby={labelledBy}>
        <div className="editor-scroll">{children}</div>
      </div>

      {overlay}
    </div>
  );
}
