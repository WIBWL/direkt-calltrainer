import { useCallback, useEffect, useRef, useState } from "react";

import type { CallState, TranscriptEntry } from "../protocol";
import { useBargeIn } from "./useBargeIn";
import { useSessionSocket, type CommittedSession } from "./useSessionSocket";
import { useStreamedAudioPlayback } from "./useStreamedAudioPlayback";

/** The live call. The opening-line reset keys on the socket's `committed`;
 * `accept` is the only way to `activate()`; a Persona-ended call waits for its
 * goodbye to play out (`endIsDue`). */

export interface EndedCall {
  reason: "user" | "error" | "completed";
  turns: TranscriptEntry[];
  /** Null where nothing was stored. */
  sessionId: string | null;
}

/** `session.ended` can arrive while the goodbye plays; only a hang-up stops at once. */
export function endIsDue(end: EndedCall, isPlaying: boolean): boolean {
  return end.reason === "user" || !isPlaying;
}

export interface LiveCall {
  displayState: CallState;
  audioLevel: number;
  error: string | null;
  /** One identity for the component's life; `useMicrophoneVAD` depends on it. */
  bargeIn: () => void;
  endCall: () => void;
  sendTurnAudio: (audio: Blob, mimeType: string) => void;
  /** Reveals buffered opening audio (a reverse's only, ADR 0110) and starts the server clock, as one act (ADR 0042). */
  accept: () => void;
}

export function useLiveCall(
  committed: CommittedSession | null,
  onCallOver: (ended: EndedCall) => void,
): LiveCall {
  const playback = useStreamedAudioPlayback();
  const [pendingEnd, setPendingEnd] = useState<EndedCall | null>(null);

  const handleEnded = useCallback(
    (reason: EndedCall["reason"], turns: TranscriptEntry[], sessionId: string | null) => {
      setPendingEnd({ reason, turns, sessionId });
    },
    [],
  );

  const socket = useSessionSocket({
    session: committed,
    onAudioChunk: playback.enqueue,
    onEnded: handleEnded,
  });

  // Buffered audio belongs to one connection (ADR 0042): keyed like the socket.
  useEffect(() => {
    playback.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- playback is stable-shaped; this must mirror the connection key exactly
  }, [committed]);

  // A ref, as in `useBargeIn`: the effect must not re-run on a new callback.
  const latest = useRef({ onCallOver, playback, socket });
  latest.current = { onCallOver, playback, socket };

  useEffect(() => {
    if (pendingEnd === null || !endIsDue(pendingEnd, playback.isPlaying)) return;
    latest.current.playback.reset();
    setPendingEnd(null);
    latest.current.onCallOver(pendingEnd);
  }, [pendingEnd, playback.isPlaying]);

  const { displayState, bargeIn, endCall } = useBargeIn(socket, playback);

  const accept = useCallback(() => {
    latest.current.playback.activate();
    latest.current.socket.sendActivate();
  }, []);

  return {
    displayState,
    audioLevel: playback.audioLevel,
    error: socket.error,
    bargeIn,
    endCall,
    sendTurnAudio: socket.sendTurnAudio,
    accept,
  };
}
