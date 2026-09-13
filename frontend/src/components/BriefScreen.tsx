import type { ReactNode } from "react";

import AppLayout from "./AppLayout";

/**
 * The last screen before a call: a briefing, the button that goes on, and the
 * way out (F-61, F-63).
 *
 * Shared by the reverse's briefing and the ordinary call's case, because it is
 * the same moment in the flow — the last thing read before someone has to
 * speak. The way out is the microphone check's door, in the same place: for a
 * reverse this screen *replaces* that one, so leaving must not read as a
 * different act. Leaving drops the committed Session rather than holding its
 * connection open.
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
