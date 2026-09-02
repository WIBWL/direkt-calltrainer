/**
 * Mirrors the backend's WebSocket wire protocol (`backend/api/session_ws.py`,
 * see ADR 0033). JSON control messages; binary audio frames are sent/received
 * separately, immediately after the "meta"/"chunk" message that describes them.
 */

/** The animation the call screen shows; driven by the server's `state` message. */
export type CallState = "listening" | "thinking" | "speaking";

/** One line of the post-call Gesprächsprotokoll, placed on the Session's
 * timeline. Flattened server-side (backend/session/models.py) so this log and
 * the persisted one cannot disagree about who spoke when. */
export interface TranscriptEntry {
  sprecher: "nutzer" | "persona";
  text: string;
  offset_ms: number;
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

export interface Messung {
  schluessel: string;
  bezeichnung: string;
  einheit: string | null;
  wert: number;
  /** ADR 0029's free-form payload: curves, sub-measures, pause positions. */
  detail: Record<string, unknown> | null;
}

export interface SessionTurn {
  turn_id: number;
  sprecher: "nutzer" | "persona";
  start_offset_ms: number;
  /** NULL where the utterance has no measured end. */
  dauer_ms: number | null;
  transkript: string;
}

export interface Feedbackpunkt {
  art: "staerke" | "verbesserung";
  text: string;
  turn_id: number | null;
}

export interface SessionFeedback {
  zusammenfassung: string;
  punkte: Feedbackpunkt[];
}

export interface SessionDetail {
  session_id: string;
  persona: string;
  szenario: string;
  status: FeedbackStatus;
  turns: SessionTurn[];
  /** Statistics for the whole call, not per utterance (ADR 0051). */
  messungen: Messung[];
  feedback: SessionFeedback | null;
}
