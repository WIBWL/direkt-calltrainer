import type { ScenarioCategory } from "./scenarioLibrary";

/**
 * Mirrors the backend's WebSocket wire protocol (`backend/api/session_ws.py`,
 * see ADR 0033). JSON control messages; binary audio frames are sent/received
 * separately, immediately after the "meta"/"chunk" message that describes them.
 */

/** The call's phase: sets the wave's colour and sr-only label; only "speaking"
 * reacts to audio (amplitude from useStreamedAudioPlayback's audioLevel). Set by
 * the server's `state` message, and by the client on barge-in (ADR 0035) and
 * while trailing audio plays out (useBargeIn's displayState). */
export type CallState = "listening" | "thinking" | "speaking";

/** One line of the post-call transcript, placed on the Session's timeline.
 * Flattened server-side (backend/session/models.py) so this log and the
 * persisted one cannot disagree about who spoke when. */
export interface TranscriptEntry {
  speaker: "user" | "persona";
  text: string;
  offset_ms: number;
}

// --- Setup lists (GET /api/personas, GET /api/scenarios, backend/app.py) ---
// Display fields only: the prompt text the model reads stays on the server.

export interface Persona {
  id: string;
  name: string;
  role: string;
  // A Persona speaks exactly one language and the user cannot change it
  // (ADR 0043), so the card has to say which one it is.
  language: string;
  // The same language as a code ("de", "en"), for the flag on the card. The
  // display name above is what is read; this is what is switched on.
  language_code: string;
  // Path to the Persona's portrait, served from the app's own static files
  // (`frontend/public/personas/`). Null for a Persona that has none — every
  // place that shows it falls back to the initials.
  avatar_url: string | null;
}

/**
 * The info panel behind a Persona card (`GET /api/personas/{id}`). German
 * display text only, never the prompt fields (ADR 0043): `traits` is
 * `traits_label`, `objections` their `text_label`. `traits` may be null.
 */
export interface PersonaDetail extends Persona {
  traits: string | null;
  training_goal: string;
  objections: string[];
}

export interface Scenario {
  id: string;
  name: string;
  // The short teaser, not the call context the model gets.
  short_description: string;
}

// --- Client -> Server ---

/** First frame after the socket opens: names the Session and carries the token. */
export interface SessionStartMessage {
  type: "session.start";
  persona_id: string;
  scenario_id: string;
  /**
   * The Keycloak access token. A browser can't set an Authorization header on a
   * WebSocket, so it travels in the handshake message (ADR 0009).
   */
  token: string;
}

/**
 * Announces one recorded Turn; the raw audio follows as the next binary frame.
 * No duration on purpose: speaking time is the server's measurement of the
 * recording (ADR 0047/0048), not the VAD's.
 */
export interface TurnAudioMetaMessage {
  type: "turn.audio.meta";
  turn_seq: number;
  mime_type: string;
}

/** Sent the moment the client starts playing the Persona's opening line.
 * The server generates that line as soon as the socket connects (ADR 0042),
 * long before the user reaches the call screen, so this is what tells it where
 * t=0 on the Session's timeline actually is (ADR 0051). */
export interface SessionActivateMessage {
  type: "session.activate";
}

/** The user hung up. The server replies with `session.ended`. */
export interface SessionEndMessage {
  type: "session.end";
}

/** The user talked over the persona; cut the in-flight reply short (barge-in, ADR 0035). */
export interface TurnInterruptMessage {
  type: "turn.interrupt";
  /**
   * Milliseconds of the in-flight reply actually played before the user cut in.
   * The server keeps only what played within it in the history, so the next
   * reply cannot build on words never spoken aloud (ADR 0035).
   */
  played_ms: number;
}

/** Every message the client can send. Discriminated on `type`. */
export type ClientMessage =
  | SessionStartMessage
  | SessionActivateMessage
  | TurnAudioMetaMessage
  | SessionEndMessage
  | TurnInterruptMessage;

// --- Server -> Client ---

/** Handshake accepted; the Session is live. */
export interface SessionStartedMessage {
  type: "session.started";
  session_id: string;
}

/** The call-screen animation should change to `value`. */
export interface StateMessage {
  type: "state";
  value: CallState;
}

/** A synthesized audio chunk follows as the next binary frame. */
export interface TurnAudioChunkMessage {
  type: "turn.audio.chunk";
  turn_seq: number;
  chunk_seq: number;
}

/** One Turn finished; the next user utterance can start. */
export interface TurnCompletedMessage {
  type: "turn.completed";
  turn_seq: number;
}

/** A pipeline leg failed past its retry (ADR 0016); the Session ends after this. */
export interface ErrorMessage {
  type: "error";
  code: "stt_failed" | "llm_failed" | "tts_failed";
  message: string;
}

/** The Session is over; `transcript` is the full post-call summary. */
export interface SessionEndedMessage {
  type: "session.ended";
  reason: "user" | "error" | "completed";
  transcript: TranscriptEntry[];
}

/** Every message the server can send. Discriminated on `type`. */
export type ServerMessage =
  | SessionStartedMessage
  | StateMessage
  | TurnAudioChunkMessage
  | TurnCompletedMessage
  | ErrorMessage
  | SessionEndedMessage;

// --- Finished Session (GET /api/sessions/{id}, backend/api/sessions.py) ---
// The wrap-up is generated asynchronously (ADR 0019), so a Session is readable
// before its Feedback exists; `status` says which of the two this is.

export type FeedbackStatus = "queued" | "running" | "done" | "failed";

/** backend/db/models.py METRIC_ASPECTS. */
export type MetricAspect = "how" | "what";

export interface Measurement {
  key: string;
  name: string;
  unit: string | null;
  /** Which half of the metrics this one sits in. NULL only for a metric
   * the inventory has retired. */
  aspect: MetricAspect | null;
  value: number;
  /** ADR 0029's free-form payload: curves, sub-measures, pause positions —
   *  plus whatever the metric's reading adds on the way out (ADR 0091), which
   *  is derived on every read and never stored: F-35's liveliness step, F-51's
   *  light, F-37's `course` (the band and the stretches the page draws). */
  detail: Record<string, unknown> | null;
}

export interface SessionTurn {
  turn_id: number;
  speaker: "user" | "persona";
  start_offset_ms: number;
  /** NULL where the utterance has no measured end. */
  duration_ms: number | null;
  transcript: string;
  /** True on a Persona line the user cut into (ADR 0035). */
  interrupted: boolean;
  /**
   * What the Persona was about to say when interrupted; null otherwise and for
   * older recordings. Never transcript — always rendered as what was *not* said.
   */
  unheard_text: string | null;
}

export interface FeedbackPoint {
  kind: "strength" | "improvement";
  text: string;
  turn_id: number | null;
  /**
   * The F-62 focus goal this point is about (catalogue key), assigned by the
   * wrap-up (ADR 0080); null for older wrap-ups or when nothing fitted.
   */
  goal: string | null;
}

/**
 * One tagged point of a wrap-up. The text rides along so the progress view can
 * quote what was written about a goal (ADR 0064's amendment); summary, phase
 * paragraph and untagged points stay on the detail route.
 */
export interface FeedbackGoalTag {
  kind: "strength" | "improvement";
  goal: string;
  /** The point as the wrap-up wrote it. Two sentences at most in practice. */
  text: string;
}

export interface SessionFeedback {
  summary: string;
  /**
   * F-42: whether the register moved with the phase of the call. Prose, not a
   * Measurement (ADR 0056). NULL where absent; the block is then omitted.
   */
  phase_language: string | null;
  /**
   * Whether the trainee's tone suited this call's occasion (ADR 0079), prose
   * for ADR 0056's reasons. Rendered on the Sprachmelodie page, not in the
   * wrap-up. NULL where absent; the block is then omitted.
   */
  tone_fit: string | null;
  points: FeedbackPoint[];
}

/**
 * One noted moment inside a call, the counterpart to a Measurement: a
 * Measurement is what the whole call amounted to, a Finding is one thing that
 * happened at one point. F-51's hard interruptions are the first kind written.
 */
export interface Finding {
  /** Machine-readable kind, e.g. "hard_interruption". The wording is
   *  `description`; this decides where the entry belongs. */
  category: string;
  /** Milliseconds into the call, so the entry can be placed on the transcript. */
  offset_ms: number | null;
  description: string;
  /** The metric this moment belongs to, or null if it stands alone. */
  metric_key: string | null;
}

/** The provisional three-step reading of a figure, computed server-side from
 *  thresholds that are declared heuristics. Shown as an orientation, never as
 *  a verdict, and never as colour alone. */
export type TrafficLight = "green" | "yellow" | "red";

/**
 * One step of a reading's scale (F-51, F-35). `label`, `range` and `light` come
 * from the backend, beside their thresholds, so a recalibration cannot leave wrong
 * words on screen; never map them here (ADR 0078). `light` null = no direction.
 */
export interface MetricStep {
  /** Machine-readable step name, matched against the measurement's own
   *  reading (`detail.liveliness` / `detail.light`) to mark the current one. */
  step: string;
  label: string;
  /** Where this step applies, written out, e.g. "15 % bis 25 %". */
  range: string;
  light: TrafficLight | null;
}

/** Which stretch of a call a figure describes (ADR 0081). `call` is the whole
 *  of it and is what `measurements` carries; these two are the exchanges where
 *  the partner pushed back, and everything else. */
export type MeasurementSegment = "pressure" | "rest";

/**
 * One metric over one stretch of a call (ADR 0081). Deliberately no difference,
 * ratio or verdict between stretches (ADR 0051). No `detail`: nothing plots a
 * segment's curve (ADR 0064).
 */
export interface SegmentMeasurement {
  segment: MeasurementSegment;
  key: string;
  name: string;
  unit: string | null;
  value: number;
}

export interface SessionDetail {
  session_id: string;
  persona: string;
  /** The Persona's own id (ADR 0050), for starting the follow-up below
   * against the same partner — `persona` above is only its display name. */
  persona_id: string;
  scenario: string;
  /** Whether this training was a reverse — the User rang and the Persona
   * answered (ADR 0070). Display only; the casting itself lives on the
   * Scenario row. */
  reverse: boolean;
  status: FeedbackStatus;
  turns: SessionTurn[];
  /** Statistics for the whole call, not per utterance (ADR 0051). */
  measurements: Measurement[];
  /** The same metrics over the demanding stretches and over the rest
   *  (ADR 0081). Empty where nobody pushed back, where a stretch was too short
   *  to measure, and for every call recorded before the per-utterance facts
   *  were kept. */
  segments: SegmentMeasurement[];
  /** Individual noted moments, ordered by when they happened. */
  findings: Finding[];
  /** The long explanation behind a metric's "i", by metric key. Served
   *  rather than bundled, so the text and the thresholds it explains are
   *  edited in one place (ADR 0063's arrangement for the field limits). */
  metric_notes: Record<string, string>;
  /** The steps a reading comes from, by metric key, written out. Shown beside
   *  it: a boundary the user cannot see is a judgement they cannot argue
   *  with. */
  metric_scales: Record<string, MetricStep[]>;
  feedback: SessionFeedback | null;
  /**
   * The follow-up drafted from this Session (F-60, ADR 0069), or null if none
   * was asked for, possible or kept. The card only; the rest loads by id.
   */
  follow_up: FollowUpCard | null;
}

/** The card of a follow-up Scenario — what both the create route and the
 * Session detail route hand back for one (F-60, ADR 0069). */
export interface FollowUpCard {
  id: string;
  name: string;
  short_description: string;
}

// --- Session history (GET /api/sessions, ADR 0064) -------------------------
// The caller's own finished Sessions, newest first. Note that `status` means
// something different here than on SessionDetail above: this is the Session's
// own outcome, that one is the state of its wrap-up job.

/** How a stored Session ended — `session.status` in the schema (ADR 0057). */
export type SessionOutcome = "completed" | "aborted";

/** A Measurement as the listing carries it: no `detail`, because the loudness
 * curve would outweigh everything else on a page of Sessions (ADR 0064). */
export interface SessionSummaryMeasurement {
  key: string;
  name: string;
  unit: string | null;
  /** Which half of the metrics this one sits in — the schema's own `aspect`
   *  (ADR 0064). Display only: it decides which side of the dashboard's
   *  delivery/content switch the metric appears on, and nothing else. */
  aspect: MetricAspect;
  value: number;
  /**
   * False for a metric measured under a since-renamed key. The progress view
   * drops those, or one renamed metric appears as two identical charts.
   */
  active: boolean;
}

/** One row of the training history. */
export interface SessionSummary {
  session_id: string;
  persona: string;
  scenario: string;
  /** Whether this training was a reverse — the User rang and the Persona
   * answered (ADR 0070). Display only; the casting itself lives on the
   * Scenario row. */
  reverse: boolean;
  /**
   * The kind of call (ADR 0072), null for authored Scenarios and reverses. On
   * the listing so the progress view can read courses per occasion.
   */
  category: ScenarioCategory | null;
  status: SessionOutcome;
  /** Whether a wrap-up was stored — i.e. whether this row has one to open. */
  has_feedback: boolean;
  /**
   * Why not, where there is none: the wrap-up job's state. Carries its own
   * name rather than sharing `status`, which on this route is the Session's
   * own outcome and nothing else (ADR 0057/0064).
   */
  feedback_status: FeedbackStatus;
  /** ISO 8601, from the client's `session.activate` (ADR 0051). */
  started_at: string;
  /** ISO 8601. NULL where the Session has no recorded end. */
  ended_at: string | null;
  measurements: SessionSummaryMeasurement[];
  /** The demanding stretches against the rest (ADR 0081), the only data behind
   *  the focus goal "composure under pressure". Beside `measurements` and not
   *  inside it: that list is one entry per metric, and a series built over it
   *  would splice one training's pressure figure into the next one's line. */
  segments: SegmentMeasurement[];
  /**
   * One entry per tagged point; untagged points are absent, not null-goaled, so
   * "not assigned" cannot be counted as a category. Empty without a wrap-up.
   */
  feedback_goals: FeedbackGoalTag[];
}

// --- What is stored about the caller (GET /api/me/data, ADR 0066) ----------

/** Counts and the period they span — the extent of the data, not its content. */
export interface DataOverviewPayload {
  sessions: number;
  utterances: number;
  measurements: number;
  feedbacks: number;
  first_session_at: string | null;
  last_session_at: string | null;
  retention: RetentionState;
}

/** How long stored trainings are kept, and whether the sweep applies (ADR 0067). */
export interface RetentionState {
  /** False when the user has suspended the automatic deletion. */
  auto_delete: boolean;
  /** The retention period in days. */
  retention_days: number;
  /**
   * When the oldest stored training falls due. Null when nothing is stored, or
   * when the sweep is suspended, in which case the interface must not name a
   * date because there is not going to be one.
   */
  next_expiry_at: string | null;
}

// --- Storage consent (GET/POST /api/consent, ADR 0066) ---------------------

/** What the user decided about their trainings being stored, if anything. */
export interface ConsentState {
  /** null where no decision was ever recorded — a new account. */
  status: "granted" | "withdrawn" | null;
  /** The wording that decision was made against. */
  version: string | null;
  decided_at: string | null;
  /** The wording currently in force; a mismatch makes the decision stale. */
  current_version: string;
  /** Whether finished trainings are being stored right now. */
  allows_storage: boolean;
  /** Whether the interface has to ask. False after a withdrawal — that is a
   *  decision, and re-asking would be a way of wearing the user down. */
  decision_required: boolean;
}

// --- Training focus (GET/PUT /api/focus, F-62, ADR 0076) -------------------

/** Which heading a goal sits under. Display grouping only. */
export type FocusGroupKey = "paraverbal" | "phases" | "impact" | "habit";

/** One entry of the shipped catalogue; German text from the database. The
 *  goal's `evidence` is deliberately absent: planning information, not
 *  something the user weighs while picking (ADR 0076). */
export interface FocusGoal {
  key: string;
  title: string;
  caption: string;
  /** The paragraph behind the "i". */
  info: string;
  group: FocusGroupKey;
}

export interface FocusGroup {
  key: FocusGroupKey;
  name: string;
}

/** A role on offer (F-62), with the call types it preselects. */
export interface FocusRole {
  key: string;
  name: string;
  categories: ScenarioCategory[];
}

/** The catalogue plus what the caller has picked out of it. */
export interface FocusState {
  /** How many goals may be focused on at once. Read from here rather than
   *  hardcoded, so the interface enforces the number the backend does. */
  max_goals: number;
  /** Whether the question has been answered at all. An empty `selected` with
   *  `decided: true` is "no focus" — a real answer, not a missing one. */
  decided: boolean;
  decided_at: string | null;
  /** Whether the first-run dialog still has to ask. */
  decision_required: boolean;
  /** The picked keys, in catalogue order. */
  selected: string[];
  /** What the User said about their work (F-62); both optional. */
  role: string | null;
  categories: ScenarioCategory[];
  roles: FocusRole[];
  groups: FocusGroup[];
  goals: FocusGoal[];
}

/** The whole of what PUT /api/focus replaces; leaving a part out clears it. */
export interface FocusChoice {
  goals: string[];
  role: string | null;
  categories: ScenarioCategory[];
}

export interface SessionHistoryPage {
  /** All of the caller's Sessions, not just this page. */
  total: number;
  limit: number;
  offset: number;
  sessions: SessionSummary[];
}
