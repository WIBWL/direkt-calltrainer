import { useCallback, useEffect, useRef, useState } from "react";

import { apiFetch } from "./api";
import AppFooter from "./components/AppFooter";
import AppHeader from "./components/AppHeader";
import CallView from "./components/CallView";
import FeedbackView from "./components/FeedbackView";
import MicCheck from "./components/MicCheck";
import SelectionSummary from "./components/SelectionSummary";
import SetupSection from "./components/SetupSection";
import TranscriptView from "./components/TranscriptView";
import { useMicrophoneVAD } from "./hooks/useMicrophoneVAD";
import { useSessionSocket, type CommittedSession } from "./hooks/useSessionSocket";
import { useStreamedAudioPlayback } from "./hooks/useStreamedAudioPlayback";
import type { TranscriptEntry } from "./protocol";

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
  // A Persona speaks exactly one language and the user cannot change it
  // (ADR 0043), so the card has to say which one it is.
  language: string;
}

interface Scenario {
  id: string;
  name: string;
  // The short teaser, not the call context the model gets.
  short_description: string;
}

type Screen = "setup" | "mic-check" | "call" | "transcript";

export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Tracks intentional muting separately from entering or leaving the call screen.
  const [isMicrophoneMuted, setIsMicrophoneMuted] = useState(false);
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
  // The committed Session: set when the user actually commits to one (the
  // "Session starten" click), never by the selection itself — see ADR 0042.
  // Nothing connects on its own, which is also what keeps a persistently
  // failing backend from looping: a failed Session is only ever retried by
  // another deliberate click, never automatically.
  const [committed, setCommitted] = useState<CommittedSession | null>(null);

  useEffect(() => {
  apiFetch<Persona[]>("/api/personas")
    .then((data) => {
      setPersonas(data);
      if (!restored && data[0]) setPersonaId(data[0].id);
    })
    .catch((e) =>
      setLoadError(`Personas konnten nicht geladen werden: ${e.message}`)
    );

  apiFetch<Scenario[]>("/api/scenarios")
    .then((data) => {
      setScenarios(data);
      if (!restored && data[0]) setScenarioId(data[0].id);
    })
    .catch((e) =>
      setLoadError(`Szenarien konnten nicht geladen werden: ${e.message}`)
    );
}, [restored]);

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
  const handleEnded = useCallback(
    (reason: "user" | "error" | "completed", turns: TranscriptEntry[], sessionId: string | null) => {
      setPendingEnd({ reason, turns, sessionId });
    },
    [],
  );

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
    setEndedSessionId(pendingEnd.sessionId);
    saveFinishedSession({ sessionId: pendingEnd.sessionId, turns: pendingEnd.turns, personaName });
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
    const playedMs = playback.interrupt();
    socket.sendInterrupt(playedMs);
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
    if (screen !== "call" || isMicrophoneMuted) {
      // Pausing keeps the preloaded VAD instance warm without capturing speech.
      vad.stopListening();
      return;
    }

    void vad.startListening();
    return () => vad.stopListening();
  }, [isMicrophoneMuted, screen, vad.startListening, vad.stopListening]);

  const handleConfirmed = useCallback(() => {
    // Reveal the buffered opening line and switch to live playback.
    // This is also the point at which the Session timeline starts.
    setIsMicrophoneMuted(false);
    playback.activate();
    socket.sendActivate();
    setScreen("call");
  }, [playback, socket.sendActivate]);

  // The effect above owns VAD pause/resume; the button only changes UI state.
  const handleToggleMicrophone = useCallback(() => {
    setIsMicrophoneMuted((muted) => !muted);
  }, []);

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

  // Clears the stored finished Session too, so the wrap-up does not come
  // back when the next Session ends (ADR 0042 handles the reconnect side).
  const handleRestart = useCallback(() => {
    saveFinishedSession(null);
    setScreen("setup");
  }, []);

  const selectedPersona = personas.find((persona) => persona.id === personaId);
  const selectedScenario = scenarios.find((scenario) => scenario.id === scenarioId);

  const readyForCall = personaId !== null && scenarioId !== null;

  if (screen === "mic-check") {
    return (
      <>
        <AppHeader activeStep="prepare" />

        <main className="app-page mic-check-page">
          <MicCheck onConfirmed={handleConfirmed} onCancel={handleCancelMicCheck} />
        </main>

        <AppFooter />
      </>
    );
  }

  if (screen === "call") {
    return (
      <>
        <AppHeader activeStep="call" />

        <main className="app-page call-page">
          <CallView
            scenarioName={selectedScenario?.name ?? "Gespräch"}
            personaName={selectedPersona?.name ?? "Persona"}
            personaRole={selectedPersona?.role ?? "Gesprächspartner"}
            languageLabel={selectedPersona?.language ?? "Sprache"}
            isMicrophoneMuted={isMicrophoneMuted}
            callState={displayState}
            audioLevel={playback.audioLevel}
            error={socket.error ?? vad.micError}
            onToggleMicrophone={handleToggleMicrophone}
            onEndCall={socket.endSession}
          />
        </main>

        <AppFooter />
      </>
    );
  }

  if (screen === "transcript") {
    return (
      <>
        <AppHeader activeStep="feedback" />

        <main className="app-page app-page-narrow">
          <TranscriptView
            transcript={transcript}
            personaName={personaName}
            onRestart={handleRestart}
            feedback={<FeedbackView sessionId={endedSessionId} />}
          />
        </main>

        <AppFooter />
      </>
    );
  }

  return (
  <>
    <AppHeader activeStep="prepare" />

    <main className="app-page setup-page">
      <section className="setup-intro" aria-labelledby="setup-page-title">
        <div className="eyebrow">Training vorbereiten</div>

        <h1 id="setup-page-title">Wählen Sie Ihr Kundengespräch</h1>

        <p className="setup-intro-description">
          Wählen Sie die Gesprächssituation und den passenden Gesprächspartner.
          Sprache und Stimme übernimmt die ausgewählte Persona.
        </p>
      </section>

      <SetupSection
        index="01"
        title="Gesprächssituation wählen"
        description="Welche Situation möchten Sie trainieren?"
      >
        <div className="persona-grid">
          {scenarios.map((s) => (
            <button
              key={s.id}
              className={
                "persona-card" + (s.id === scenarioId ? " selected" : "")
              }
              onClick={() => setScenarioId(s.id)}
              type="button"
              aria-pressed={s.id === scenarioId}
            >
              <span className="choice-check" aria-hidden="true">
                {s.id === scenarioId ? "✓" : ""}
              </span>

              <span className="persona-name">{s.name}</span>
              <span className="card-subtitle">{s.short_description}</span>
            </button>
          ))}
        </div>
      </SetupSection>

      <SetupSection
        index="02"
        title="Gesprächspartner auswählen"
        description="Jede Persona besitzt eine eigene Sprache, Stimme und Persönlichkeit."
      >
        <div className="persona-grid">
          {personas.map((p) => (
            <button
              key={p.id}
              className={
                "persona-card" + (p.id === personaId ? " selected" : "")
              }
              onClick={() => setPersonaId(p.id)}
              type="button"
              aria-pressed={p.id === personaId}
            >
              <span className="choice-check" aria-hidden="true">
                {p.id === personaId ? "✓" : ""}
              </span>

              <span className="persona-name">{p.name}</span>
              <span className="card-subtitle">{p.role}</span>
            </button>
          ))}
        </div>
      </SetupSection>

      <SetupSection
        index="03"
        title="Auswahl prüfen"
        description="Ihre Trainingsauswahl steht fest."
      >
        <SelectionSummary
          scenario={selectedScenario?.name ?? "Noch nicht ausgewählt"}
          persona={selectedPersona?.name ?? "Noch nicht ausgewählt"}
          language={selectedPersona?.language ?? "Noch nicht ausgewählt"}
          voice="Durch Persona festgelegt"
        />

        <button
          className="start-call-button"
          type="button"
          disabled={!readyForCall}
          onClick={handleStartSession}
        >
          Weiter zum Mikrofontest
        </button>
      </SetupSection>

      {loadError && (
        <p id="status" className="error">
          {loadError}
        </p>
      )}
    </main>

    <AppFooter />
  </>
);
}