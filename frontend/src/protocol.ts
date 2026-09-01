// Mirrors the backend's WebSocket wire protocol (backend/api/session_ws.py,
// see ADR 0033). JSON control messages; binary audio frames are sent/received
// separately, immediately after the "meta"/"chunk" message that describes them.

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

export interface SessionStartMessage {
  type: "session.start";
  persona_id: string;
  scenario_id: string;
}

export interface TurnAudioMetaMessage {
  type: "turn.audio.meta";
  turn_seq: number;
  mime_type: string;
}

/** Sent the moment the client starts playing the Persona's opening line.
 * The server generates that line as soon as the socket connects (ADR 0042),
 * long before the user reaches the call screen, so this is what tells it where
 * t=0 on the Session's timeline actually is (ADR 0049). */
export interface SessionActivateMessage {
  type: "session.activate";
}

export interface SessionEndMessage {
  type: "session.end";
}

export interface TurnInterruptMessage {
  type: "turn.interrupt";
}

export type ClientMessage =
  | SessionStartMessage
  | SessionActivateMessage
  | TurnAudioMetaMessage
  | SessionEndMessage
  | TurnInterruptMessage;

// --- Server -> Client ---

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

export interface ErrorMessage {
  type: "error";
  code: "stt_failed" | "llm_failed" | "tts_failed";
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
  /** Statistics for the whole call, not per utterance (ADR 0049). */
  messungen: Messung[];
  feedback: SessionFeedback | null;
}
