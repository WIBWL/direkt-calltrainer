// Mirrors the backend's WebSocket wire protocol (backend/api/session_ws.py,
// see ADR 0033). JSON control messages; binary audio frames are sent/received
// separately, immediately after the "meta"/"chunk" message that describes them.

export type CallState = "listening" | "thinking" | "speaking";

export interface TurnRecord {
  turn_seq: number;
  user_text: string;
  persona_text: string;
}

// --- Client -> Server ---

export interface SessionStartMessage {
  type: "session.start";
  persona_id: string;
  scenario_id: string;
  // The Keycloak access token. A browser can't set an Authorization header on a
  // WebSocket, so it travels in the handshake message (ADR 0009).
  token: string;
}

export interface TurnAudioMetaMessage {
  type: "turn.audio.meta";
  turn_seq: number;
  mime_type: string;
}

export interface SessionEndMessage {
  type: "session.end";
}

export interface TurnInterruptMessage {
  type: "turn.interrupt";
}

export type ClientMessage =
  | SessionStartMessage
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
  transcript: TurnRecord[];
}

export type ServerMessage =
  | SessionStartedMessage
  | StateMessage
  | TurnAudioChunkMessage
  | TurnCompletedMessage
  | ErrorMessage
  | SessionEndedMessage;
