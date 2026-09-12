import { useCallback, useRef } from "react";

import type { CallState } from "../protocol";

/**
 * The wire between hearing the user start talking and telling the server how
 * much of the Persona's reply they actually heard (ADR 0035).
 *
 * One line used to carry the whole guarantee — `socket.sendInterrupt(
 * playback.interrupt())`, written twice in `App.tsx`. Both hooks had their own
 * tests; the line between them had none, and `interrupt()`'s return value is
 * easy to drop, which would silently keep words in the transcript that nobody
 * heard.
 *
 * What it deliberately does not do: the four mechanisms that make a barge-in
 * actually stop the audio — the epoch counter, the master gain, stopping the
 * scheduled sources, and the socket refusing further chunks — stay where they
 * are. This owns when they are asked for, not how they work.
 */

/** What this needs of the session socket, and nothing more. */
export interface BargeInSocket {
  callState: CallState;
  /** Report how much of the current reply was played before the user cut in. */
  sendInterrupt: (playedMs: number) => void;
  endSession: () => void;
}

/** What this needs of the playback, and nothing more. */
export interface BargeInPlayback {
  isPlaying: boolean;
  /** Stop the reply and return how many milliseconds of it were heard. */
  interrupt: () => number;
}

export interface BargeIn {
  /**
   * What the call screen shows.
   *
   * The server sends "listening" the moment the Turn completes, but the last
   * chunk can still be playing out locally — so this holds at "speaking" until
   * playback has actually finished. It is the only answer to "is the Persona
   * still talking?" that accounts for both sides, and both callbacks below
   * branch on it.
   */
  displayState: CallState;
  /**
   * The user started speaking over the Persona.
   *
   * Stable for the life of the component, because `useMicrophoneVAD` wires
   * this into `MicVAD.new` once and never rewires it — the callback given on
   * the first render is the one that fires for the whole call.
   */
  bargeIn: () => void;
  /** Hang up. Reports the played position first where the Persona was still
   * talking, so the transcript keeps only what was heard. */
  endCall: () => void;
}

export function useBargeIn(
  socket: BargeInSocket,
  playback: BargeInPlayback,
): BargeIn {
  const displayState: CallState =
    socket.callState === "listening" && playback.isPlaying ? "speaking" : socket.callState;

  /**
   * The current everything, refreshed each render and read only from the two
   * callbacks below.
   *
   * They cannot close over `socket` and `playback` directly: they must keep one
   * identity (see `bargeIn`), so a closure would hold the first render's
   * values forever. Reading through a ref also removes what used to hold this
   * together by luck — the callbacks captured `sendInterrupt`, `endSession` and
   * `interrupt`, which are stable today only because four separate dependency
   * arrays happen to be empty. A single dependency added to any of them would
   * have frozen barge-in against a dead socket, with no type error and no
   * failing test.
   */
  const latest = useRef({ socket, playback, displayState });
  latest.current = { socket, playback, displayState };

  const bargeIn = useCallback(() => {
    const { socket: s, playback: p, displayState: state } = latest.current;
    // Not a barge-in if the Persona was not talking: the user's own turn is
    // the normal case, and reporting an interrupt there would trim a reply
    // that had already finished.
    if (state === "listening") return;
    s.sendInterrupt(p.interrupt());
  }, []);

  const endCall = useCallback(() => {
    const { socket: s, playback: p, displayState: state } = latest.current;
    // Hanging up mid-reply is a barge-in too: report the played position
    // first, or the transcript keeps the part of that reply the user never
    // heard (ADR 0035). Order matters — ending first would close the socket
    // before the position could be sent.
    if (state !== "listening") s.sendInterrupt(p.interrupt());
    s.endSession();
  }, []);

  return { displayState, bargeIn, endCall };
}
