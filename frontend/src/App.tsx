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

type Screen = "setup" | "mic-check" | "call" | "transcript";

export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [languageId, setLanguageId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [screen, setScreen] = useState<Screen>("setup");
  const [transcript, setTranscript] = useState<TurnRecord[]>([]);
  // Forces a fresh Session even when persona/language didn't change — bumped
  // right when a call ends, so the *next* Session (and its opening line)
  // starts pre-warming immediately, before the user has asked for it.
  const [generation, setGeneration] = useState(0);

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
  }, []);

  // The Session (WebSocket + VAD + audio playback) lives here, at the App
  // level, not inside whichever screen happens to be showing — it connects
  // as soon as personaId/languageId are known (i.e. on app load, well before
  // "Session starten" is ever clicked) and its opening line is buffered
  // (see useStreamedAudioPlayback's hold/activate) until the call screen
  // actually appears. Speed matters more than a literal "screen order"
  // mapping: anything that can be anticipated runs in the background.
  const playback = useStreamedAudioPlayback();

  const handleEnded = useCallback(
    (_reason: "user" | "error", turns: TurnRecord[]) => {
      playback.reset();
      setTranscript(turns);
      setScreen("transcript");
      setGeneration((g) => g + 1);
    },
    [playback],
  );

  const socket = useSessionSocket({
    personaId,
    languageId,
    generation,
    onAudioChunk: playback.enqueue,
    onEnded: handleEnded,
  });

  const vad = useMicrophoneVAD(socket.sendTurnAudio);

  useEffect(() => {
    vad.preload();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- preload once, on mount
  }, []);

  // Strict turn-taking (no barge-in): the mic is armed only once we're on the
  // call screen, the server says it's the user's turn, AND the persona's
  // audio has fully played out.
  useEffect(() => {
    if (screen !== "call") return;
    if (socket.callState === "listening" && !playback.isPlaying) {
      void vad.startListening();
    } else {
      vad.stopListening();
    }
  }, [screen, socket.callState, playback.isPlaying, vad.startListening, vad.stopListening]);

  const handleConfirmed = useCallback(() => {
    // Reveal whatever's already been generated (possibly the whole opening
    // line by now) and switch to live playback for everything after.
    playback.activate();
    setScreen("call");
  }, [playback]);

  const readyForCall = personaId !== null && languageId !== null;

  if (screen === "mic-check") {
    return <MicCheck onConfirmed={handleConfirmed} onCancel={() => setScreen("setup")} />;
  }

  if (screen === "call") {
    return (
      <CallView
        callState={socket.callState}
        error={socket.error ?? vad.micError}
        onEndCall={socket.endSession}
      />
    );
  }

  if (screen === "transcript") {
    return <TranscriptView transcript={transcript} onRestart={() => setScreen("setup")} />;
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
