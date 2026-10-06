import type { ScenarioCategory } from "./scenarioLibrary";

/** The backend's wire protocol (ADR 0033). Binary audio frames follow the "meta"/"chunk" message describing them. */

/** Set by the server's `state` message, and by the client on barge-in (ADR 0035). */
export type CallState = "listening" | "thinking" | "speaking";

export interface TranscriptEntry {
  speaker: "user" | "persona";
  text: string;
  offset_ms: number;
}

// Setup lists: display fields only; the prompt text stays on the server.

export interface Persona {
  id: string;
  name: string;
  role: string;
  language: string;
  language_code: string;
  // Null without a portrait; the card falls back to the initials.
  avatar_url: string | null;
}

/** German display text only, never the prompt fields (ADR 0043). */
export interface PersonaDetail extends Persona {
  traits: string | null;
  training_goal: string;
  objections: string[];
}

export interface Scenario {
  id: string;
  name: string;
  short_description: string;
}

export interface SessionStartMessage {
  type: "session.start";
  persona_id: string;
  scenario_id: string;
  /** Browsers cannot set headers on a WebSocket (ADR 0009). */
  token: string;
}

/** The audio follows as the next binary frame. No duration: the server measures it (ADR 0048). */
export interface TurnAudioMetaMessage {
  type: "turn.audio.meta";
  turn_seq: number;
  mime_type: string;
}

/** The user accepted the call: t=0 on the timeline (ADR 0051), and the wait for the user's first words (ADR 0110). */
export interface SessionActivateMessage {
  type: "session.activate";
}

export interface SessionEndMessage {
  type: "session.end";
}

/** Stops the server asking "Hallo?" into a sentence still being recorded (ADR 0110). */
export interface UserSpeakingMessage {
  type: "user.speaking";
}

/** Barge-in (ADR 0035). */
export interface TurnInterruptMessage {
  type: "turn.interrupt";
  /** How much of the reply played; the server keeps only that in the history. */
  played_ms: number;
}

export type ClientMessage =
  | SessionStartMessage
  | SessionActivateMessage
  | TurnAudioMetaMessage
  | SessionEndMessage
  | TurnInterruptMessage
  | UserSpeakingMessage;

export interface SessionStartedMessage {
  type: "session.started";
  session_id: string;
}

export interface StateMessage {
  type: "state";
  value: CallState;
}

export interface TurnAudioChunkMessage {
  type: "turn.audio.chunk";
  turn_seq: number;
  chunk_seq: number;
}

export interface TurnCompletedMessage {
  type: "turn.completed";
  turn_seq: number;
}

/** A leg failed past its retry, the handshake was refused or the time limit hit; the Session ends. `message` is German. */
export interface ErrorMessage {
  type: "error";
  code:
    | "stt_failed"
    | "llm_failed"
    | "tts_failed"
    | "not_admitted"
    | "too_many_calls"
    | "time_limit";
  message: string;
}

export interface SessionEndedMessage {
  type: "session.ended";
  reason: "user" | "error" | "completed";
  transcript: TranscriptEntry[];
}

export type ServerMessage =
  | SessionStartedMessage
  | StateMessage
  | TurnAudioChunkMessage
  | TurnCompletedMessage
  | ErrorMessage
  | SessionEndedMessage;

// Finished Session. The wrap-up is generated asynchronously (ADR 0019); `status` is its job's state.

export type FeedbackStatus = "queued" | "running" | "done" | "failed";

export type MetricAspect = "how" | "what";

export interface Measurement {
  key: string;
  name: string;
  unit: string | null;
  /** NULL only for a retired metric. */
  aspect: MetricAspect | null;
  value: number;
  /** ADR 0029's payload plus what the reading derives on every read (ADR 0091). */
  detail: Record<string, unknown> | null;
}

export interface SessionTurn {
  turn_id: number;
  speaker: "user" | "persona";
  start_offset_ms: number;
  duration_ms: number | null;
  transcript: string;
  interrupted: boolean;
  /** Never transcript: always rendered as what was not said. */
  unheard_text: string | null;
}

export interface FeedbackPoint {
  kind: "strength" | "improvement";
  text: string;
  turn_id: number | null;
  /** A focus-goal key (ADR 0080), or null. */
  goal: string | null;
}

/** A tagged point, with its text for the progress view (ADR 0064). */
export interface FeedbackGoalTag {
  kind: "strength" | "improvement";
  goal: string;
  text: string;
}

export interface SessionFeedback {
  summary: string;
  /** F-42 (ADR 0056). NULL omits the block. */
  phase_language: string | null;
  /** ADR 0079; shown on the Sprachmelodie page. NULL omits the block. */
  tone_fit: string | null;
  points: FeedbackPoint[];
}

/** One noted moment, where a Measurement is the whole call. */
export interface Finding {
  category: string;
  offset_ms: number | null;
  description: string;
  metric_key: string | null;
}

/** A provisional orientation, never a verdict, never colour alone (ADR 0078). */
export type TrafficLight = "green" | "yellow" | "red";

/** Words and lights come from the backend beside their thresholds (ADR 0078). `light` null = no direction. */
export interface MetricStep {
  /** Matched against `detail.liveliness` / `detail.light`. */
  step: string;
  label: string;
  range: string;
  light: TrafficLight | null;
}

/** ADR 0081: `call` is the whole call; `pressure` and `rest` its two stretches. */
export type MeasurementSegment = "pressure" | "rest";

/** No difference or verdict between stretches (ADR 0051), and no `detail`. */
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
  persona_id: string;
  scenario: string;
  /** The User rang and the Persona answered (ADR 0070). */
  reverse: boolean;
  status: FeedbackStatus;
  turns: SessionTurn[];
  measurements: Measurement[];
  /** Empty where nobody pushed back or a stretch was too short (ADR 0081). */
  segments: SegmentMeasurement[];
  findings: Finding[];
  /** The text behind a metric's "i", served beside its thresholds (ADR 0098). */
  metric_notes: Record<string, string>;
  metric_scales: Record<string, MetricStep[]>;
  feedback: SessionFeedback | null;
  /** F-60 (ADR 0069), or null. */
  follow_up: FollowUpCard | null;
}

export interface FollowUpCard {
  id: string;
  name: string;
  short_description: string;
}

// History (ADR 0064). `status` here is the Session's outcome, not the job's.

export type SessionOutcome = "completed" | "aborted";

/** No `detail`: the loudness curve would outweigh the page (ADR 0064). */
export interface SessionSummaryMeasurement {
  key: string;
  name: string;
  unit: string | null;
  aspect: MetricAspect;
  value: number;
}

export interface SessionSummary {
  session_id: string;
  persona: string;
  scenario: string;
  /** The User rang and the Persona answered (ADR 0070). */
  reverse: boolean;
  /** ADR 0072; null for authored Scenarios and reverses. */
  category: ScenarioCategory | null;
  status: SessionOutcome;
  has_feedback: boolean;
  /** The wrap-up job's state, kept apart from `status` (ADR 0057/0064). */
  feedback_status: FeedbackStatus;
  started_at: string;
  ended_at: string | null;
  measurements: SessionSummaryMeasurement[];
  /** Beside `measurements`, or a series would splice in segment figures (ADR 0081). */
  segments: SegmentMeasurement[];
  /** Untagged points are absent, not null-goaled. */
  feedback_goals: FeedbackGoalTag[];
}

// GET /api/me/data (ADR 0066)

export interface DataOverviewPayload {
  sessions: number;
  utterances: number;
  measurements: number;
  feedbacks: number;
  first_session_at: string | null;
  last_session_at: string | null;
  retention: RetentionState;
}

/** ADR 0067. */
export interface RetentionState {
  auto_delete: boolean;
  retention_days: number;
  /** Null when nothing is stored or the sweep is suspended: then there is no date. */
  next_expiry_at: string | null;
}

// Consent (ADR 0066)

export interface ConsentState {
  status: "granted" | "withdrawn" | null;
  version: string | null;
  decided_at: string | null;
  current_version: string;
  allows_storage: boolean;
  /** False after a withdrawal: re-asking would wear the user down. */
  decision_required: boolean;
}

// Training focus (F-62, ADR 0076)

export type FocusGroupKey = "paraverbal" | "phases" | "impact" | "habit";

export interface FocusGoal {
  key: string;
  title: string;
  caption: string;
  info: string;
  group: FocusGroupKey;
}

export interface FocusGroup {
  key: FocusGroupKey;
  name: string;
}

export interface FocusRole {
  key: string;
  name: string;
  categories: ScenarioCategory[];
}

export interface FocusState {
  /** Read from here, so the interface enforces the backend's number. */
  max_goals: number;
  /** `decided` with an empty `selected` is "no focus", a real answer. */
  decided: boolean;
  decided_at: string | null;
  decision_required: boolean;
  selected: string[];
  role: string | null;
  categories: ScenarioCategory[];
  roles: FocusRole[];
  groups: FocusGroup[];
  goals: FocusGoal[];
}

/** PUT /api/focus replaces all of it; a part left out is cleared. */
export interface FocusChoice {
  goals: string[];
  role: string | null;
  categories: ScenarioCategory[];
}

export interface SessionHistoryPage {
  total: number;
  limit: number;
  offset: number;
  sessions: SessionSummary[];
}
