import { useCallback, useEffect, useRef, useState } from "react";

import CallView from "./components/CallView";
import MicCheck from "./components/MicCheck";
import TranscriptView from "./components/TranscriptView";
import { useMicrophoneVAD } from "./hooks/useMicrophoneVAD";
import { useSessionSocket, type CommittedSession } from "./hooks/useSessionSocket";
import { useStreamedAudioPlayback } from "./hooks/useStreamedAudioPlayback";
import type { TurnRecord } from "./protocol";

const API_URL = import.meta.env.VITE_API_URL ?? "";

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
  const [screen, setScreen] = useState<Screen>("setup");
  const [transcript, setTranscript] = useState<TurnRecord[]>([]);
  // Holds a just-received session.ended until playback actually finishes —
  // see the effect below.
  const [pendingEnd, setPendingEnd] = useState<{
    reason: "user" | "error" | "completed";
    turns: TurnRecord[];
  } | null>(null);
  // The committed Session: set when the user actually commits to one (the
  // "Session starten" click), never by the selection itself — see ADR 0042.
  // Nothing connects on its own, which is also what keeps a persistently
  // failing backend from looping: a failed Session is only ever retried by
  // another deliberate click, never automatically.
  const [committed, setCommitted] = useState<CommittedSession | null>(null);

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
  // once the user commits to a Session, and its opening line is generated
  // and buffered (see useStreamedAudioPlayback's hold/activate) while the
  // microphone check is still on screen, so the Persona can start speaking
  // the moment the call screen appears (ADR 0042).
  const playback = useStreamedAudioPlayback();

  // session.ended (e.g. after a natural [CALL_END]) can arrive while the
  // Persona's closing line is still playing out — the server sends it the
  // moment the reply's Turn completes, independent of local audio playback
  // timing. Don't tear the Session down immediately: stash it and let the
  // effect below act on it once the tail audio has actually finished, so
  // the goodbye is heard instead of getting cut off mid-sentence. This only
  // applies to natural/error endings — when the user clicks "Anruf
  // beenden", the call ends immediately instead (see the effect below).
  const handleEnded = useCallback((reason: "user" | "error" | "completed", turns: TurnRecord[]) => {
    setPendingEnd({ reason, turns });
  }, []);

  const socket = useSessionSocket({
    session: committed,
    onAudioChunk: playback.enqueue,
    onEnded: handleEnded,
  });

  // Buffered opening audio belongs to exactly one connection (ADR 0042).
  // Whenever `committed` changes, useSessionSocket above replaces the
  // connection, so whatever the previous one buffered is audio from a
  // Session that will never be conducted — drop it, and go back to holding.
  // Both effects must key on `committed` and nothing else: if they drift
  // apart, activate() starts replaying opening lines from abandoned
  // Sessions back to back.
  useEffect(() => {
    playback.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- playback is stable-shaped; this must mirror the connection key above exactly
  }, [committed]);

  useEffect(() => {
    if (pendingEnd === null) return;
    // A user-initiated end should cut the call immediately, not let the
    // Persona's audio keep playing out — only natural/error endings wait
    // for the tail audio to finish (see handleEnded above).
    if (pendingEnd.reason !== "user" && playback.isPlaying) return;
    playback.reset();
    setTranscript(pendingEnd.turns);
    setScreen("transcript");
    // This Session is over — the next one connects when the user commits
    // to it, not while the transcript is still being read (ADR 0042).
    setCommitted(null);
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
    // line by now) and switch to live playback for everything after.
    playback.activate();
    setScreen("call");
  }, [playback]);

  const handleStartSession = useCallback(() => {
    if (personaId === null || scenarioId === null) return;
    // A new object every time: that identity is what makes this a new
    // Session for useSessionSocket, even when the pairing is unchanged.
    setCommitted({ personaId, scenarioId });
    setScreen("mic-check");
  }, [personaId, scenarioId]);

  // Abandoning the microphone check drops the Session that was committed to
  // — the opening line generated for it is already spent, but there is no
  // point holding the connection (and the server-side Session) open for it.
  const handleCancelMicCheck = useCallback(() => {
    setCommitted(null);
    setScreen("setup");
  }, []);

  const handleRestart = useCallback(() => setScreen("setup"), []);

  const readyForCall = personaId !== null && scenarioId !== null;

  if (screen === "mic-check") {
    return <MicCheck onConfirmed={handleConfirmed} onCancel={handleCancelMicCheck} />;
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
    const personaName = personas.find((p) => p.id === personaId)?.name ?? "Persona";
    return <TranscriptView transcript={transcript} personaName={personaName} onRestart={handleRestart} />;
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
        onClick={handleStartSession}
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
