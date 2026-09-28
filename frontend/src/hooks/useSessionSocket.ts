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
  /** Whether the committed Scenario is a reverse (ADR 0070). Client-side only:
   * it decides whether the briefing panel is fetched and shown, and is never
   * sent — the server reads the casting off the Scenario row, which is the one
   * place it cannot be wrong. */
  reverse: boolean;
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
 * Owns the per-Session WebSocket (ADR 0033's wire protocol). Connects as soon
 * as a Session is committed to (ADR 0042), so the opening line generates in
 * the background while the user is still on the microphone check.
 */
export function useSessionSocket({ session, onAudioChunk, onEnded }: UseSessionSocketOptions) {
  const [callState, setCallState] = useState<CallState>("thinking");
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const turnSeqRef = useRef(0);
  const sessionIdRef = useRef<string | null>(null);
  // After a barge-in, sentences of the cut-off reply are still in transit and
  // must not be played (audio side of ADR 0035). Closed on sendInterrupt,
  // reopened on the next `state: "speaking"`, which the wire order puts after
  // every stale chunk.
  const acceptingAudioRef = useRef(true);
  // `sendActivate` called before the socket opened (usual for F-60/F-61, which
  // skip the mic check). Sent from `onopen`: dropping it would leave the server
  // holding the opening line forever, with nothing on screen to say so.
  const pendingActivateRef = useRef(false);

  useEffect(() => {
    if (session === null) return;

    setError(null);
    setCallState("thinking");
    sessionIdRef.current = null;
    acceptingAudioRef.current = true;
    pendingActivateRef.current = false;

    const ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    // An effect re-run (e.g. StrictMode) can replace this socket before it
    // opens; its onerror/onclose then fire late. Without this guard the stale
    // socket would show a permanent, false "connection lost".
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
      // Order matters: activate marks t=0 and must follow the handshake it
      // belongs to, on the same socket.
      if (pendingActivateRef.current) {
        pendingActivateRef.current = false;
        console.debug("[WS] -> deferred session.activate");
        ws.send(JSON.stringify({ type: "session.activate" } satisfies ClientMessage));
      }
    };

    ws.onmessage = (event: MessageEvent<string | ArrayBuffer>) => {
      if (!isCurrent()) return;
      if (typeof event.data !== "string") {
        // Dropped between a barge-in and the next reply: audio the server
        // streamed ahead of the reply the user just cut off (see above).
        if (acceptingAudioRef.current) onAudioChunk(event.data);
        return;
      }
      const message: ServerMessage = JSON.parse(event.data);
      console.debug("[WS] <-", message);
      switch (message.type) {
        case "state":
          // The next reply is starting: audio is wanted again.
          if (message.value === "speaking") acceptingAudioRef.current = true;
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

  /** The socket, but only while it can actually carry a message. */
  const openSocket = useCallback(() => {
    const ws = wsRef.current;
    return ws && ws.readyState === WebSocket.OPEN ? ws : null;
  }, []);

  /** Sends one JSON control message. Reports whether it went out rather than
   * calling that a loss: a caller with a fallback for a closed socket
   * (endSession) takes it, so only the caller knows what a `false` means. */
  const send = useCallback(
    (message: ClientMessage): boolean => {
      const ws = openSocket();
      if (!ws) {
        console.debug("[WS] not sent, socket not open", wsRef.current?.readyState, message);
        return false;
      }
      console.debug("[WS] ->", message);
      ws.send(JSON.stringify(message));
      return true;
    },
    [openSocket],
  );

  /** One recorded Turn: the meta message and the audio it describes, in that
   * order and on the same socket (ADR 0033). */
  const sendTurnAudio = useCallback(
    (blob: Blob, mimeType: string) => {
      const ws = openSocket();
      if (!ws) {
        console.warn("[WS] dropped turn audio: socket not open", wsRef.current?.readyState);
        return;
      }
      turnSeqRef.current += 1;
      const meta: ClientMessage = {
        type: "turn.audio.meta",
        turn_seq: turnSeqRef.current,
        mime_type: mimeType,
      };
      console.debug("[WS] ->", { ...meta, size: blob.size });
      ws.send(JSON.stringify(meta));
      void blob.arrayBuffer().then((buf) => ws.send(buf));
    },
    [openSocket],
  );

  /** Tells the server to stop the in-flight Turn (a user barge-in) and
   * optimistically flips local state to "listening" right away. `playedMs` is
   * how much of the persona's reply actually played before the cut-in, so the
   * server commits only what was heard to the history (ADR 0035). */
  const sendInterrupt = useCallback(
    (playedMs: number) => {
      // Stop forwarding the reply's audio right away: what is still in transit
      // is the part of it the user just talked over.
      acceptingAudioRef.current = false;
      const sent = send({ type: "turn.interrupt", played_ms: Math.max(0, Math.round(playedMs)) });
      if (sent) setCallState("listening");
    },
    [send],
  );

  /** Marks t=0 on the Session's timeline: the opening line starts playing now.
   * Held back rather than lost when the socket is not open yet (see
   * `pendingActivateRef`); no other message can arrive that early. */
  const sendActivate = useCallback(() => {
    if (!send({ type: "session.activate" })) pendingActivateRef.current = true;
  }, [send]);

  const endSession = useCallback(() => {
    if (send({ type: "session.end" })) return;
    // The handshake never finished, so the server will never send
    // session.ended — end locally instead, so the end-call button always
    // works, even in the brief window before the connection is established.
    const ws = wsRef.current;
    if (ws?.readyState !== WebSocket.CONNECTING) return;
    console.debug("[WS] ending before connection was established");
    ws.close();
    // No handshake means no Session was ever created, let alone persisted,
    // so there is no id and no Feedback to wait for.
    onEnded("user", [], null);
  }, [send, onEnded]);

  return { callState, error, sendTurnAudio, sendInterrupt, sendActivate, endSession };
}
