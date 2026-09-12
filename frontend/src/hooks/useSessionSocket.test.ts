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
