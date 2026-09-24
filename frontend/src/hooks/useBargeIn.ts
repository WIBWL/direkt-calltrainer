import { useCallback, useRef } from "react";

import type { CallState } from "../protocol";

/**
 * Tells the server how much of the Persona's reply the user heard when they cut
 * in (ADR 0035); dropping `interrupt()`'s return silently keeps unheard words.
 * Owns *when* a barge-in is asked for, not the mechanisms that stop the audio.
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
   * What the call screen shows. The server sends "listening" when the Turn
   * completes while the last chunk may still be playing, so this holds at
   * "speaking" until playback finishes. Both callbacks below branch on it.
   */
  displayState: CallState;
  /**
   * The user started speaking over the Persona. Stable for the component's
   * life: `useMicrophoneVAD` wires it into `MicVAD.new` once and never rewires.
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
   * Latest values for the two callbacks below, which must keep one identity
   * (see `bargeIn`): closing over `socket`/`playback` would freeze the first
   * render's values and leave barge-in wired to a dead socket, silently.
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
