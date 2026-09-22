import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { endIsDue, useLiveCall, type EndedCall } from "./useLiveCall";
import type { CommittedSession } from "./useSessionSocket";
import type { TranscriptEntry } from "../protocol";

/**
 * The three rules that bind the connection to its audio, which used to be
 * held by comments beside three effects in `App.tsx`.
 *
 * The socket and the playback are replaced by plain fakes: their own specs
 * cover the WebSocket and the Web Audio graph, and what is under test here is
 * only what this hook asks of them, and when.
 */

type OnEnded = (
  reason: EndedCall["reason"],
  turns: TranscriptEntry[],
  sessionId: string | null,
) => void;

const fake = vi.hoisted(() => ({
  playback: {
    enqueue: vi.fn(),
    activate: vi.fn(),
    reset: vi.fn(),
    interrupt: vi.fn(() => 0),
    isPlaying: false,
    audioLevel: 0,
  },
  socket: {
    callState: "listening" as const,
    error: null,
    sendTurnAudio: vi.fn(),
    sendInterrupt: vi.fn(),
    sendActivate: vi.fn(),
    endSession: vi.fn(),
  },
  onEnded: null as OnEnded | null,
}));

vi.mock("./useStreamedAudioPlayback", () => ({
  useStreamedAudioPlayback: () => fake.playback,
}));
vi.mock("./useSessionSocket", () => ({
  useSessionSocket: ({ onEnded }: { onEnded: OnEnded }) => {
    fake.onEnded = onEnded;
    return fake.socket;
  },
}));

const session = (): CommittedSession => ({ personaId: "p", scenarioId: "s", reverse: false });

function render(committed: CommittedSession | null = session()) {
  const onCallOver = vi.fn<(ended: EndedCall) => void>();
  const hook = renderHook(({ c }: { c: CommittedSession | null }) => useLiveCall(c, onCallOver), {
    initialProps: { c: committed },
  });
  return { ...hook, onCallOver };
}

function serverEnds(reason: EndedCall["reason"], sessionId: string | null = "sid") {
  act(() => fake.onEnded?.(reason, [], sessionId));
}

beforeEach(() => {
  vi.clearAllMocks();
  fake.playback.isPlaying = false;
});

describe("when an ended call is torn down", () => {
  const end = (reason: EndedCall["reason"]): EndedCall => ({ reason, turns: [], sessionId: null });

  it("waits for the Persona's goodbye to finish playing", () => {
    expect(endIsDue(end("completed"), true)).toBe(false);
    expect(endIsDue(end("error"), true)).toBe(false);
  });

  it("goes once the audio has stopped", () => {
    expect(endIsDue(end("completed"), false)).toBe(true);
  });

  it("does not wait when the User hung up", () => {
    expect(endIsDue(end("user"), true)).toBe(true);
  });

  it("hands a natural ending over only after the goodbye was heard", () => {
    fake.playback.isPlaying = true;
    const committed = session();
    const { rerender, onCallOver } = render(committed);
    serverEnds("completed");
    expect(onCallOver).not.toHaveBeenCalled();

    fake.playback.isPlaying = false;
    rerender({ c: committed });

    expect(onCallOver).toHaveBeenCalledTimes(1);
    expect(onCallOver).toHaveBeenCalledWith(
      expect.objectContaining({ reason: "completed", sessionId: "sid" }),
    );
  });

  it("hands the call over once, however often it renders afterwards", () => {
    const committed = session();
    const { rerender, onCallOver } = render(committed);
    serverEnds("user");
    rerender({ c: committed });
    rerender({ c: committed });

    expect(onCallOver).toHaveBeenCalledTimes(1);
  });
});

describe("the buffered opening line (ADR 0042)", () => {
  it("is dropped whenever a new Session is committed to", () => {
    const { rerender } = render();
    fake.playback.reset.mockClear();

    // A new object is a new Session, even for the same pairing.
    rerender({ c: session() });

    expect(fake.playback.reset).toHaveBeenCalledTimes(1);
  });

  it("is kept while the same Session renders again", () => {
    const committed = session();
    const { rerender } = render(committed);
    fake.playback.reset.mockClear();

    rerender({ c: committed });

    expect(fake.playback.reset).not.toHaveBeenCalled();
  });

  it("is revealed together with the server's clock starting", () => {
    // One without the other either plays a line the server has not timed, or
    // leaves the server holding a line nobody hears.
    const { result } = render();
    result.current.accept();

    expect(fake.playback.activate).toHaveBeenCalledTimes(1);
    expect(fake.socket.sendActivate).toHaveBeenCalledTimes(1);
  });
});
