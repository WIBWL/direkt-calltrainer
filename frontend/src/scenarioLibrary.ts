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
import type { SessionDetail } from "./protocol";

/** builtin = shipped built-in, own = the caller authored it (ADR 0058),
 * tenant = a colleague shared it with the caller's company (ADR 0060). */
export type Origin = "builtin" | "own" | "tenant";

export type Visibility = "private" | "tenant";

/** What kind of call a Scenario is (ADR 0072). The wire carries the English
 * key; the German labels below are display only. */
export type ScenarioCategory = "operations" | "requirements" | "pricing" | "closing";

/** "" = no category. Only reachable for a Scenario authored before the column
 * existed, or one whose author left the field empty; such a row is listed under
 * "Alle" and under no category. */
export type CategoryChoice = ScenarioCategory | "";

/** Display order and labels, in one place: the filter slider and the editor's
 * select both read this, so a further category is one entry here plus one value
 * in the backend's SCENARIO_CATEGORIES. The labels name the occasion of the
 * call rather than a department, because that is what a user picking a training
 * case is choosing between. */
export const CATEGORY_LABELS: Record<ScenarioCategory, string> = {
  operations: "Betrieb & Störung",
  requirements: "Beratung & Anforderung",
  pricing: "Preis & Kondition",
  closing: "Abschluss & Einwand",
};

export const CATEGORIES = Object.keys(CATEGORY_LABELS) as ScenarioCategory[];

/** The conversation a reverse replays (ADR 0070). Null on the card once that
 * Session has been deleted — the reverse outlives it. */
export interface OriginSessionRef {
  id: string;
  persona: string;
  /** ISO 8601, as every timestamp on this wire is. */
  started_at: string;
}

/** What the User reads while playing a reverse: the briefing the Persona had
 * for the original call, in German, plus the checklist of what this call has to
 * cover (ADR 0070). Generated once when the reverse is created and stored
 * with it.
 *
 * `goal` and `goals` are two different things and both are wanted: the first is
 * the one sentence on what the caller is after, the second the concrete points
 * to raise, ask and come away with. */
export interface ReverseBrief {
  situation: string;
  facts: string;
  /** What the caller wants *and* the bar that settles it, in one field since
   * the two were merged — the same merge the Scenario's own `call_goal` got. */
  goal: string;
  goals: string[];
  /** The bar, back when it was a field of its own. Read only, and appended to
   * `goal` when a stored briefing still carries it; nothing writes it, and it
   * can go once no stored reverse predates the merge. Same arrangement as
   * `watch_points` below, for the same reason: a stored briefing is the only
   * copy of a case that was played, and dropping half of it silently would be
   * the worse of the two options. */
  settled?: string;
  /** What `goals` was called before it became a list of objectives rather than
   * of things to watch out for. Read only so a briefing written before that
   * still shows its list; nothing writes it, and it can go once no stored
   * reverse predates the change. */
  watch_points?: string[];
}

export interface ScenarioCard {
  id: string;
  name: string;
  short_description: string;
  /** The trainee's own briefing (ADR 0054): the role they answer in, the room
   * they have, what a good outcome is. Shown before the call, never sent to the
   * model. "" for a Scenario whose author left it empty. */
  briefing: string;
  /** null = uncategorised (ADR 0072). */
  category: ScenarioCategory | null;
  origin: Origin;
  /** True once shared with the company — also for the caller's own Scenarios,
   * which `origin` still reports as "own". */
  shared: boolean;
  /** Drafted from one of the caller's Sessions (F-60, ADR 0069). Its own
   * category in the picker; `origin` stays "own", so it is edited and shared
   * like anything else they own. */
  follow_up: boolean;
  /** A reverse of one finished Session (F-61, ADR 0070). Also `origin: "own"`,
   * and also its own category — but unlike a follow-up it is neither edited
   * nor shared, because it copies a case that was actually played. */
  reverse: boolean;
  origin_session: OriginSessionRef | null;
}

/** The pick that is not a Scenario: draw one, and do not say which (F-62).
 *
 * A sentinel id rather than a flag beside the selection, so the screen still
 * has exactly one selected value and the summary, the start button and the
 * picker's own pressed state each need no second case. It cannot collide with
 * a real Scenario: those ids are the backend's UUIDs (ADR 0050). */
export const RANDOM_SCENARIO_ID = "__random__";

/** One of the Scenarios the User could have picked by hand, drawn at the moment
 * the call is committed to.
 *
 * A reverse and a follow-up are left out because neither survives being walked
 * into unprepared: a reverse is played *from* a briefing the User is meant to
 * read first (ADR 0070), and a follow-up continues a call they are meant to
 * remember (ADR 0069). Everything else is in — built-in, own and shared alike.
 *
 * This is only half the pool: the caller narrows it to what the two filter
 * rows currently show before handing it over (see `App.tsx`). The draw once
 * ignored them both, on the argument that picking a category has already said
 * what is coming — but that read the surprise as the whole of the feature. It
 * is also the way into a case the User did not choose, and staying inside the
 * filter keeps that offer honest: nothing is drawn that the chips on screen
 * exclude. */
export function isDrawable(scenario: ScenarioCard): boolean {
  return !scenario.reverse && !scenario.follow_up;
}

/** One of `pool`, drawn uniformly. `isDrawable` is applied again here rather
 * than trusted: the caller's filtering is about what is on screen, this is
 * about what may be walked into blind, and the second is not the first's to
 * get right. */
export function drawRandomScenario(pool: ScenarioCard[]): ScenarioCard | null {
  const drawable = pool.filter(isDrawable);
  return drawable[Math.floor(Math.random() * drawable.length)] ?? null;
}

/** The fields a User may author. `name` / `short_description` are the card and
 * `briefing` the trainee's own text (ADR 0054); the rest is prompt input and may
 * be left empty (ADR 0045). */
export interface ScenarioDraft {
  name: string;
  short_description: string;
  briefing: string;
  description: string;
  case_facts: string;
  call_goal: string;
  /** A closed vocabulary, not free text. The backend validates it against the
   * same list the CHECK constraint holds (ADR 0072). "" is a valid choice. */
  category: CategoryChoice;
}

/** The draft fields that are text and therefore length-capped. `category` is a
 * choice from a fixed list, so it has no limit to fetch. */
export type TextField = Exclude<keyof ScenarioDraft, "category">;

/**
 * One Scenario as `GET /api/scenarios/{id}` returns it (ADR 0076): the read
 * view the info panel shows, and — where `editable` is true — the row the
 * editor loads. Not a `ScenarioDraft`: two fields are nullable here.
 */
export interface ScenarioDetail {
  id: string;
  name: string;
  short_description: string;
  briefing: string;
  description: string;
  case_facts: string;
  /** What the caller wants and the bar that settles it, in one field.
   * null = withheld because this is a built-in, whose caller's intent is the
   * answer key (ADR 0076). "" = its author left the field empty. */
  call_goal: string | null;
  category: CategoryChoice;
  /** "public" for a built-in. The editor never sees that value: it opens
   * only where `editable` is true, and those rows are private or tenant. */
  visibility: Visibility | "public";
  /** The caller authored this row and may edit it. Decided by the server from
   * the verified token, never inferred from `origin` here — and false on the
   * two kinds built from a Session, which their author owns but cannot change
   * (ADR 0069, ADR 0070). */
  editable: boolean;
  /** ADR 0070. `reverse_brief` is null on everything that is not a reverse;
   * on one it is the panel shown during the call. */
  reverse: boolean;
  /** ADR 0069. Beside `reverse` because the panel treats the two alike: these
   * are the rows whose one action is deleting them. */
  follow_up: boolean;
  origin_session: OriginSessionRef | null;
  reverse_brief: ReverseBrief | null;
}

/** The editor works on strings; a withheld or absent field is an empty one
 * to it. Only ever called on an `editable` row, where nothing is withheld. */
export function toDraft(detail: ScenarioDetail): ScenarioDraft {
  return {
    name: detail.name,
    short_description: detail.short_description,
    briefing: detail.briefing,
    description: detail.description,
    case_facts: detail.case_facts,
    call_goal: detail.call_goal ?? "",
    category: detail.category,
  };
}

export type FieldLimits = Record<TextField, number>;

/** Max length per authorable field. The backend (`backend/authored_text.py`
 * FIELD_LIMITS) is the single source of truth and validates against it; the
 * editor calls `getFieldLimits()` so its input caps track that automatically.
 * This constant is only the offline fallback if that request fails — the server
 * still rejects an over-long field with a 422 either way. Keep it roughly in
 * step, but it does not need to be exact. */
export const FALLBACK_FIELD_LIMITS: FieldLimits = {
  name: 50,
  short_description: 100,
  briefing: 600,
  description: 500,
  case_facts: 3000,
  call_goal: 1000,
};

/** The lengths the API currently enforces, keyed by the same field names as
 * `ScenarioDraft`. Fetched once when the editor opens. */
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

/** What `POST /api/sessions/{id}/reverse` answers: enough to start the reverse
 * immediately, without a second request for the row that was just written. */
export interface ReverseScenario {
  id: string;
  name: string;
  short_description: string;
  reverse_brief: ReverseBrief | null;
}

/** Create (or find) the reverse of a finished Session: the same call with the
 * roles swapped (F-61, ADR 0070). It stores a Scenario, so the reverse can be
 * selected again later, and it is idempotent — the existing row comes back
 * rather than a second copy. Slow (thinking mode), so callers show a busy
 * state; 409 = nothing to swap or already a reverse, 503 = model unreachable,
 * both with a `detail` to show. */
export const createReverse = (sessionId: string) =>
  apiFetch<ReverseScenario>(`/api/sessions/${sessionId}/reverse`, { method: "POST" });

/** The card of a follow-up Scenario — what both the create route and the
 * Session detail route hand back for one (F-60, ADR 0069). */
export type FollowUpCard = NonNullable<SessionDetail["follow_up"]>;

/** Draft (or find) the follow-up Scenario for a finished Session: the next
 * exercise, built from what its wrap-up asked the User to work on (F-60,
 * ADR 0069). Asked for rather than written unbidden, exactly like the reverse
 * above — the two routes share their shape down to the status codes: 409 =
 * that wrap-up names nothing to build from, 503 = model unreachable, both with
 * a `detail` to show, and a second press returns the row the first one wrote.
 * Slow (thinking mode), so callers show a busy state. */
export const createFollowUp = (sessionId: string) =>
  apiFetch<FollowUpCard>(`/api/sessions/${sessionId}/follow-up`, { method: "POST" });

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
