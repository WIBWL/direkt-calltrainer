import { useCallback, useEffect, useState } from "react";

import CallView from "./components/CallView";
import MicCheck from "./components/MicCheck";
import TranscriptView from "./components/TranscriptView";
import { useMicrophoneVAD } from "./hooks/useMicrophoneVAD";
import { useSessionSocket } from "./hooks/useSessionSocket";
import { useStreamedAudioPlayback } from "./hooks/useStreamedAudioPlayback";
import type { TurnRecord } from "./protocol";

const API_URL = import.meta.env.VITE_API_URL ?? "";

interface Persona {
  id: string;
  name: string;
  training_goal: string;
}

interface Language {
  id: string;
  name: string;
}

interface Scenario {
  id: string;
  name: string;
  description: string;
}

type Screen = "setup" | "mic-check" | "call" | "transcript";

export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [languageId, setLanguageId] = useState<string | null>(null);
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
  // Forces a fresh Session even when persona/language didn't change — bumped
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
    fetch(`${API_URL}/api/languages`)
      .then((r) => r.json())
      .then((data: Language[]) => {
        setLanguages(data);
        if (data.length > 0) setLanguageId(data[0].id);
      })
      .catch((e) => setLoadError(`Sprachen konnten nicht geladen werden: ${e.message}`));
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
  // as soon as personaId/languageId are known (i.e. on app load, well before
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
  // the goodbye is heard instead of getting cut off mid-sentence.
  const handleEnded = useCallback((reason: "user" | "error" | "completed", turns: TurnRecord[]) => {
    setPendingEnd({ reason, turns });
  }, []);

  const socket = useSessionSocket({
    personaId,
    languageId,
    scenarioId,
    generation,
    onAudioChunk: playback.enqueue,
    onEnded: handleEnded,
  });

  useEffect(() => {
    if (pendingEnd === null || playback.isPlaying) return;
    playback.reset();
    setTranscript(pendingEnd.turns);
    setScreen("transcript");
    if (pendingEnd.reason === "error") {
      setNeedsReconnect(true);
    } else {
      setGeneration((g) => g + 1);
    }
    setPendingEnd(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- playback is stable-shaped; only isPlaying/pendingEnd should retrigger this
  }, [pendingEnd, playback.isPlaying]);

  // Kept as a defensive no-op rather than removed: with the strict gating
  // below, the mic is never actually armed except during the user's own
  // "listening" Turn, so this should never fire against a live Persona
  // reply. It previously also drove an early-barge-in-during-"thinking"
  // feature, but that let the user's own trailing speech/background noise
  // re-trigger onSpeechStart *after* their Turn was already sent, cancelling
  // their own in-flight reply mid-generation — confusing and unreliable in
  // practice, and full mid-speech barge-in was already ruled out separately
  // (acoustic feedback without a headset, see useMicrophoneVAD). Simplified
  // back to strict turn-taking: the mic is only ever live while "Du bist am
  // Zug" is genuinely true.
  const handleSpeechStart = useCallback(() => {
    playback.stopAll();
    socket.sendInterrupt();
  }, [playback, socket]);

  const vad = useMicrophoneVAD(socket.sendTurnAudio, handleSpeechStart);

  useEffect(() => {
    vad.preload();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- preload once, on mount
  }, []);

  // Strict turn-taking: armed only while it's genuinely the user's turn —
  // callState is "listening" AND the Persona's audio has fully finished
  // playing (not just server-side Turn completion, see displayState below).
  // Everywhere else (including "thinking"), the mic stays off.
  useEffect(() => {
    if (screen !== "call" || socket.callState !== "listening" || playback.isPlaying) {
      vad.stopListening();
      return;
    }
    void vad.startListening();
    return () => vad.stopListening();
  }, [screen, socket.callState, playback.isPlaying, vad.startListening, vad.stopListening]);

  const handleConfirmed = useCallback(() => {
    // Reveal whatever's already been generated (possibly the whole opening
    // line by now) and switch to live playback for everything after.
    playback.activate();
    setScreen("call");
  }, [playback]);

  const handleRestart = useCallback(() => {
    if (needsReconnect) {
      setGeneration((g) => g + 1);
      setNeedsReconnect(false);
    }
    setScreen("setup");
  }, [needsReconnect]);

  const readyForCall = personaId !== null && languageId !== null && scenarioId !== null;

  // The server sends state:"listening" the moment the Turn completes
  // server-side — but the Persona's last audio chunk(s) can still be
  // playing out locally for a bit after that (same root cause as the
  // session.ended/pendingEnd race above, just on every Turn instead of only
  // the last one). Showing "listening" ("Du bist am Zug") already at that
  // point is misleading — the mic isn't even armed yet either, since that's
  // separately gated on !playback.isPlaying — so the displayed state holds
  // at "speaking" until playback actually finishes.
  const displayState = socket.callState === "listening" && playback.isPlaying ? "speaking" : socket.callState;

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
    return <TranscriptView transcript={transcript} onRestart={handleRestart} />;
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
            <span className="persona-goal">{p.training_goal}</span>
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
            <span className="persona-goal">{s.description}</span>
          </button>
        ))}
      </div>

      <h2>Sprache</h2>
      <div className="language-row">
        {languages.map((l) => (
          <button
            key={l.id}
            className={"language-pill" + (l.id === languageId ? " selected" : "")}
            onClick={() => setLanguageId(l.id)}
            type="button"
          >
            {l.name}
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
