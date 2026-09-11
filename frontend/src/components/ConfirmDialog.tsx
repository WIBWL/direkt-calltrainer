import { useId } from "react";

interface ConfirmDialogProps {
  /** The question, as a heading. */
  title: string;
  /** What is lost, or what happens. Omitted where the title says all of it. */
  body?: string;
  /** The word on the button that goes through with it. */
  confirmLabel: string;
  /** The word on the way back. */
  cancelLabel: string;
  /** Red rather than plain, for an action that destroys something. */
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * The app's own "are you sure?", laid over the panel that asked it.
 *
 * Not `window.confirm`: a native dialog is drawn by the browser, in the
 * browser's own look, at the top of the screen and away from the thing it is
 * about — it breaks out of the app in the one moment the User is being asked
 * to think about what is in front of them. It also names the app's origin
 * ("localhost:8391 sagt …"), which reads as a warning about the page rather
 * than a question from it.
 *
 * Positioned `absolute; inset: 0`, so it is mounted as a child of the
 * full-screen backdrop that owns the panel underneath (`.editor-backdrop`) and
 * covers exactly that.
 *
 * Escape is deliberately *not* handled here. Every screen that uses this
 * already listens for it to close itself, and two listeners on `window` fire
 * in the order they were registered — the panel's, being older, would win and
 * close everything. The dialog's owner therefore handles Escape for both, and
 * closes the inner one first.
 */
export default function ConfirmDialog({
  title,
  body,
  confirmLabel,
  cancelLabel,
  destructive = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const titleId = useId();

  return (
    <div
      className="editor-confirm"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onMouseDown={(e) => {
        // Kept off the panel's own backdrop handler, which would otherwise
        // read a press on this overlay as "clicked outside" and close both.
        e.stopPropagation();
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div className="editor-confirm-box">
        <h3 id={titleId}>{title}</h3>
        {body && <p>{body}</p>}
        <div className="editor-confirm-actions">
          <button type="button" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={destructive ? "editor-confirm-discard" : undefined}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
