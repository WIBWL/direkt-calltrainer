import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { latestSocket } from "../test/setup";
import { useSessionSocket, type CommittedSession } from "./useSessionSocket";

vi.mock("../auth", () => ({
  currentAccessToken: () => Promise.resolve("test-token"),
}));

const SESSION: CommittedSession = { personaId: "p1", scenarioId: "s1", reverse: false };

/** Render the hook and take the socket through open + handshake + the server
 * announcing it has started speaking, so a binary frame next is "live" audio. */
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

    // The user talks over the persona.
    act(() => {
      result.current.sendInterrupt(1200);
    });
    expect(
      latestSocket()
        .sentJson()
        .some((m) => m.type === "turn.interrupt"),
    ).toBe(true);

    // Everything the server streamed ahead keeps arriving — none of it is
    // still wanted, the user cut the reply off.
    act(() => {
      latestSocket().serverBinary();
      latestSocket().serverBinary();
      latestSocket().serverBinary();
    });
    expect(onAudioChunk).toHaveBeenCalledTimes(1);

    // The reply to the barge-in begins: server goes thinking -> speaking, then
    // sends its audio. That audio plays.
    act(() => {
      latestSocket().serverJson({ type: "state", value: "thinking" });
      latestSocket().serverJson({ type: "state", value: "speaking" });
      latestSocket().serverBinary();
    });
    expect(onAudioChunk).toHaveBeenCalledTimes(2);
  });
});

describe("useSessionSocket after the server refuses the call", () => {
  // ADR 0109: a caller over the open-call cap (or without the role) is told
  // why in an `error` frame and the socket is closed before any Session
  // exists. The end-call button must still leave the call screen.
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
    // That one has a Session on the server, stored as aborted; inventing an
    // ending here would send the screen to a wrap-up of a call that has none.
    const { result, onEnded } = await renderSpeakingSession();
    act(() => {
      latestSocket().close();
      result.current.endSession();
    });
    expect(onEnded).not.toHaveBeenCalled();
  });
});
