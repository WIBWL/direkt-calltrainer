import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { audibleSources, FakeAudioContext, flushDecodes, masterMuted } from "../test/setup";
import { useStreamedAudioPlayback } from "./useStreamedAudioPlayback";

const chunk = () => new ArrayBuffer(8);

describe("useStreamedAudioPlayback barge-in", () => {
  it("plays chunks that arrive while live", async () => {
    const { result } = renderHook(() => useStreamedAudioPlayback());

    act(() => result.current.activate());
    await act(async () => {
      result.current.enqueue(chunk());
      result.current.enqueue(chunk());
    });
    await act(async () => {
      await flushDecodes();
    });

    expect(audibleSources()).toHaveLength(2);
  });

  it("does not play the persona's remaining audio after an interrupt", async () => {
    const { result } = renderHook(() => useStreamedAudioPlayback());
    act(() => result.current.activate());

    // Three chunks streamed ahead: one decoding, two queued.
    await act(async () => {
      result.current.enqueue(chunk());
      result.current.enqueue(chunk());
      result.current.enqueue(chunk());
    });
    expect(FakeAudioContext.pendingDecodes).toHaveLength(1);

    // Barge-in before any played.
    act(() => {
      result.current.interrupt();
    });

    // None of the late decodes may reach the speakers.
    await act(async () => {
      await flushDecodes();
    });

    expect(audibleSources()).toHaveLength(0);
  });

  it("silences audio the server already streamed ahead and scheduled", async () => {
    const { result } = renderHook(() => useStreamedAudioPlayback());
    act(() => result.current.activate());

    // Five chunks decoded and scheduled into the future.
    await act(async () => {
      for (let i = 0; i < 5; i++) result.current.enqueue(chunk());
    });
    await act(async () => {
      await flushDecodes();
    });
    expect(audibleSources().length).toBeGreaterThan(0);

    act(() => {
      result.current.interrupt();
    });

    // The master gain is a backstop for engines that ignore stop().
    expect(audibleSources()).toHaveLength(0);
    expect(masterMuted()).toBe(true);
  });

  it("lifts the barge-in mute once the next reply's audio arrives", async () => {
    const { result } = renderHook(() => useStreamedAudioPlayback());
    act(() => result.current.activate());

    await act(async () => {
      result.current.enqueue(chunk());
    });
    act(() => {
      result.current.interrupt();
    });
    expect(masterMuted()).toBe(true);

    await act(async () => {
      result.current.enqueue(chunk());
    });
    await act(async () => {
      await flushDecodes();
    });
    expect(masterMuted()).toBe(false);
  });

  it("plays the next turn's chunks normally after an interrupt", async () => {
    const { result } = renderHook(() => useStreamedAudioPlayback());
    act(() => result.current.activate());

    await act(async () => {
      result.current.enqueue(chunk());
    });
    act(() => {
      result.current.interrupt();
    });
    await act(async () => {
      await flushDecodes();
    });

    await act(async () => {
      result.current.enqueue(chunk());
      result.current.enqueue(chunk());
    });
    await act(async () => {
      await flushDecodes();
    });

    expect(audibleSources()).toHaveLength(2);
  });
});
