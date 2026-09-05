/**
 * The Scenario library REST surface (backend/api/scenarios.py, ADR 0058).
 *
 * `listScenarios` feeds the selection screen; the rest is the authoring flow.
 * A Scenario is addressed by its `id` (the backend's unguessable extern_id,
 * ADR 0050). Wire field names are German, matching the backend.
 */
import { apiFetch, ApiError, reauthenticate } from "./api";
import { currentAccessToken } from "./auth";

/** vorlage = shipped built-in, eigen = the caller authored it (ADR 0058),
 * unternehmen = a colleague shared it with the caller's company (ADR 0060). */
export type Herkunft = "vorlage" | "eigen" | "unternehmen";

export type Sichtbarkeit = "privat" | "unternehmen";

export interface ScenarioCard {
  id: string;
  name: string;
  short_description: string;
  herkunft: Herkunft;
  /** True once shared with the company — also for the caller's own Scenarios,
   * which `herkunft` still reports as "eigen". */
  geteilt: boolean;
}

/** The fields a User may author. `name` / `kurzbeschreibung` are the card;
 * the rest is prompt input and may be left empty (ADR 0045). */
export interface ScenarioDraft {
  name: string;
  kurzbeschreibung: string;
  szenariotyp: string;
  beschreibung: string;
  fallfakten: string;
  anrufziel: string;
  erfolgsbedingung: string;
}

export interface ScenarioDetail extends ScenarioDraft {
  id: string;
  sichtbarkeit: Sichtbarkeit;
}

/** Mirrors backend/authored_text.py FIELD_LIMITS, so the field is rejected
 * client-side before a round trip rather than coming back a 422. */
export const FIELD_LIMITS: Record<keyof ScenarioDraft, number> = {
  name: 160,
  kurzbeschreibung: 240,
  szenariotyp: 60,
  beschreibung: 2000,
  fallfakten: 2000,
  anrufziel: 2000,
  erfolgsbedingung: 2000,
};

export const EMPTY_DRAFT: ScenarioDraft = {
  name: "",
  kurzbeschreibung: "",
  szenariotyp: "",
  beschreibung: "",
  fallfakten: "",
  anrufziel: "",
  erfolgsbedingung: "",
};

/** The caller's company (ADR 0060), or `{name: null}` for the default tenant.
 * Drives the "<Unternehmen>" filter chip and badge in the Scenario library. */
export const getUnternehmen = () =>
  apiFetch<{ name: string | null }>("/api/unternehmen");

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
export const setScenarioVisibility = (id: string, sichtbarkeit: Sichtbarkeit) =>
  apiFetch<ScenarioDetail>(`/api/scenarios/${id}/sichtbarkeit`, {
    method: "PUT",
    body: JSON.stringify({ sichtbarkeit }),
  });

export interface DocumentText {
  /** The LLM's fact list, or (when `zusammengefasst` is false) the raw text. */
  text: string;
  seiten: number;
  /** True: the LLM condensed the document. False: the LLM was unreachable and
   * this is the raw extracted text, truncated. */
  zusammengefasst: boolean;
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
  form.append("datei", file);
  const response = await fetch("/api/scenarios/dokument", {
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
