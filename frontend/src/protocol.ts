/**
 * Mirrors the backend's WebSocket wire protocol (`backend/api/session_ws.py`,
 * see ADR 0033). JSON control messages; binary audio frames are sent/received
 * separately, immediately after the "meta"/"chunk" message that describes them.
 */

/** The call's current phase: sets the wave's color and the sr-only label, and
 * gates whether the waveform reacts to audio at all — only "speaking" does;
 * the actual amplitude comes from useStreamedAudioPlayback's audioLevel, not
 * from this value (see CallAnimation). Usually driven by the server's `state`
 * message, but the client also sets it directly: optimistically on barge-in
 * (ADR 0035, useSessionSocket's sendInterrupt) and held at "speaking" while
 * trailing audio is still playing out (App.tsx's displayState). */
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
}

/**
 * What the info panel behind a Persona card shows (`GET /api/personas/{id}`).
 *
 * Every text here is German display content, never the English prompt fields
 * the model reads (ADR 0043): `traits` is the `traits_label` column and
 * `objections` the objections' `text_label`, not their `text`. `traits` is
 * nullable because the column is — a Persona seeded without one still plays,
 * the panel just leaves the line out.
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

/** Announces one recorded Turn; the raw audio follows as the next binary frame. */
export interface TurnAudioMetaMessage {
  type: "turn.audio.meta";
  turn_seq: number;
  mime_type: string;
  /**
   * How long the user actually spoke, in milliseconds, as measured by the VAD.
   *
   * The server only ever receives the finished recording and cannot derive
   * this itself, but it needs it for speaking rate (F-36), talk-time share
   * (F-24) and fluency (F-51). Optional so the backend can ship ahead of the
   * client: a Turn without it is still stored, just without speaking-rate data.
   */
  duration_ms?: number;
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
   * How many milliseconds of the in-flight persona reply actually played
   * before the user cut in. The server commits only the utterances whose
   * audio finished within this window to the conversation history — anything
   * it streamed ahead but the client never played is discarded, so the next
   * reply can't pick up from words that were never spoken aloud (ADR 0035).
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

export interface Measurement {
  key: string;
  name: string;
  unit: string | null;
  value: number;
  /** ADR 0029's free-form payload: curves, sub-measures, pause positions. */
  detail: Record<string, unknown> | null;
}

export interface SessionTurn {
  turn_id: number;
  speaker: "user" | "persona";
  start_offset_ms: number;
  /** NULL where the utterance has no measured end. */
  duration_ms: number | null;
  transcript: string;
}

export interface FeedbackPoint {
  kind: "strength" | "improvement";
  text: string;
  turn_id: number | null;
}

export interface SessionFeedback {
  summary: string;
  /**
   * F-42: one paragraph on whether the register moved with the phase of the
   * call — warm in the opening, factual through the core business, warm again
   * at the close. Prose rather than a Measurement, because it describes a
   * change over the call that no single number carries. NULL where the
   * wrap-up has none; FeedbackView omits the block instead of showing it
   * empty.
   */
  phase_language: string | null;
  points: FeedbackPoint[];
}

export interface SessionDetail {
  session_id: string;
  persona: string;
  /** The Persona's own id (ADR 0050), for starting the follow-up below
   * against the same partner — `persona` above is only its display name. */
  persona_id: string;
  scenario: string;
  status: FeedbackStatus;
  turns: SessionTurn[];
  /** Statistics for the whole call, not per utterance (ADR 0051). */
  measurements: Measurement[];
  feedback: SessionFeedback | null;
  /**
   * The Scenario the worker drafted from this Session's feedback (F-60,
   * ADR 0069), or null — because there were no improvement points to build one
   * from, because it is still being written, or because the User has since
   * deleted it. The card only; the editor loads the rest by id.
   */
  follow_up: { id: string; name: string; short_description: string } | null;
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
  value: number;
}

/** One row of the training history. */
export interface SessionSummary {
  session_id: string;
  persona: string;
  scenario: string;
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

export interface SessionHistoryPage {
  /** All of the caller's Sessions, not just this page. */
  total: number;
  limit: number;
  offset: number;
  sessions: SessionSummary[];
}
