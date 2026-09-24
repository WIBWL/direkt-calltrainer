import type { ReactNode } from "react";

import AppLayout from "./AppLayout";

/**
 * The last screen before a call: a briefing, the button on, and the way out (F-61,
 * F-63). Shared by the reverse's briefing and the ordinary case. The way out sits where
 * the mic check's does, since for a reverse this replaces it; leaving drops the Session.
 */
export default function BriefScreen({
  onContinue,
  onLeave,
  children,
}: {
  onContinue: () => void;
  onLeave: () => void;
  /** The briefing itself, or what stands in while it is on its way. */
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
