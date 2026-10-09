/** Scenario library API (ADR 0058). `id` is the extern_id (ADR 0050); the card's `name` is column `title`. */
import { apiFetch } from "./api";
import type { FollowUpCard } from "./protocol";

/** builtin, own (ADR 0058), or shared by a colleague (ADR 0060). */
export type Origin = "builtin" | "own" | "tenant";

export type Visibility = "private" | "tenant";

/** ADR 0072; the German labels below are display only. */
export type ScenarioCategory = "operations" | "requirements" | "pricing" | "closing";

/** "" = no category: listed only under the unfiltered row. */
export type CategoryChoice = ScenarioCategory | "";

/** Read by the filter and the editor; a new category also needs the backend's SCENARIO_CATEGORIES. */
export const CATEGORY_LABELS: Record<ScenarioCategory, string> = {
  operations: "Betrieb & Störung",
  requirements: "Beratung & Anforderung",
  pricing: "Preis & Kondition",
  closing: "Abschluss & Einwand",
};

export const CATEGORIES = Object.keys(CATEGORY_LABELS) as ScenarioCategory[];

/** The call a reverse replays (ADR 0070); null once that Session is deleted. */
export interface OriginSessionRef {
  id: string;
  persona: string;
  started_at: string;
}

/** What the User reads while playing a reverse (ADR 0070). */
export interface ReverseBrief {
  situation: string;
  facts: string;
  /** What the caller wants and the bar that settles it. */
  goal: string;
  goals: string[];
}

/** F-62: the call type and the focus goals it exercises. */
export interface ScenarioRecommendation {
  call_type: boolean;
  goals: string[];
}

export interface ScenarioCard {
  id: string;
  name: string;
  short_description: string;
  /** The trainee's own briefing (ADR 0054), never sent to the model. */
  briefing: string;
  description: string;
  /** null = uncategorised. */
  category: ScenarioCategory | null;
  origin: Origin;
  /** Also true for the caller's own, which `origin` still reports as "own". */
  shared: boolean;
  /** F-60 (ADR 0069): `origin` "own", but neither edited nor shared. */
  follow_up: boolean;
  /** F-61 (ADR 0070): likewise neither edited nor shared. */
  reverse: boolean;
  origin_session: OriginSessionRef | null;
  recommendation: ScenarioRecommendation | null;
}

/** Draw one and do not say which (F-66); cannot collide with a UUID. */
export const RANDOM_SCENARIO_ID = "__random__";

/** Reverses and follow-ups do not survive being walked into unprepared. */
export function isDrawable(scenario: ScenarioCard): boolean {
  return !scenario.reverse && !scenario.follow_up;
}

/** `isDrawable` again rather than trusting the caller's on-screen filtering. */
export function drawRandomScenario(pool: ScenarioCard[]): ScenarioCard | null {
  const drawable = pool.filter(isDrawable);
  return drawable[Math.floor(Math.random() * drawable.length)] ?? null;
}

/** Level 1 of the filter, in chip order (ADR 0072). "own" means hand-authored only. */
export const LIBRARY_FILTERS = [
  "recommended",
  "all",
  "standard",
  "own",
  "tenant",
  "followUp",
  "reverse",
] as const;

export type LibraryFilter = (typeof LIBRARY_FILTERS)[number];

export type CategoryFilter = "all" | ScenarioCategory;

export const CATEGORY_FILTERS: CategoryFilter[] = ["all", ...CATEGORIES];

export const CATEGORY_FILTER_LABELS: Record<CategoryFilter, string> = {
  all: "Alle",
  ...CATEGORY_LABELS,
};

/** The grid, the chip counts and the random pool all ask this one function. */
export function matchesFilter(card: ScenarioCard, filter: LibraryFilter): boolean {
  if (filter === "recommended") return card.recommendation !== null;
  if (filter === "all") return true;
  if (filter === "standard") return card.origin === "builtin";
  if (filter === "followUp") return card.follow_up;
  if (filter === "reverse") return card.reverse;
  if (filter === "own") return card.origin === "own" && !card.follow_up && !card.reverse;
  return card.shared;
}

/** Uncategorised matches only "all" (ADR 0072). */
export function matchesCategory(card: ScenarioCard, category: CategoryFilter): boolean {
  return category === "all" || card.category === category;
}

export function recommendationReason(
  recommendation: ScenarioRecommendation,
  goalTitle: (key: string) => string,
): string {
  const parts: string[] = [];
  if (recommendation.call_type) parts.push("Passt zu Ihren Gesprächen");
  if (recommendation.goals.length > 0) {
    parts.push("Übt " + recommendation.goals.map((g) => `„${goalTitle(g)}“`).join(", "));
  }
  return parts.join(" · ");
}

/** `briefing` is the trainee's (ADR 0054); the prompt fields may be empty (ADR 0045). */
export interface ScenarioDraft {
  name: string;
  short_description: string;
  briefing: string;
  description: string;
  case_facts: string;
  call_goal: string;
  /** Validated against the CHECK constraint's list (ADR 0072). */
  category: CategoryChoice;
}

export type TextField = Exclude<keyof ScenarioDraft, "category">;

/** The read view (ADR 0062), and the editor's row where `editable`. */
export interface ScenarioDetail {
  id: string;
  name: string;
  short_description: string;
  briefing: string;
  description: string;
  /** null = withheld for a built-in (ADR 0054). */
  case_facts: string | null;
  /** null = withheld for a built-in: the answer key (ADR 0062). */
  call_goal: string | null;
  category: CategoryChoice;
  visibility: Visibility | "public";
  /** From the verified token; false on reverses and follow-ups (ADR 0069, 0070). */
  editable: boolean;
  reverse: boolean;
  follow_up: boolean;
  origin_session: OriginSessionRef | null;
  reverse_brief: ReverseBrief | null;
}

/** Only called on an `editable` row, where nothing is withheld. */
export function toDraft(detail: ScenarioDetail): ScenarioDraft {
  return {
    name: detail.name,
    short_description: detail.short_description,
    briefing: detail.briefing,
    description: detail.description,
    case_facts: detail.case_facts ?? "",
    call_goal: detail.call_goal ?? "",
    category: detail.category,
  };
}

export type FieldLimits = Record<TextField, number>;

/** Until `getFieldLimits()` answers. Must match `backend/authored_text.py` (pinned by test_authored_text.py). */
export const FALLBACK_FIELD_LIMITS: FieldLimits = {
  name: 50,
  short_description: 100,
  briefing: 500,
  description: 500,
  case_facts: 2500,
  call_goal: 500,
};

export const getFieldLimits = () =>
  apiFetch<FieldLimits>("/api/scenarios/field-limits");

export const EMPTY_DRAFT: ScenarioDraft = {
  name: "",
  short_description: "",
  briefing: "",
  description: "",
  case_facts: "",
  call_goal: "",
  category: "",
};

/** ADR 0060; `{name: null}` for the default tenant. */
export const getTenant = () =>
  apiFetch<{ name: string | null }>("/api/tenant");

export const listScenarios = () => apiFetch<ScenarioCard[]>("/api/scenarios");

/** F-64: the same Scenario in the other language, or another from the library. */
export interface NextCallOffer {
  kind: "language" | "library";
  scenario_id: string;
  scenario_name: string;
  persona_id: string;
  persona_name: string;
  language: string;
  recommendation: ScenarioRecommendation | null;
  unplayed: boolean;
}

export const getNextCalls = (scenarioId: string, personaId: string) =>
  apiFetch<NextCallOffer[]>(
    `/api/scenarios/${encodeURIComponent(scenarioId)}/next` +
      `?persona=${encodeURIComponent(personaId)}`,
  );

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

/** R-58; author only. */
export const setScenarioVisibility = (id: string, visibility: Visibility) =>
  apiFetch<ScenarioDetail>(`/api/scenarios/${id}/visibility`, {
    method: "PUT",
    body: JSON.stringify({ visibility }),
  });

export interface ReverseScenario {
  id: string;
  name: string;
  short_description: string;
  reverse_brief: ReverseBrief | null;
}

/** Idempotent (F-61, ADR 0070). 409 = nothing to swap, 503 = model unreachable. */
export const createReverse = (sessionId: string) =>
  apiFetch<ReverseScenario>(`/api/sessions/${sessionId}/reverse`, { method: "POST" });

/** Idempotent (F-60, ADR 0069). 409 = nothing to build from, 503 = model unreachable. */
export const createFollowUp = (sessionId: string) =>
  apiFetch<FollowUpCard>(`/api/sessions/${sessionId}/follow-up`, { method: "POST" });

export interface DocumentText {
  /** The fact list, or the raw text when `summarised` is false. */
  text: string;
  pages: number;
  documents: { name: string; pages: number }[];
  summarised: boolean;
}

/** A courtesy check mirrored from `backend/documents.py`; the server enforces the real one. */
export const MAX_DOCUMENT_MB = 5;
export const MAX_DOCUMENTS_TOTAL_MB = 20;

/** Condenses the PDFs together into one fact list (F-58). */
export function extractPdfs(files: File[]): Promise<DocumentText> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  return apiFetch<DocumentText>("/api/scenarios/document", { method: "POST", body: form });
}
