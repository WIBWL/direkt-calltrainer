import { useCallback, useEffect, useRef, useState } from "react";

import { apiFetch } from "./api";
import AppLayout from "./components/AppLayout";
import CallView from "./components/CallView";
import FeedbackView from "./components/FeedbackView";
import { matchesFilter, type LibraryFilter } from "./components/LibraryPicker";
import MicCheck from "./components/MicCheck";
import ScenarioEditor from "./components/ScenarioEditor";
import SetupView from "./components/SetupView";
import TranscriptView from "./components/TranscriptView";
import { useMicrophoneDevices } from "./hooks/useMicrophoneDevices";
import { useMicrophoneVAD } from "./hooks/useMicrophoneVAD";
import { useSessionSocket, type CommittedSession } from "./hooks/useSessionSocket";
import { useStreamedAudioPlayback } from "./hooks/useStreamedAudioPlayback";
import type { Persona, TranscriptEntry } from "./protocol";
import { getTenant, listScenarios, type ScenarioCard } from "./scenarioLibrary";
import { loadFinishedSession, saveFinishedSession } from "./utils/finishedSession";

type Screen = "setup" | "mic-check" | "call" | "transcript";

interface PendingEnd {
  reason: "user" | "error" | "completed";
  turns: TranscriptEntry[];
  sessionId: string | null;
}

/** null = closed; { id: null } = new; { id } = editing that row. */
type EditorState = { id: string | null } | null;

/**
 * Owns the training flow: which screen is showing, what has been selected, and
 * the live Session behind it. Everything visible is delegated to a screen
 * component — what stays here is the state those screens share.
 */
export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioCard[]>([]);
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [scenarioFilter, setScenarioFilter] = useState<LibraryFilter>("all");
  const [editingScenario, setEditingScenario] = useState<EditorState>(null);
  // The caller's company (ADR 0060); null = default tenant, no company chip.
  const [tenantName, setTenantName] = useState<string | null>(null);
  // Tracks intentional muting separately from entering or leaving the call screen.
  const [isMicrophoneMuted, setIsMicrophoneMuted] = useState(false);
  // The input device picked in the mic-check screen; null = browser default.
  // Carries over into the call the same way isMicrophoneMuted does.
  const [micDeviceId, setMicDeviceId] = useState<string | null>(null);
  const { devices: micDevices, refresh: refreshMicDevices } = useMicrophoneDevices();
  // Lazy initializer: read once on mount, not on every render.
  const [restored] = useState(loadFinishedSession);
  const [screen, setScreen] = useState<Screen>(restored ? "transcript" : "setup");
  const [transcript, setTranscript] = useState<TranscriptEntry[]>(restored?.turns ?? []);
  // Names the persisted Session so its Feedback can be fetched once the
  // worker has produced it. Not kept anywhere but here: the wrap-up is
  // reachable for as long as this screen is, and no longer.
  const [endedSessionId, setEndedSessionId] = useState<string | null>(restored?.sessionId ?? null);
  // Holds a just-received session.ended until playback actually finishes —
  // see the effect below.
  const [pendingEnd, setPendingEnd] = useState<PendingEnd | null>(null);
  // The committed Session: set when the user actually commits to one (the
  // "Session starten" click), never by the selection itself — see ADR 0042.
  // Nothing connects on its own, which is also what keeps a persistently
  // failing backend from looping: a failed Session is only ever retried by
  // another deliberate click, never automatically.
  const [committed, setCommitted] = useState<CommittedSession | null>(null);

  // Reloaded after the user creates, edits, shares or deletes a row, so a
  // refetch shows the change without a full page reload. `select` (when passed)
  // is the id to select next — the saved row, or the first remaining one if it
  // was deleted.
  const reloadScenarios = useCallback(
    (select?: string | null) =>
      listScenarios()
        .then((data) => {
          setScenarios(data);
          if (select !== undefined) setScenarioId(select ?? data[0]?.id ?? null);
        })
        .catch((e) =>
          setLoadError(`Szenarien konnten nicht geladen werden: ${e.message}`),
        ),
    [],
  );

  const selectedPersona = personas.find((persona) => persona.id === personaId) ?? null;
  const selectedScenario = scenarios.find((scenario) => scenario.id === scenarioId) ?? null;
  // A reload restores the post-call screen without a selection to look the
  // name up in, so the stored one stands in.
  const personaName = selectedPersona?.name ?? restored?.personaName ?? "Persona";

  // The two lists load independently: either one failing leaves the other
  // usable, and names itself in the error line. A restored wrap-up owns the
  // screen, so nothing is preselected behind it.
  useEffect(() => {
    apiFetch<Persona[]>("/api/personas")
      .then((data) => {
        setPersonas(data);
        if (!restored && data[0]) setPersonaId(data[0].id);
      })
      .catch((e) =>
        setLoadError(`Personas konnten nicht geladen werden: ${e.message}`),
      );

    listScenarios()
      .then((data) => {
        setScenarios(data);
        if (!restored && data[0]) setScenarioId(data[0].id);
      })
      .catch((e) =>
        setLoadError(`Szenarien konnten nicht geladen werden: ${e.message}`),
      );

    getTenant()
      .then((t) => setTenantName(t.name))
      .catch(() => setTenantName(null)); // no company filter if this fails
  }, [restored]);

  // A selected microphone that gets unplugged (mid-test or mid-call) falls
  // back to the browser default rather than failing every getUserMedia call
  // with a stale exact deviceId from then on.
  useEffect(() => {
    if (micDeviceId !== null && !micDevices.some((d) => d.deviceId === micDeviceId)) {
      setMicDeviceId(null);
    }
  }, [micDevices, micDeviceId]);

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
  // applies to natural/error endings — when the user clicks the end-call
  // button, the call ends immediately instead (see the effect below).
  const handleEnded = useCallback(
    (reason: PendingEnd["reason"], turns: TranscriptEntry[], sessionId: string | null) => {
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
  const displayState =
    socket.callState === "listening" && playback.isPlaying ? "speaking" : socket.callState;

  // useMicrophoneVAD wires onSpeechStart into MicVAD only once (see its
  // initRef guard), so handleBargeIn below must read fresh state via a ref.
  const displayStateRef = useRef(displayState);
  displayStateRef.current = displayState;

  // Barge-in trigger (see useMicrophoneVAD for the actual filtering).
  // Stable ([]) so startListening/stopListening below don't churn either.
  const handleBargeIn = useCallback(() => {
    if (displayStateRef.current === "listening") return;
    socket.sendInterrupt(playback.interrupt());
    // eslint-disable-next-line react-hooks/exhaustive-deps -- see comment above
  }, []);

  const vad = useMicrophoneVAD(handleBargeIn, socket.sendTurnAudio, micDeviceId);

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

  const handleStartSession = useCallback(() => {
    if (personaId === null || scenarioId === null) return;
    // A new object every time: that identity is what makes this a new
    // Session for useSessionSocket, even when the pairing is unchanged.
    setCommitted({ personaId, scenarioId });
    setScreen("mic-check");
  }, [personaId, scenarioId]);

  const handleConfirmed = useCallback(() => {
    // Reveal the buffered opening line and switch to live playback.
    // This is also the point at which the Session timeline starts.
    setIsMicrophoneMuted(false);
    playback.activate();
    socket.sendActivate();
    setScreen("call");
  }, [playback, socket.sendActivate]);

  // Abandoning the microphone check drops the Session that was committed to
  // — the opening line generated for it is already spent, but there is no
  // point holding the connection (and the server-side Session) open for it.
  const handleCancelMicCheck = useCallback(() => {
    setCommitted(null);
    setScreen("setup");
  }, []);

  // The effect above owns VAD pause/resume; the button only changes UI state.
  const handleToggleMicrophone = useCallback(() => {
    setIsMicrophoneMuted((muted) => !muted);
  }, []);

  // Clears the stored finished Session too, so the wrap-up does not come
  // back when the next Session ends (ADR 0042 handles the reconnect side).
  const handleRestart = useCallback(() => {
    saveFinishedSession(null);
    setScreen("setup");
  }, []);

  // The filter chips appear once there is more than just built-ins to filter
  // to — the user authored something, a colleague shared something, or the user
  // is in a company at all.
  const showScenarioFilter =
    tenantName !== null || scenarios.some((s) => s.origin !== "builtin");
  const scenarioItems = scenarios.map((s) => ({
    id: s.id,
    name: s.name,
    subtitle: s.short_description,
    origin: s.origin,
    shared: s.shared,
  }));
  const visibleScenarios = scenarioItems.filter((s) => matchesFilter(s, scenarioFilter));

  const handleScenarioSaved = (savedId: string | null) => {
    setEditingScenario(null);
    void reloadScenarios(savedId);
  };

  if (screen === "mic-check") {
    return (
      <AppLayout step="prepare" pageClassName="mic-check-page">
        <MicCheck
          deviceId={micDeviceId}
          devices={micDevices}
          onDeviceChange={setMicDeviceId}
          onDevicesRefresh={refreshMicDevices}
          onConfirmed={handleConfirmed}
          onCancel={handleCancelMicCheck}
        />
      </AppLayout>
    );
  }

  if (screen === "call") {
    return (
      <AppLayout step="call" pageClassName="call-page">
        <CallView
          scenarioName={selectedScenario?.name ?? "Gespräch"}
          personaName={personaName}
          personaRole={selectedPersona?.role ?? "Gesprächspartner"}
          languageLabel={selectedPersona?.language ?? "Sprache"}
          isMicrophoneMuted={isMicrophoneMuted}
          callState={displayState}
          audioLevel={playback.audioLevel}
          error={socket.error ?? vad.micError}
          onToggleMicrophone={handleToggleMicrophone}
          onEndCall={socket.endSession}
        />
      </AppLayout>
    );
  }

  if (screen === "transcript") {
    return (
      <AppLayout step="feedback" pageClassName="app-page-narrow">
        <TranscriptView
          transcript={transcript}
          personaName={personaName}
          onRestart={handleRestart}
          feedback={<FeedbackView sessionId={endedSessionId} />}
        />
      </AppLayout>
    );
  }

  return (
    <AppLayout step="prepare" pageClassName="setup-page">
      <SetupView
        scenarioItems={visibleScenarios}
        scenarioId={scenarioId}
        scenarioFilter={scenarioFilter}
        onScenarioFilter={setScenarioFilter}
        showScenarioFilter={showScenarioFilter}
        tenantName={tenantName}
        onNewScenario={() => setEditingScenario({ id: null })}
        onEditScenario={(id) => setEditingScenario({ id })}
        personas={personas}
        personaId={personaId}
        selectedScenario={selectedScenario}
        selectedPersona={selectedPersona}
        loadError={loadError}
        onSelectScenario={setScenarioId}
        onSelectPersona={setPersonaId}
        onStart={handleStartSession}
      />

      {editingScenario && (
        <ScenarioEditor
          scenarioId={editingScenario.id}
          tenantName={tenantName}
          onClose={() => setEditingScenario(null)}
          onSaved={handleScenarioSaved}
          onRefresh={() => void reloadScenarios()}
        />
      )}
    </AppLayout>
  );
}
