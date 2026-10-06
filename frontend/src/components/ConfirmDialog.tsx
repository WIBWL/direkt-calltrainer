import { useId } from "react";

interface ConfirmDialogProps {
  title: string;
  /** Omitted where the title says it all. */
  body?: string;
  confirmLabel: string;
  cancelLabel: string;
  /** For an action that destroys something. */
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** The app's own "are you sure?", mounted inside the owner's backdrop. Escape is the
 * owner's: its older `window` listener would fire first and close everything. */
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
        // Or the owner's backdrop reads it as a click outside.
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
