import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ReverseBrief } from "../scenarioLibrary";
import { loadFinishedSession, saveFinishedSession } from "../utils/finishedSession";
import { useTrainingRun } from "./useTrainingRun";

/**
 * The training run's rules, which lived as comments beside five handlers in
 * `App.tsx` ("after `beginSession`, which clears it"). The detail route is the
 * one thing faked: what is under test is which Session asks it what, and what
 * survives a commit, an end and a reload.
 */

const fake = vi.hoisted(() => ({ getScenario: vi.fn() }));
vi.mock("../scenarioLibrary", () => ({ getScenario: fake.getScenario }));

const brief = { goals: ["Den Termin festhalten"] } as unknown as ReverseBrief;

beforeEach(() => {
  fake.getScenario.mockReset();
  saveFinishedSession(null);
});

describe("useTrainingRun", () => {
  it("fetches the case of an ordinary call once it is committed", async () => {
    fake.getScenario.mockResolvedValue({ briefing: "Sie sind im Support.", case_facts: "Zähler 4711" });
    const { result } = renderHook(() => useTrainingRun());

    act(() => result.current.commit("s1", "p1"));

    await waitFor(() =>
      expect(result.current.committedCase).toEqual({
        briefing: "Sie sind im Support.",
        facts: "Zähler 4711",
      }),
    );
    expect(fake.getScenario).toHaveBeenCalledWith("s1");
    expect(result.current.secretScenario).toBeNull();
  });

  it("never fetches the case of a drawn Scenario, and keeps its name secret", () => {
    const { result } = renderHook(() => useTrainingRun());

    act(() => result.current.commit("s1", "p1", { drawnName: "Störung im Betrieb" }));

    expect(result.current.secretScenario).toBe("Störung im Betrieb");
    expect(fake.getScenario).not.toHaveBeenCalled();
  });

  it("forgets that a Scenario was drawn on the next commit that does not say so", () => {
    const { result } = renderHook(() => useTrainingRun());

    act(() => result.current.commit("s1", "p1", { drawnName: "Störung im Betrieb" }));
    fake.getScenario.mockResolvedValue({ briefing: "", case_facts: "" });
    act(() => result.current.commit("s2", "p1"));

    expect(result.current.secretScenario).toBeNull();
  });

  it("keeps a seeded briefing when the refetch fails", async () => {
    fake.getScenario.mockRejectedValue(new Error("offline"));
    const { result } = renderHook(() => useTrainingRun());

    act(() => result.current.commit("r1", "p1", { reverse: true, brief }));

    await waitFor(() => expect(fake.getScenario).toHaveBeenCalled());
    expect(result.current.reverseBrief).toBe(brief);
  });

  it("forgets the previous wrap-up once a new call is committed", () => {
    saveFinishedSession({ sessionId: "old", turns: [], personaName: "Thomas Brandt" });
    fake.getScenario.mockResolvedValue({ briefing: "", case_facts: "" });
    const { result } = renderHook(() => useTrainingRun());

    act(() => result.current.commit("s1", "p1"));

    expect(loadFinishedSession()).toBeNull();
  });

  it("remembers the finished call and the pairing it was, and lets go of the Session", () => {
    fake.getScenario.mockResolvedValue({ briefing: "", case_facts: "" });
    const { result } = renderHook(() => useTrainingRun());
    act(() => result.current.commit("s1", "p1"));

    const turns = [{ speaker: "user" as const, text: "Hallo", offset_ms: 0 }];
    act(() =>
      result.current.finish(
        { reason: "completed", turns, sessionId: "e1" },
        { personaName: "Thomas Brandt", scenarioName: "Störung", personaId: "p1" },
      ),
    );

    expect(result.current.committed).toBeNull();
    expect(result.current.lastPlayed).toEqual({ scenarioId: "s1", personaId: "p1" });
    expect(result.current.endedSessionId).toBe("e1");
    expect(loadFinishedSession()?.sessionId).toBe("e1");
  });

  it("comes back on the finished call after a reload", () => {
    saveFinishedSession({ sessionId: "e1", turns: [], personaName: "Thomas Brandt" });
    const { result } = renderHook(() => useTrainingRun());

    expect(result.current.restored?.sessionId).toBe("e1");
    expect(result.current.endedSessionId).toBe("e1");
  });
});
