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

    // Three chunks the server streamed ahead of playback arrive over the
    // socket; the first is mid-decode, the other two are queued behind it.
    await act(async () => {
      result.current.enqueue(chunk());
      result.current.enqueue(chunk());
      result.current.enqueue(chunk());
    });
    expect(FakeAudioContext.pendingDecodes).toHaveLength(1);

    // The user talks over the persona before any of those chunks played.
    act(() => {
      result.current.interrupt();
    });

    // Their decodes now resolve (the audio came back from the gateway) — none
    // of them may reach the speakers: the user already cut the reply off.
    await act(async () => {
      await flushDecodes();
    });

    expect(audibleSources()).toHaveLength(0);
  });

  it("silences audio the server already streamed ahead and scheduled", async () => {
    const { result } = renderHook(() => useStreamedAudioPlayback());
    act(() => result.current.activate());

    // The server streamed a long reply ahead of playback: five chunks that are
    // fully decoded and scheduled back-to-back into the future.
    await act(async () => {
      for (let i = 0; i < 5; i++) result.current.enqueue(chunk());
    });
    await act(async () => {
      await flushDecodes();
    });
    // Only the first is playing; the rest sit scheduled ahead.
    expect(audibleSources().length).toBeGreaterThan(0);

    act(() => {
      result.current.interrupt();
    });

    // Nothing may still be routed to the speakers, and the master gain is cut
    // as a backstop for engines that ignore stop() on a pending source.
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

    // The reply to the barge-in arrives.
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
