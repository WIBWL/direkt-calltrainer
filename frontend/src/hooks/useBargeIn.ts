import { useCallback, useRef } from "react";

import type { CallState } from "../protocol";

/** Tells the server how much of the Persona's reply the user heard (ADR 0035). */

export interface BargeInSocket {
  callState: CallState;
  sendInterrupt: (playedMs: number) => void;
  sendSpeaking: () => void;
  endSession: () => void;
}

export interface BargeInPlayback {
  isPlaying: boolean;
  /** Stops the reply; returns the ms heard. Dropping it keeps unheard words. */
  interrupt: () => number;
}

export interface BargeIn {
  /** Stays "speaking" until playback ends, though the server already says "listening". */
  displayState: CallState;
  /** Must keep one identity: `useMicrophoneVAD` wires it once. */
  bargeIn: () => void;
  endCall: () => void;
}

export function useBargeIn(
  socket: BargeInSocket,
  playback: BargeInPlayback,
): BargeIn {
  const displayState: CallState =
    socket.callState === "listening" && playback.isPlaying ? "speaking" : socket.callState;

  // Read through a ref so the callbacks keep one identity without going stale.
  const latest = useRef({ socket, playback, displayState });
  latest.current = { socket, playback, displayState };

  const bargeIn = useCallback(() => {
    const { socket: s, playback: p, displayState: state } = latest.current;
    // The user's own turn: no interrupt, but stop the server's "Hallo?" (ADR 0110).
    if (state === "listening") {
      s.sendSpeaking();
      return;
    }
    s.sendInterrupt(p.interrupt());
  }, []);

  const endCall = useCallback(() => {
    const { socket: s, playback: p, displayState: state } = latest.current;
    // Report the played position before the socket closes.
    if (state !== "listening") s.sendInterrupt(p.interrupt());
    s.endSession();
  }, []);

  return { displayState, bargeIn, endCall };
}
