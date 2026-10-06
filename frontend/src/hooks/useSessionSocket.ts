import { useCallback, useEffect, useRef, useState } from "react";

import { currentAccessToken } from "../auth";
import { apiUrl } from "../config";
import type { CallState, ClientMessage, ServerMessage, TranscriptEntry } from "../protocol";

// The backend's origin, or the SPA's own when empty (Vite proxies /ws). The
// token rides in the first message, so a foreign page has none to borrow (ADR 0107).
const WS_URL =
  typeof window === "undefined"
    ? "/ws/session"
    : new URL("/ws/session", apiUrl || window.location.origin).href.replace(/^http/, "ws");

/** Keyed on identity: committing to the same pairing twice still reconnects. Don't memoize it. */
export interface CommittedSession {
  personaId: string;
  scenarioId: string;
  /** ADR 0070. Client-side only; the server reads the casting off the Scenario. */
  reverse: boolean;
}

interface UseSessionSocketOptions {
  session: CommittedSession | null;
  onAudioChunk: (data: ArrayBuffer) => void;
  onEnded: (
    reason: "user" | "error" | "completed",
    transcript: TranscriptEntry[],
    sessionId: string | null,
  ) => void;
}

/** The per-Session WebSocket (ADR 0033). Connects on commit (ADR 0042), so a
 * reverse's answering line generates while the user reads the briefing. */
export function useSessionSocket({ session, onAudioChunk, onEnded }: UseSessionSocketOptions) {
  const [callState, setCallState] = useState<CallState>("thinking");
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const turnSeqRef = useRef(0);
  const sessionIdRef = useRef<string | null>(null);
  // After a barge-in, chunks of the cut-off reply are still in transit (ADR 0035).
  // Reopened on the next `state: "speaking"`, which follows every stale chunk.
  const acceptingAudioRef = useRef(true);
  // `sendActivate` before the socket opened (F-60/F-61 skip the mic check).
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

    // A StrictMode re-run can replace this socket before it opens; its late
    // onerror/onclose must not show a false "connection lost".
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
      // activate must follow the handshake, on the same socket.
      if (pendingActivateRef.current) {
        pendingActivateRef.current = false;
        console.debug("[WS] -> deferred session.activate");
        ws.send(JSON.stringify({ type: "session.activate" } satisfies ClientMessage));
      }
    };

    ws.onmessage = (event: MessageEvent<string | ArrayBuffer>) => {
      if (!isCurrent()) return;
      if (typeof event.data !== "string") {
        if (acceptingAudioRef.current) onAudioChunk(event.data);
        return;
      }
      const message: ServerMessage = JSON.parse(event.data);
      console.debug("[WS] <-", message);
      switch (message.type) {
        case "state":
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

  const openSocket = useCallback(() => {
    const ws = wsRef.current;
    return ws && ws.readyState === WebSocket.OPEN ? ws : null;
  }, []);

  /** Reports whether it went out; only the caller knows what `false` means. */
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

  /** Meta message, then audio, on the same socket (ADR 0033). */
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

  /** Barge-in: flips local state to "listening" at once. `playedMs` bounds what
   * the server keeps in the history (ADR 0035). */
  const sendInterrupt = useCallback(
    (playedMs: number) => {
      acceptingAudioRef.current = false;
      const sent = send({ type: "turn.interrupt", played_ms: Math.max(0, Math.round(playedMs)) });
      if (sent) setCallState("listening");
    },
    [send],
  );

  /** t=0 on the timeline; held until the socket opens. */
  const sendActivate = useCallback(() => {
    if (!send({ type: "session.activate" })) pendingActivateRef.current = true;
  }, [send]);

  /** ADR 0110. Lost on a closed socket, which only postpones a "Hallo?". */
  const sendSpeaking = useCallback(() => {
    send({ type: "user.speaking" });
  }, [send]);

  const endSession = useCallback(() => {
    if (send({ type: "session.end" })) return;
    // No handshake, so no session.ended will come: end locally, before the
    // connection is up or after a refusal (ADR 0109).
    if (sessionIdRef.current !== null) return;
    const ws = wsRef.current;
    console.debug("[WS] ending a call that never started");
    if (ws?.readyState === WebSocket.CONNECTING) ws.close();
    onEnded("user", [], null);
  }, [send, onEnded]);

  return { callState, error, sendTurnAudio, sendInterrupt, sendActivate, sendSpeaking, endSession };
}
