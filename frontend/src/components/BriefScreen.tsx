import type { ReactNode } from "react";

import AppLayout from "./AppLayout";

/** The last screen before a call (F-61, F-63); its way out drops the Session. */
export default function BriefScreen({
  onContinue,
  onLeave,
  children,
}: {
  onContinue: () => void;
  onLeave: () => void;
  children: ReactNode;
}) {
  return (
    <AppLayout step="prepare" navigationLocked pageClassName="brief-page">
      {children}
      <div className="brief-actions">
        <button type="button" className="start-call-button" onClick={onContinue}>
          Los geht's
        </button>
      </div>
      <button type="button" className="back-to-start-button" onClick={onLeave}>
        Zur Startseite
      </button>
    </AppLayout>
  );
}
