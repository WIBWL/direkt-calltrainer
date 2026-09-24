import { useEffect, type ReactNode } from "react";

/**
 * The app's modal shell: backdrop, panel, dismissed by Escape or a backdrop press. With a `ConfirmDialog` open
 * (`overlay`), `onDismiss` must close the question first: it handles no Escape itself, since two `window`
 * listeners fire in registration order and the panel's would win (see `ConfirmDialog`).
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
