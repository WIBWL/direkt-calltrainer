import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  useBargeIn,
  type BargeInPlayback,
  type BargeInSocket,
} from "./useBargeIn";
import type { CallState } from "../protocol";

/**
 * The wire between the two hooks, which neither of their own specs covers.
 *
 * `useStreamedAudioPlayback.test.ts` proves `interrupt()` stops the audio and
 * returns how much was heard; `useSessionSocket.test.ts` proves the socket
 * stops forwarding chunks. Nothing proved the number got from one to the other
 * — and dropping it is a silent failure: the transcript keeps words nobody
 * heard, which is exactly what ADR 0035 exists to prevent.
 *
 * Plain fakes rather than the Web Audio and WebSocket doubles: what is under
 * test here is the wire, not the audio.
 */

function fakes(callState: CallState, isPlaying: boolean, playedMs = 1234) {
  const socket: BargeInSocket = {
    callState,
    sendInterrupt: vi.fn(),
    endSession: vi.fn(),
  };
  const playback: BargeInPlayback = {
    isPlaying,
    interrupt: vi.fn(() => playedMs),
  };
  return { socket, playback };
}

const render = (socket: BargeInSocket, playback: BargeInPlayback) =>
  renderHook(({ s, p }: { s: BargeInSocket; p: BargeInPlayback }) => useBargeIn(s, p), {
    initialProps: { s: socket, p: playback },
  });

describe("what the call screen shows", () => {
  it("holds at speaking while the last chunk plays out", () => {
    // The server says the Turn is over the moment it has the transcript; the
    // audio it already sent is still playing locally.
    const { socket, playback } = fakes("listening", true);
    expect(render(socket, playback).result.current.displayState).toBe("speaking");
  });

  it("follows the server once playback has finished", () => {
    const { socket, playback } = fakes("listening", false);
    expect(render(socket, playback).result.current.displayState).toBe("listening");
  });

  it("never overrides a state that is not listening", () => {
    const { socket, playback } = fakes("thinking", true);
    expect(render(socket, playback).result.current.displayState).toBe("thinking");
  });
});

describe("barging in", () => {
  it("forwards the played position to the server (ADR 0035)", () => {
    // The assertion that matters: the number `interrupt()` returns is the
    // number the server is told. Dropping it keeps unheard words in the
    // transcript, and nothing else in the suite would notice.
    const { socket, playback } = fakes("speaking", true, 1234);
    render(socket, playback).result.current.bargeIn();

    expect(playback.interrupt).toHaveBeenCalledTimes(1);
    expect(socket.sendInterrupt).toHaveBeenCalledWith(1234);
  });

  it("does nothing during the user's own turn", () => {
    // The other failure direction: an interrupt reported here would trim a
    // reply that had already finished.
    const { socket, playback } = fakes("listening", false);
    render(socket, playback).result.current.bargeIn();

    expect(playback.interrupt).not.toHaveBeenCalled();
    expect(socket.sendInterrupt).not.toHaveBeenCalled();
  });

  it("still fires while the tail of a reply plays out", () => {
    // The server already said "listening", but the Persona is audibly still
    // talking — the user talking over it is a real barge-in.
    const { socket, playback } = fakes("listening", true, 900);
    render(socket, playback).result.current.bargeIn();

    expect(socket.sendInterrupt).toHaveBeenCalledWith(900);
  });
});

describe("ending the call", () => {
  it("reports the played position before ending, mid-reply", () => {
    const { socket, playback } = fakes("speaking", true, 500);
    render(socket, playback).result.current.endCall();

    expect(socket.sendInterrupt).toHaveBeenCalledWith(500);
    expect(socket.endSession).toHaveBeenCalledTimes(1);
    // Order matters: ending first would close the socket before the position
    // could be sent.
    const interruptOrder = (socket.sendInterrupt as ReturnType<typeof vi.fn>).mock
      .invocationCallOrder[0] as number;
    const endOrder = (socket.endSession as ReturnType<typeof vi.fn>).mock
      .invocationCallOrder[0] as number;
    expect(interruptOrder).toBeLessThan(endOrder);
  });

  it("just ends when the user was the one talking", () => {
    const { socket, playback } = fakes("listening", false);
    render(socket, playback).result.current.endCall();

    expect(socket.sendInterrupt).not.toHaveBeenCalled();
    expect(socket.endSession).toHaveBeenCalledTimes(1);
  });
});

describe("the callbacks VAD holds for the whole call", () => {
  it("keep one identity, because MicVAD is wired once and never rewired", () => {
    const first = fakes("speaking", true);
    const view = render(first.socket, first.playback);
    const { bargeIn, endCall } = view.result.current;

    const second = fakes("listening", false);
    view.rerender({ s: second.socket, p: second.playback });

    expect(view.result.current.bargeIn).toBe(bargeIn);
    expect(view.result.current.endCall).toBe(endCall);
  });

  it("act on the current socket, not the one they were created with", () => {
    // What the latest-value ref buys: the callbacks used to capture
    // sendInterrupt and interrupt from the first render, and were correct only
    // because four separate dependency arrays happened to be empty.
    const first = fakes("speaking", true, 100);
    const view = render(first.socket, first.playback);
    const frozen = view.result.current.bargeIn;

    const second = fakes("speaking", true, 700);
    view.rerender({ s: second.socket, p: second.playback });
    frozen();

    expect(first.socket.sendInterrupt).not.toHaveBeenCalled();
    expect(second.socket.sendInterrupt).toHaveBeenCalledWith(700);
  });

  it("see the current state, so a stale one cannot suppress a barge-in", () => {
    // The subtle failure this guards: a callback holding the first render's
    // "listening" would return early and never report an interrupt again.
    const first = fakes("listening", false);
    const view = render(first.socket, first.playback);
    const frozen = view.result.current.bargeIn;

    const second = fakes("speaking", true, 42);
    view.rerender({ s: second.socket, p: second.playback });
    frozen();

    expect(second.socket.sendInterrupt).toHaveBeenCalledWith(42);
  });
});
