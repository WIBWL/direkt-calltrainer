import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { latestSocket } from "../test/setup";
import { useSessionSocket, type CommittedSession } from "./useSessionSocket";

vi.mock("../auth", () => ({
  currentAccessToken: () => Promise.resolve("test-token"),
}));

const SESSION: CommittedSession = { personaId: "p1", scenarioId: "s1", reverse: false };

/** Through open, handshake and "speaking", so the next binary frame is live audio. */
async function renderSpeakingSession() {
  const onAudioChunk = vi.fn();
  const onEnded = vi.fn();
  const view = renderHook(() =>
    useSessionSocket({ session: SESSION, onAudioChunk, onEnded }),
  );

  await act(async () => {
    latestSocket().simulateOpen();
  });
  act(() => {
    latestSocket().serverJson({ type: "session.started", session_id: "abc" });
    latestSocket().serverJson({ type: "state", value: "speaking" });
  });

  return { ...view, onAudioChunk, onEnded };
}

describe("useSessionSocket audio gating on barge-in", () => {
  it("forwards persona audio while the reply is playing", async () => {
    const { onAudioChunk } = await renderSpeakingSession();

    act(() => {
      latestSocket().serverBinary();
      latestSocket().serverBinary();
    });

    expect(onAudioChunk).toHaveBeenCalledTimes(2);
  });

  it("drops audio that arrives after an interrupt until the next reply starts", async () => {
    const { result, onAudioChunk } = await renderSpeakingSession();

    act(() => {
      latestSocket().serverBinary();
    });
    expect(onAudioChunk).toHaveBeenCalledTimes(1);

    act(() => {
      result.current.sendInterrupt(1200);
    });
    expect(
      latestSocket()
        .sentJson()
        .some((m) => m.type === "turn.interrupt"),
    ).toBe(true);

    // Streamed ahead; the user cut the reply off.
    act(() => {
      latestSocket().serverBinary();
      latestSocket().serverBinary();
      latestSocket().serverBinary();
    });
    expect(onAudioChunk).toHaveBeenCalledTimes(1);

    // The reply to the barge-in plays.
    act(() => {
      latestSocket().serverJson({ type: "state", value: "thinking" });
      latestSocket().serverJson({ type: "state", value: "speaking" });
      latestSocket().serverBinary();
    });
    expect(onAudioChunk).toHaveBeenCalledTimes(2);
  });
});

describe("useSessionSocket after the server refuses the call", () => {
  // ADR 0109: refused before any Session exists; the end-call button must still leave.
  async function renderRefusedSession() {
    const onEnded = vi.fn();
    const view = renderHook(() =>
      useSessionSocket({ session: SESSION, onAudioChunk: vi.fn(), onEnded }),
    );
    await act(async () => {
      latestSocket().simulateOpen();
    });
    act(() => {
      latestSocket().serverJson({
        type: "error",
        code: "too_many_calls",
        message: "Sie führen bereits zu viele Gespräche gleichzeitig.",
      });
      latestSocket().close();
    });
    return { ...view, onEnded };
  }

  it("shows the server's reason", async () => {
    const { result } = await renderRefusedSession();
    expect(result.current.error).toBe("Sie führen bereits zu viele Gespräche gleichzeitig.");
  });

  it("ends locally when the user hangs up, with no Session to wait for", async () => {
    const { result, onEnded } = await renderRefusedSession();
    act(() => {
      result.current.endSession();
    });
    expect(onEnded).toHaveBeenCalledWith("user", [], null);
  });

  it("does not end locally a call that had started and then lost its socket", async () => {
    // That one is stored as aborted; inventing an ending would show a wrap-up that does not exist.
    const { result, onEnded } = await renderSpeakingSession();
    act(() => {
      latestSocket().close();
      result.current.endSession();
    });
    expect(onEnded).not.toHaveBeenCalled();
  });
});
