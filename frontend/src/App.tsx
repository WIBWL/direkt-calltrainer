import { useCallback, useEffect, useRef, useState } from "react";

import CallView from "./components/CallView";
import FeedbackView from "./components/FeedbackView";
import MicCheck from "./components/MicCheck";
import TranscriptView from "./components/TranscriptView";
import { useMicrophoneVAD } from "./hooks/useMicrophoneVAD";
import { useSessionSocket } from "./hooks/useSessionSocket";
import { useStreamedAudioPlayback } from "./hooks/useStreamedAudioPlayback";
import type { TranscriptEntry } from "./protocol";

const API_URL = import.meta.env.VITE_API_URL ?? "";

// Survives a reload but not the tab closing, which is exactly the scope the
// wrap-up has: it is reachable while this tab is, and is not linkable or
// listed anywhere. Without it, refreshing the results page — the natural
// reaction to a wrap-up that is taking a while — silently discarded it.
const LAST_SESSION_KEY = "calltrainer.finishedSession";

interface FinishedSession {
  sessionId: string | null;
  turns: TranscriptEntry[];
  /** Carried along because a reload restores this screen without a Persona
   * selection to look the name up in. */
  personaName: string;
}

function loadFinishedSession(): FinishedSession | null {
  try {
    const stored = sessionStorage.getItem(LAST_SESSION_KEY);
    return stored ? (JSON.parse(stored) as FinishedSession) : null;
  } catch {
    return null; // private mode, cleared storage, or an older shape
  }
}

function saveFinishedSession(finished: FinishedSession | null) {
  try {
    if (finished) sessionStorage.setItem(LAST_SESSION_KEY, JSON.stringify(finished));
    else sessionStorage.removeItem(LAST_SESSION_KEY);
  } catch {
    // Storage is a convenience here; the current tab works without it.
  }
}

interface Persona {
  id: string;
  name: string;
  role: string;
}

interface Scenario {
  id: string;
  name: string;
  description: string;
}

type Screen = "setup" | "mic-check" | "call" | "transcript";

export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Lazy initializer: read once on mount, not on every render.
  const [restored] = useState<FinishedSession | null>(loadFinishedSession);
  const [screen, setScreen] = useState<Screen>(restored ? "transcript" : "setup");
  const [transcript, setTranscript] = useState<TranscriptEntry[]>(restored?.turns ?? []);
  // Names the persisted Session so its Feedback can be fetched once the
  // worker has produced it. Not kept anywhere but here: the wrap-up is
  // reachable for as long as this screen is, and no longer.
  const [endedSessionId, setEndedSessionId] = useState<string | null>(restored?.sessionId ?? null);
  // Holds a just-received session.ended until playback actually finishes —
  // see the effect below.
  const [pendingEnd, setPendingEnd] = useState<{
    reason: "user" | "error" | "completed";
    turns: TranscriptEntry[];
    sessionId: string | null;
  } | null>(null);
  const personaName =
    personas.find((p) => p.id === personaId)?.name ?? restored?.personaName ?? "Persona";
  // Forces a fresh Session even when persona/scenario didn't change — bumped
  // right when a call ends normally, so the *next* Session (and its opening
  // line) starts pre-warming immediately, before the user has asked for it.
  const [generation, setGeneration] = useState(0);
  // True right after an error ending, until the user explicitly restarts.
  // Without this, a persistently-failing backend (e.g. the LLM gateway
  // rejecting every request) would auto-pre-warm again immediately, fail
  // again immediately, and loop forever with no backoff — confirmed in
  // production as a tight reconnect storm. An error ending is therefore NOT
  // auto-retried; only a deliberate "Neue Session starten" click reconnects.
  const [needsReconnect, setNeedsReconnect] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/api/personas`)
      .then((r) => r.json())
      .then((data: Persona[]) => {
        setPersonas(data);
        if (data.length > 0) setPersonaId(data[0].id);
      })
      .catch((e) => setLoadError(`Personas konnten nicht geladen werden: ${e.message}`));
    fetch(`${API_URL}/api/scenarios`)
      .then((r) => r.json())
      .then((data: Scenario[]) => {
        setScenarios(data);
        if (data.length > 0) setScenarioId(data[0].id);
      })
      .catch((e) => setLoadError(`Szenarien konnten nicht geladen werden: ${e.message}`));
  }, []);

  // The Session (WebSocket + VAD + audio playback) lives here, at the App
  // level, not inside whichever screen happens to be showing — it connects
  // as soon as personaId/scenarioId are known (i.e. on app load, well before
  // "Session starten" is ever clicked) and its opening line is buffered
  // (see useStreamedAudioPlayback's hold/activate) until the call screen
  // actually appears. Speed matters more than a literal "screen order"
  // mapping: anything that can be anticipated runs in the background.
  const playback = useStreamedAudioPlayback();

  // session.ended (e.g. after a natural [CALL_END]) can arrive while the
  // Persona's closing line is still playing out — the server sends it the
  // moment the reply's Turn completes, independent of local audio playback
  // timing. Don't tear the Session down immediately: stash it and let the
  // effect below act on it once the tail audio has actually finished, so
  // the goodbye is heard instead of getting cut off mid-sentence. This only
  // applies to natural/error endings — when the user clicks "Anruf
  // beenden", the call ends immediately instead (see the effect below).
  const handleEnded = useCallback(
    (reason: "user" | "error" | "completed", turns: TranscriptEntry[], sessionId: string | null) => {
      setPendingEnd({ reason, turns, sessionId });
    },
    [],
  );

  const socket = useSessionSocket({
    personaId,
    scenarioId,
    generation,
    onAudioChunk: playback.enqueue,
    onEnded: handleEnded,
  });

  useEffect(() => {
    if (pendingEnd === null) return;
    // A user-initiated end should cut the call immediately, not let the
    // Persona's audio keep playing out — only natural/error endings wait
    // for the tail audio to finish (see handleEnded above).
    if (pendingEnd.reason !== "user" && playback.isPlaying) return;
    playback.reset();
    setTranscript(pendingEnd.turns);
    setEndedSessionId(pendingEnd.sessionId);
    saveFinishedSession({ sessionId: pendingEnd.sessionId, turns: pendingEnd.turns, personaName });
    setScreen("transcript");
    if (pendingEnd.reason === "error") {
      setNeedsReconnect(true);
    } else {
      setGeneration((g) => g + 1);
    }
    setPendingEnd(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- playback is stable-shaped; only isPlaying/pendingEnd should retrigger this
  }, [pendingEnd, playback.isPlaying]);

  // The server sends state:"listening" the moment the Turn completes, but
  // the Persona's last audio chunk(s) can still be playing out locally —
  // hold the displayed state at "speaking" until playback actually finishes.
  const displayState = socket.callState === "listening" && playback.isPlaying ? "speaking" : socket.callState;

  // useMicrophoneVAD wires onSpeechStart into MicVAD only once (see its
  // initRef guard), so handleBargeIn below must read fresh state via a ref.
  const displayStateRef = useRef(displayState);
  displayStateRef.current = displayState;

  // Barge-in trigger (see useMicrophoneVAD for the actual filtering).
  // Stable ([]) so startListening/stopListening below don't churn either.
  const handleBargeIn = useCallback(() => {
    if (displayStateRef.current === "listening") return;
    playback.interrupt();
    socket.sendInterrupt();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- see comment above
  }, []);

  const vad = useMicrophoneVAD(handleBargeIn, socket.sendTurnAudio);

  useEffect(() => {
    vad.preload();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- preload once, on mount
  }, []);

  // Armed for the whole call, not just while it's nominally the user's turn
  // — see the barge-in handling above.
  useEffect(() => {
    if (screen !== "call") {
      vad.stopListening();
      return;
    }
    void vad.startListening();
    return () => vad.stopListening();
  }, [screen, vad.startListening, vad.stopListening]);

  const handleConfirmed = useCallback(() => {
    // Reveal whatever's already been generated (possibly the whole opening
    // line by now) and switch to live playback for everything after. The
    // server is told at the same moment, because this — not the connect —
    // is where the Session's timeline starts (ADR 0048).
    playback.activate();
    socket.sendActivate();
    setScreen("call");
  }, [playback, socket.sendActivate]);

  const handleRestart = useCallback(() => {
    saveFinishedSession(null);
    if (needsReconnect) {
      setGeneration((g) => g + 1);
      setNeedsReconnect(false);
    }
    setScreen("setup");
  }, [needsReconnect]);

  const readyForCall = personaId !== null && scenarioId !== null;

  if (screen === "mic-check") {
    return <MicCheck onConfirmed={handleConfirmed} onCancel={() => setScreen("setup")} />;
  }

  if (screen === "call") {
    return (
      <CallView
        callState={displayState}
        error={socket.error ?? vad.micError}
        onEndCall={socket.endSession}
      />
    );
  }

  if (screen === "transcript") {
    return (
      <TranscriptView
        transcript={transcript}
        personaName={personaName}
        onRestart={handleRestart}
        feedback={<FeedbackView sessionId={endedSessionId} />}
      />
    );
  }

  return (
    <>
      <div className="eyebrow">Calltrainer</div>
      <h1>Training starten</h1>

      <h2>Persona</h2>
      <div className="persona-grid">
        {personas.map((p) => (
          <button
            key={p.id}
            className={"persona-card" + (p.id === personaId ? " selected" : "")}
            onClick={() => setPersonaId(p.id)}
            type="button"
          >
            <span className="persona-name">{p.name}</span>
            <span className="card-subtitle">{p.role}</span>
          </button>
        ))}
      </div>

      <h2>Szenario</h2>
      <div className="persona-grid">
        {scenarios.map((s) => (
          <button
            key={s.id}
            className={"persona-card" + (s.id === scenarioId ? " selected" : "")}
            onClick={() => setScenarioId(s.id)}
            type="button"
          >
            <span className="persona-name">{s.name}</span>
            <span className="card-subtitle">{s.description}</span>
          </button>
        ))}
      </div>

      <button
        className="start-call-button"
        type="button"
        disabled={!readyForCall}
        onClick={() => setScreen("mic-check")}
      >
        Session starten
      </button>

      {loadError && (
        <p id="status" className="error">
          {loadError}
        </p>
      )}
    </>
  );
}
