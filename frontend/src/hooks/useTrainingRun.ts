import { useCallback, useEffect, useState } from "react";

import type { TranscriptEntry } from "../protocol";
import { getScenario, type ReverseBrief } from "../scenarioLibrary";
import { loadFinishedSession, saveFinishedSession } from "../utils/finishedSession";
import type { EndedCall } from "./useLiveCall";
import type { CommittedSession } from "./useSessionSocket";

/** The case of an ordinary committed call. `null` from the hook means "not
 *  fetched yet" and is what the case screen waits on; empty strings mean the
 *  case has nothing to read. */
export interface CommittedCase {
  briefing: string;
  facts: string;
}

export interface CommitOptions {
  /** The User rings and the Persona answers (ADR 0070). */
  reverse?: boolean;
  /** The drawn Scenario's name, for a Zufallsszenario (F-62): the one case the
   *  User is meant to walk into unread, so its case is never fetched and the
   *  call screen must not show it. */
  drawnName?: string | null;
  /** A reverse's briefing where the caller already has it — the answer that
   *  just created the reverse — so its screen is not empty for one request. */
  brief?: ReverseBrief | null;
}

/** What the finished Session is remembered under across a reload: the names
 *  come from the selection, which a reload does not restore. */
export interface FinishedNames {
  personaName: string;
  scenarioName: string | null;
  personaId: string | null;
}

/** One training run from commit to restart: the committed Session, its case or
 * briefing, the drawn name, the ended transcript and what survives a reload.
 * Routing stays in `trainingFlow` (ADR 0096). `commit` runs only on a deliberate
 * press (ADR 0042), with a new object each time: that identity is the new Session. */
export function useTrainingRun() {
  // Read once on mount: a reload lands back on the wrap-up of the call that
  // had just ended.
  const [restored] = useState(loadFinishedSession);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>(restored?.turns ?? []);
  // Names the persisted Session so its Feedback can be fetched once the
  // worker has produced it. Not kept anywhere but here: the wrap-up is
  // reachable for as long as its screen is, and no longer.
  const [endedSessionId, setEndedSessionId] = useState<string | null>(
    restored?.sessionId ?? null,
  );
  const [committed, setCommitted] = useState<CommittedSession | null>(null);
  // The pairing just played, kept past the end of the call for the offers of
  // what to play next (F-64): `committed` is cleared the moment the call ends.
  const [lastPlayed, setLastPlayed] = useState<{
    scenarioId: string;
    personaId: string;
  } | null>(null);
  // Set only for a drawn Scenario (F-62). Null means the User picked the case
  // themselves and knows what it is.
  const [secretScenario, setSecretScenario] = useState<string | null>(null);
  const [committedCase, setCommittedCase] = useState<CommittedCase | null>(null);
  // Shown on the briefing screen and beside the call (ADR 0070); fetched once
  // per committed Session rather than once per screen.
  const [reverseBrief, setReverseBrief] = useState<ReverseBrief | null>(null);

  // The case of an ordinary call or a reverse's briefing (ADR 0070), from the
  // detail route: the listing withholds the case (ADR 0045), and a follow-up's
  // row is not in the library yet. A failure keeps any briefing `commit` seeded.
  useEffect(() => {
    setCommittedCase(null);
    if (!committed?.reverse) setReverseBrief(null);
    // Nothing to fetch for a drawn Scenario, whose case is withheld (F-62).
    if (!committed || (!committed.reverse && secretScenario !== null)) return undefined;

    let cancelled = false;
    getScenario(committed.scenarioId)
      .then((detail) => {
        if (cancelled) return;
        if (!committed.reverse) {
          setCommittedCase({ briefing: detail.briefing, facts: detail.case_facts });
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

  /** Commit to a Session. The stored finished Session goes here rather than in
   *  whoever called: once a new call is committed to, the previous wrap-up must
   *  not come back on the next reload. */
  const commit = useCallback(
    (scenarioId: string, personaId: string, options: CommitOptions = {}) => {
      const { reverse = false, drawnName = null, brief = null } = options;
      saveFinishedSession(null);
      // Every commit states it, so a path that says nothing gets the safe
      // answer: a Scenario shown, not one wrongly hidden.
      setSecretScenario(drawnName);
      if (brief) setReverseBrief(brief);
      setCommitted({ personaId, scenarioId, reverse });
    },
    [],
  );

  /** The call is over and its goodbye has been heard: keep what was said,
   *  remember the finished Session across a reload, and let the next Session
   *  connect only when the User commits to it (ADR 0042). */
  const finish = (ended: EndedCall, names: FinishedNames) => {
    setTranscript(ended.turns);
    setEndedSessionId(ended.sessionId);
    saveFinishedSession({ sessionId: ended.sessionId, turns: ended.turns, ...names });
    if (committed) {
      setLastPlayed({ scenarioId: committed.scenarioId, personaId: committed.personaId });
    }
    setCommitted(null);
  };

  /** The microphone check was abandoned: the opening line generated for this
   *  Session is spent, but there is no point holding the connection open. */
  const cancel = useCallback(() => setCommitted(null), []);

  /** Back to the start: the wrap-up must not come back on the next reload. */
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
