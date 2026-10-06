import { useCallback, useEffect, useState } from "react";

import type { TranscriptEntry } from "../protocol";
import { getScenario, type ReverseBrief } from "../scenarioLibrary";
import { loadFinishedSession, saveFinishedSession } from "../utils/finishedSession";
import type { EndedCall } from "./useLiveCall";
import type { CommittedSession } from "./useSessionSocket";

/** `null` from the hook = not fetched yet; empty strings = nothing to read. */
export interface CommittedCase {
  briefing: string;
  facts: string;
}

export interface CommitOptions {
  reverse?: boolean;
  /** F-62: walked into unread, so its case is never fetched or shown. */
  drawnName?: string | null;
  /** Seeded from the answer that created the reverse. */
  brief?: ReverseBrief | null;
}

/** A reload does not restore the selection, so the names are stored. */
export interface FinishedNames {
  personaName: string;
  scenarioName: string | null;
  personaId: string | null;
}

/** One training run from commit to restart. Routing stays in `trainingFlow`
 * (ADR 0096). Each `commit` passes a new object: that identity is the new Session (ADR 0042). */
export function useTrainingRun() {
  // A reload lands back on the wrap-up of the call that had just ended.
  const [restored] = useState(loadFinishedSession);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>(restored?.turns ?? []);
  const [endedSessionId, setEndedSessionId] = useState<string | null>(
    restored?.sessionId ?? null,
  );
  const [committed, setCommitted] = useState<CommittedSession | null>(null);
  // For the offers of what to play next (F-64): `committed` clears when the call ends.
  const [lastPlayed, setLastPlayed] = useState<{
    scenarioId: string;
    personaId: string;
  } | null>(null);
  // Only for a drawn Scenario (F-62).
  const [secretScenario, setSecretScenario] = useState<string | null>(null);
  const [committedCase, setCommittedCase] = useState<CommittedCase | null>(null);
  // Fetched once per committed Session (ADR 0070).
  const [reverseBrief, setReverseBrief] = useState<ReverseBrief | null>(null);

  // The listing withholds the case (ADR 0045), and a follow-up is not in it yet.
  useEffect(() => {
    setCommittedCase(null);
    if (!committed?.reverse) setReverseBrief(null);
    if (!committed || (!committed.reverse && secretScenario !== null)) return undefined;

    let cancelled = false;
    getScenario(committed.scenarioId)
      .then((detail) => {
        if (cancelled) return;
        if (!committed.reverse) {
          setCommittedCase({ briefing: detail.briefing, facts: detail.case_facts ?? "" });
        } else if (detail.reverse_brief) {
          setReverseBrief(detail.reverse_brief);
        }
      })
      .catch(() => {
        // The call is the point; it runs with or without the panel.
      });
    return () => {
      cancelled = true;
    };
  }, [committed, secretScenario]);

  /** Forgets the stored finished Session, so the previous wrap-up does not come back. */
  const commit = useCallback(
    (scenarioId: string, personaId: string, options: CommitOptions = {}) => {
      const { reverse = false, drawnName = null, brief = null } = options;
      saveFinishedSession(null);
      // Stated on every commit, so silence defaults to showing the Scenario.
      setSecretScenario(drawnName);
      if (brief) setReverseBrief(brief);
      setCommitted({ personaId, scenarioId, reverse });
    },
    [],
  );

  /** The next Session connects only when the User commits to it (ADR 0042). */
  const finish = (ended: EndedCall, names: FinishedNames) => {
    setTranscript(ended.turns);
    setEndedSessionId(ended.sessionId);
    saveFinishedSession({ sessionId: ended.sessionId, turns: ended.turns, ...names });
    if (committed) {
      setLastPlayed({ scenarioId: committed.scenarioId, personaId: committed.personaId });
    }
    setCommitted(null);
  };

  const cancel = useCallback(() => setCommitted(null), []);

  const restart = useCallback(() => saveFinishedSession(null), []);

  return {
    restored,
    committed,
    lastPlayed,
    secretScenario,
    committedCase,
    reverseBrief,
    transcript,
    endedSessionId,
    commit,
    finish,
    cancel,
    restart,
  };
}
