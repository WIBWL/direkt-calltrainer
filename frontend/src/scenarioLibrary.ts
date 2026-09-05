/**
 * The Scenario library REST surface (backend/api/scenarios.py, ADR 0058).
 *
 * `listScenarios` feeds the selection screen; the rest is the authoring flow.
 * A Scenario is addressed by its `id` (the backend's unguessable extern_id,
 * ADR 0050). Wire field names are English, matching the schema (ADR 0057,
 * extended to this surface by ADR 0061); the card field `name` is the one that
 * differs from its column (`title`).
 */
import { apiFetch, ApiError, reauthenticate } from "./api";
import { currentAccessToken } from "./auth";

/** builtin = shipped built-in, own = the caller authored it (ADR 0058),
 * tenant = a colleague shared it with the caller's company (ADR 0060). */
export type Origin = "builtin" | "own" | "tenant";

export type Visibility = "private" | "tenant";

export interface ScenarioCard {
  id: string;
  name: string;
  short_description: string;
  origin: Origin;
  /** True once shared with the company — also for the caller's own Scenarios,
   * which `origin` still reports as "own". */
  shared: boolean;
}

/** The fields a User may author. `name` / `short_description` are the card;
 * the rest is prompt input and may be left empty (ADR 0045). */
export interface ScenarioDraft {
  name: string;
  short_description: string;
  scenario_type: string;
  description: string;
  case_facts: string;
  call_goal: string;
  success_condition: string;
}

export interface ScenarioDetail extends ScenarioDraft {
  id: string;
  visibility: Visibility;
}

/** Mirrors backend/authored_text.py FIELD_LIMITS, so the field is rejected
 * client-side before a round trip rather than coming back a 422. */
export const FIELD_LIMITS: Record<keyof ScenarioDraft, number> = {
  name: 160,
  short_description: 240,
  scenario_type: 60,
  description: 2000,
  case_facts: 2000,
  call_goal: 2000,
  success_condition: 2000,
};

export const EMPTY_DRAFT: ScenarioDraft = {
  name: "",
  short_description: "",
  scenario_type: "",
  description: "",
  case_facts: "",
  call_goal: "",
  success_condition: "",
};

/** The caller's tenant (ADR 0060), or `{name: null}` for the default tenant.
 * Drives the "<Unternehmen>" filter chip and badge in the Scenario library. */
export const getTenant = () =>
  apiFetch<{ name: string | null }>("/api/tenant");

export const listScenarios = () => apiFetch<ScenarioCard[]>("/api/scenarios");

export const getScenario = (id: string) =>
  apiFetch<ScenarioDetail>(`/api/scenarios/${id}`);

export const createScenario = (draft: ScenarioDraft) =>
  apiFetch<ScenarioDetail>("/api/scenarios", {
    method: "POST",
    body: JSON.stringify(draft),
  });

export const updateScenario = (id: string, draft: ScenarioDraft) =>
  apiFetch<ScenarioDetail>(`/api/scenarios/${id}`, {
    method: "PATCH",
    body: JSON.stringify(draft),
  });

export const deleteScenario = (id: string) =>
  apiFetch<null>(`/api/scenarios/${id}`, { method: "DELETE" });

/** Share the Scenario with the caller's company, or make it private again
 * (R-58). Only the author may. */
export const setScenarioVisibility = (id: string, visibility: Visibility) =>
  apiFetch<ScenarioDetail>(`/api/scenarios/${id}/visibility`, {
    method: "PUT",
    body: JSON.stringify({ visibility }),
  });

export interface DocumentText {
  /** The LLM's fact list, or (when `summarised` is false) the raw text. */
  text: string;
  pages: number;
  /** True: the LLM condensed the document. False: the LLM was unreachable and
   * this is the raw extracted text, truncated. */
  summarised: boolean;
}

/** Extract a text-layer PDF and have the LLM condense it into a fact list, for
 * the Fakten field (F-58). Multipart, so it does not go through apiFetch. */
export async function extractPdf(file: File): Promise<DocumentText> {
  const token = await currentAccessToken();
  if (!token) {
    void reauthenticate();
    throw new ApiError(401, "no active session");
  }
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/api/scenarios/document", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (response.status === 401) {
    void reauthenticate();
    throw new ApiError(401, "session invalid — re-authenticating");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => undefined)) as { detail?: unknown } | undefined;
    throw new ApiError(response.status, typeof body?.detail === "string" ? body.detail : undefined);
  }
  return (await response.json()) as DocumentText;
}
