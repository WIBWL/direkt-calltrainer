import { useCallback, useEffect, useRef, useState } from "react";

import { currentAccessToken } from "../auth";
import type { CallState, ClientMessage, ServerMessage, TranscriptEntry } from "../protocol";

// The backend serves this SPA, so the WebSocket is same-origin (see CLAUDE.md).
// Derived from window.location rather than a base-URL env var, which no longer
// exists.
const WS_URL =
  typeof window === "undefined"
    ? "/ws/session"
    : `${window.location.origin.replace(/^http/, "ws")}/ws/session`;

/** The Session the user has committed to, as far as the connection is
 * concerned. A fresh object stands for a fresh Session: the connection is
 * keyed on this object's *identity*, not on its contents, so committing to
 * the same Persona/Scenario pairing twice still reconnects rather than
 * reusing the finished Session's socket. Don't memoize it. */
export interface CommittedSession {
  personaId: string;
  scenarioId: string;
}

interface UseSessionSocketOptions {
  session: CommittedSession | null;
  onAudioChunk: (data: ArrayBuffer) => void;
  onEnded: (
    reason: "user" | "error" | "completed",
    transcript: TranscriptEntry[],
    /** Names the persisted Session, for fetching its Feedback afterwards. */
    sessionId: string | null,
  ) => void;
}

/**
 * Owns the per-Session WebSocket connection (see ADR 0033's wire protocol):
 * sends the initial handshake, forwards Turn audio, and translates incoming
 * state/audio-chunk/error/session.ended messages into hook state. Connects
 * as soon as a Session is committed to — which per ADR 0042 is the moment
 * the user leaves the selection screen, not the moment a Persona/Scenario
 * is picked — so the Persona's opening line generates in the background
 * while the user is still on the microphone check.
 */
export function useSessionSocket({ session, onAudioChunk, onEnded }: UseSessionSocketOptions) {
  const [callState, setCallState] = useState<CallState>("thinking");
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const turnSeqRef = useRef(0);
  const sessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (session === null) return;

    setError(null);
    setCallState("thinking");
    sessionIdRef.current = null;

    const ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    // React (StrictMode, or any effect re-run) can tear this effect down and
    // re-run it before this specific socket ever opens — its own onerror/
    // onclose then fire asynchronously afterwards, once wsRef.current already
    // points at the *next* socket. Without this guard, that stale socket's
    // error would still overwrite state and show a permanent, misleading
    // "connection lost" message even though the real connection is fine.
    const isCurrent = () => wsRef.current === ws;

    ws.onopen = async () => {
      if (!isCurrent()) return;
      const token = await currentAccessToken();
      if (!isCurrent()) return;
      if (!token) {
        console.warn("[WS] no access token; closing");
        ws.close();
        setError("Sitzung abgelaufen. Bitte neu anmelden.");
        return;
      }
      console.debug("[WS] connected, sending session.start");
      const start: ClientMessage = {
        type: "session.start",
        persona_id: session.personaId,
        scenario_id: session.scenarioId,
        token,
      };
      ws.send(JSON.stringify(start));
    };

    ws.onmessage = (event: MessageEvent<string | ArrayBuffer>) => {
      if (!isCurrent()) return;
      if (typeof event.data !== "string") {
        onAudioChunk(event.data);
        return;
      }
      const message: ServerMessage = JSON.parse(event.data);
      console.debug("[WS] <-", message);
      switch (message.type) {
        case "state":
          setCallState(message.value);
          break;
        case "error":
          setError(message.message);
          break;
        case "session.ended":
          onEnded(message.reason, message.transcript, sessionIdRef.current);
          break;
        case "session.started":
          sessionIdRef.current = message.session_id;
          break;
        case "turn.audio.chunk":
        case "turn.completed":
          break;
      }
    };

    ws.onerror = (event) => {
      if (!isCurrent()) {
        console.debug("[WS] error on a stale/discarded socket, ignoring", event);
        return;
      }
      console.error("[WS] error", event);
      setError("Verbindung zum Server unterbrochen.");
    };

    ws.onclose = (event) => {
      console.debug("[WS] closed", { code: event.code, reason: event.reason, stale: !isCurrent() });
    };

    return () => {
      ws.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reconnecting on every callback identity change would tear down the call
  }, [session]);

  const sendTurnAudio = useCallback((blob: Blob, mimeType: string) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn("[WS] dropped turn audio: socket not open", ws?.readyState);
      return;
    }
    turnSeqRef.current += 1;
    console.debug("[WS] -> turn.audio.meta", { turn_seq: turnSeqRef.current, size: blob.size, mimeType });
    const meta: ClientMessage = { type: "turn.audio.meta", turn_seq: turnSeqRef.current, mime_type: mimeType };
    ws.send(JSON.stringify(meta));
    void blob.arrayBuffer().then((buf) => ws.send(buf));
  }, []);

  /** Tells the server to stop the in-flight Turn (a user barge-in) and
   * optimistically flips local state to "listening" right away. */
  const sendInterrupt = useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    console.debug("[WS] -> turn.interrupt");
    const interrupt: ClientMessage = { type: "turn.interrupt" };
    ws.send(JSON.stringify(interrupt));
    setCallState("listening");
  }, []);

  /** Marks t=0 on the Session's timeline: the opening line starts playing now. */
  const sendActivate = useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    console.debug("[WS] -> session.activate");
    const activate: ClientMessage = { type: "session.activate" };
    ws.send(JSON.stringify(activate));
  }, []);

  const endSession = useCallback(() => {
    const ws = wsRef.current;
    if (!ws) return;
    if (ws.readyState === WebSocket.OPEN) {
      const end: ClientMessage = { type: "session.end" };
      ws.send(JSON.stringify(end));
      return;
    }
    if (ws.readyState === WebSocket.CONNECTING) {
      // The handshake never finished, so the server will never send
      // session.ended — end locally instead, so "Anruf beenden" always works,
      // even in the brief window before the connection is established.
      console.debug("[WS] ending before connection was established");
      ws.close();
      // No handshake means no Session was ever created, let alone persisted,
      // so there is no id and no Feedback to wait for.
      onEnded("user", [], null);
    }
  }, [onEnded]);

  return { callState, error, sendTurnAudio, sendInterrupt, sendActivate, endSession };
}
