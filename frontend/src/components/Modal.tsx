import { useEffect, type ReactNode } from "react";

/** Backdrop and panel, dismissed by Escape or a backdrop press. With an `overlay`
 * open, `onDismiss` closes the question first (see `ConfirmDialog`). */
export default function Modal({
  labelledBy,
  onDismiss,
  overlay,
  children,
}: {
  labelledBy: string;
  onDismiss: () => void;
  /** Where `ConfirmDialog` mounts. */
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
        // Not a text selection dragged out of the panel.
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
