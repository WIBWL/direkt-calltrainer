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
 * The app's own "are you sure?" (not `window.confirm`), laid over the panel that asked;
 * `absolute; inset: 0`, so it mounts inside the owner's backdrop (`.editor-backdrop`).
 * Escape is deliberately *not* handled here: the owner's older `window` listener would
 * fire first and close everything, so the owner handles Escape and closes this first.
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
