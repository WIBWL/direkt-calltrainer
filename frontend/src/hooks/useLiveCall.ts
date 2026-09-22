import { useCallback, useEffect, useRef, useState } from "react";

import type { CallState, TranscriptEntry } from "../protocol";
import { useBargeIn } from "./useBargeIn";
import { useSessionSocket, type CommittedSession } from "./useSessionSocket";
import { useStreamedAudioPlayback } from "./useStreamedAudioPlayback";

/**
 * The live call as one thing: the connection, the audio it plays and the
 * three rules that bind the two together.
 *
 * Those rules used to be held by comments in `App.tsx`, each one beside an
 * effect that had to agree with another effect somewhere else:
 *
 * - the buffered opening line is dropped whenever the *connection* is
 *   replaced, so the reset has to key on exactly what the socket keys on;
 * - revealing that opening line and starting the server's clock are one act,
 *   so `activate()` must never run without `sendActivate()`;
 * - a call the Persona ended waits for its goodbye to finish playing, a call
 *   the User ended does not.
 *
 * Here the first holds by construction — both effects read the one
 * `committed` this hook was given — the second is the one function `accept`,
 * and the third is `endIsDue`, a pure function with its own tests.
 * `useBargeIn` is composed in rather than called beside it, since it needs the
 * same socket and playback and nothing else does.
 *
 * What stays outside: which screen follows, what is kept of the call and
 * where. The ended call is handed to `onCallOver` and this hook forgets it.
 */

/** A call the server has said is over, with what it left behind. */
export interface EndedCall {
  reason: "user" | "error" | "completed";
  turns: TranscriptEntry[];
  /** Names the persisted Session; null where nothing was stored. */
  sessionId: string | null;
}

/**
 * Whether an ended call may be torn down now.
 *
 * `session.ended` can arrive while the Persona's closing line is still playing
 * out — the server sends it the moment the reply's Turn completes, independent
 * of local playback. Tearing down then cuts the goodbye off mid-sentence, so a
 * natural or failed ending waits for the audio. A User who pressed the button
 * wants the call to stop, and it does.
 */
export function endIsDue(end: EndedCall, isPlaying: boolean): boolean {
  return end.reason === "user" || !isPlaying;
}

export interface LiveCall {
  /** What the call screen shows (see `useBargeIn`). */
  displayState: CallState;
  /** The Persona's output level, for the animation. */
  audioLevel: number;
  error: string | null;
  /** The User started talking over the Persona. One identity for the life of
   * the component, which `useMicrophoneVAD` depends on. */
  bargeIn: () => void;
  endCall: () => void;
  sendTurnAudio: (audio: Blob, mimeType: string) => void;
  /**
   * The User picked up: reveal the buffered opening line and start the
   * Session clock on the server, as one act (ADR 0042).
   */
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

  // Buffered opening audio belongs to exactly one connection (ADR 0042). The
  // socket above is replaced whenever `committed` changes, so whatever the
  // previous one buffered is audio from a Session that will never be
  // conducted — drop it, and go back to holding. Keyed on the same value the
  // socket keys on, which is the whole point of the two living here.
  useEffect(() => {
    playback.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- playback is stable-shaped; this must mirror the connection key exactly
  }, [committed]);

  // Read through a ref, as `useBargeIn` does: the caller's callback closes
  // over its own render, and the effect below must not re-run when it changes.
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
