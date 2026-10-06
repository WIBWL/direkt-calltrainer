import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import CallView, { type BriefPlacement } from "./components/CallView";
import CaseBriefPanel from "./components/CaseBriefPanel";
import DiceRoll from "./components/DiceRoll";
import IncomingCall from "./components/IncomingCall";
import BriefScreen from "./components/BriefScreen";
import FeedbackView from "./components/FeedbackView";
import FeedbackWaiting from "./components/FeedbackWaiting";
import MicCheck from "./components/MicCheck";
import PersonaInfo from "./components/PersonaInfo";
import ScenarioEditor from "./components/ScenarioEditor";
import ScenarioInfo from "./components/ScenarioInfo";
import { useScreenTransition } from "./components/ScreenTransition";
import SetupView from "./components/SetupView";
import FeedbackScreen from "./components/FeedbackScreen";
import { useMicrophoneDevices } from "./hooks/useMicrophoneDevices";
import { useMicrophoneVAD } from "./hooks/useMicrophoneVAD";
import { useLiveCall, type EndedCall } from "./hooks/useLiveCall";
import { useNextCalls } from "./hooks/useNextCalls";
import { useScenarioLibrary } from "./hooks/useScenarioLibrary";
import NextCalls from "./components/NextCalls";
import { useSessionFeedback } from "./hooks/useSessionFeedback";
import { useTrainingRun, type CommitOptions } from "./hooks/useTrainingRun";
import { listPersonas } from "./personas";
import type { Persona } from "./protocol";
import ReverseBriefPanel from "./components/ReverseBriefPanel";
import { ROUTES, type TrainingStart } from "./routes";
import {
  briefingFollows,
  nextScreen,
  type FlowContext,
  type FlowEvent,
  type Screen,
} from "./trainingFlow";
import {
  drawRandomScenario,
  getTenant,
  RANDOM_SCENARIO_ID,
  type ReverseScenario,
} from "./scenarioLibrary";
import { prefersReducedMotion } from "./utils/motion";

/** How long the die shows (F-62); the Session is already connecting behind it. */
const ROLL_MS = 2000;

/** null = closed; { id: null } = new; { id } = editing that row. */
type EditorState = { id: string | null } | null;

/** The training flow's shared state; every screen is its own component. */
export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editingScenario, setEditingScenario] = useState<EditorState>(null);
  const [infoPersonaId, setInfoPersonaId] = useState<string | null>(null);
  // Editing starts from the info panel (ADR 0062).
  const [infoScenarioId, setInfoScenarioId] = useState<string | null>(null);
  // ADR 0060; null = default tenant.
  const [tenantName, setTenantName] = useState<string | null>(null);
  const [isMicrophoneMuted, setIsMicrophoneMuted] = useState(false);
  // null = browser default.
  const [micDeviceId, setMicDeviceId] = useState<string | null>(null);
  const { devices: micDevices, refresh: refreshMicDevices } = useMicrophoneDevices();
  const { playFade } = useScreenTransition();
  const run = useTrainingRun();
  const {
    restored,
    committed,
    lastPlayed,
    secretScenario,
    committedCase,
    reverseBrief,
    transcript,
    endedSessionId,
    commit,
    cancel: cancelRun,
    restart: restartRun,
  } = run;
  const [screen, setScreen] = useState<Screen>(restored ? "transcript" : "setup");
  // Polled once for the waiting screen, the post-call screen and the report
  // (F-64), so the file carries what the page shows.
  const {
    detail: endedSessionDetail,
    state: feedbackState,
    restart: restartFeedbackPoll,
  } = useSessionFeedback(
    screen === "analysing" || screen === "transcript" ? endedSessionId : null,
  );
  const nextCalls = useNextCalls(
    lastPlayed?.scenarioId ?? null,
    lastPlayed?.personaId ?? null,
    screen === "transcript",
  );

  // A restored wrap-up owns the screen, so nothing is preselected behind it.
  const library = useScenarioLibrary(!restored);
  const {
    scenarioId,
    select: setScenarioId,
    selected: selectedScenario,
    pool: drawPool,
    reload: reloadScenarios,
    remove: handleRemoveScenario,
    setFilters: setScenarioFilters,
  } = library;

  const selectedPersona = personas.find((persona) => persona.id === personaId) ?? null;

  // After a reload there is no selection, so the stored names stand in.
  const personaName = selectedPersona?.name ?? restored?.personaName ?? "Persona";
  const scenarioName = selectedScenario?.name ?? restored?.scenarioName ?? null;

  // Apart from the library, so either can fail alone.
  useEffect(() => {
    listPersonas()
      .then((data) => {
        setPersonas(data);
        if (!restored && data[0]) setPersonaId(data[0].id);
      })
      .catch((e) =>
        setLoadError(`Personas konnten nicht geladen werden: ${e.message}`),
      );

    getTenant()
      .then((t) => setTenantName(t.name))
      .catch(() => setTenantName(null)); // no company filter if this fails
  }, [restored]);

  // An unplugged microphone falls back to the default instead of a stale deviceId.
  useEffect(() => {
    if (micDeviceId !== null && !micDevices.some((d) => d.deviceId === micDeviceId)) {
      setMicDeviceId(null);
    }
  }, [micDevices, micDeviceId]);

  // Read only from handlers, so `advance` keeps one identity: the waiting
  // screen's patience timer would restart on a new one.
  const flowRef = useRef<Omit<FlowContext, "reducedMotion">>({
    reverse: false,
    drawn: false,
    committedCase: null,
  });
  flowRef.current = {
    reverse: committed?.reverse === true,
    drawn: secretScenario !== null,
    committedCase,
  };
  const flowContext = (): FlowContext => ({
    ...flowRef.current,
    reducedMotion: prefersReducedMotion(),
  });

  /** The only way the screen changes (`trainingFlow.nextScreen`). */
  const advance = useCallback(
    (event: FlowEvent) => {
      const context: FlowContext = {
        ...flowRef.current,
        reducedMotion: prefersReducedMotion(),
      };
      const { screen: next, cut } = nextScreen(context, event);
      if (cut === "fade") playFade(() => setScreen(next));
      else setScreen(next);
    },
    [playFade],
  );

  const handleCallOver = (ended: EndedCall) => {
    // Kept for a reload; the Persona's id so a reverse still knows who answers (ADR 0070).
    run.finish(ended, { personaName, scenarioName, personaId });
    // No stored Session, no wrap-up to wait for (ADR 0066).
    advance({ type: "callEnded", stored: ended.sessionId !== null });
  };

  // At App level: it connects on commit and buffers a reverse's opening during
  // the mic check (ADR 0042).
  const call = useLiveCall(committed, handleCallOver);
  const { accept } = call;

  const vad = useMicrophoneVAD(call.bargeIn, call.sendTurnAudio, micDeviceId);

  useEffect(() => {
    vad.preload();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- preload once, on mount
  }, []);

  // Armed for the whole call, for barge-in.
  const { startListening, stopListening } = vad;
  useEffect(() => {
    if (screen !== "call" || isMicrophoneMuted) {
      // Keeps the preloaded VAD warm without capturing speech.
      stopListening();
      return;
    }

    void startListening();
    return () => stopListening();
  }, [isMicrophoneMuted, screen, startListening, stopListening]);

  // The one way into a call, from setup and from a finished training alike.
  // `commit` forgets the stored finished Session.
  const beginSession = useCallback(
    (
      nextScenarioId: string,
      nextPersonaId: string,
      { skipMicCheck = false, ...options }: CommitOptions & { skipMicCheck?: boolean } = {},
    ) => {
      const reverse = options.reverse ?? false;
      setScenarioId(nextScenarioId);
      setPersonaId(nextPersonaId);
      commit(nextScenarioId, nextPersonaId, options);
      // After a training the microphone was just in use; the case screen is never skipped.
      advance({ type: "sessionCommitted", reverse, skipMicCheck });
      if (skipMicCheck) setIsMicrophoneMuted(false);
    },
    [advance, setScenarioId, commit],
  );

  const handleStartSession = useCallback(() => {
    if (personaId === null || scenarioId === null) return;

    // Drawn here, not on selection, or each change of Persona would redraw (F-62).
    if (scenarioId === RANDOM_SCENARIO_ID) {
      const drawn = drawRandomScenario(drawPool);
      if (drawn === null) return; // nothing to draw from; the tile is not offered
      beginSession(drawn.id, personaId, { drawnName: drawn.name });
      return;
    }

    beginSession(scenarioId, personaId, { reverse: selectedScenario?.reverse ?? false });
  }, [personaId, scenarioId, drawPool, selectedScenario, beginSession]);

  // F-61 (ADR 0070): same Persona, new Scenario, onto the briefing screen.
  const handleReverse = useCallback(
    (reverse: ReverseScenario) => {
      const persona = personaId ?? restored?.personaId ?? null;
      if (persona === null) return;
      setScenarioFilters({ origin: "reverse", category: "all" });
      void reloadScenarios();
      // Seeded from the answer, so the briefing shows at once.
      beginSession(reverse.id, persona, {
        reverse: true,
        skipMicCheck: true,
        brief: reverse.reverse_brief,
      });
    },
    [personaId, restored, reloadScenarios, setScenarioFilters, beginSession],
  );

  const handleConfirmed = useCallback(() => {
    // In a reverse this reveals the buffered answering line (ADR 0042, 0110).
    setIsMicrophoneMuted(false);
    accept();
    advance({ type: "callAccepted" });
  }, [accept, advance]);

  // The label asks `briefingFollows` too, so the two cannot disagree.
  const handleMicConfirmed = useCallback(() => {
    advance({ type: "micConfirmed" });
  }, [advance]);

  // A follow-up lands here before its case is fetched; move on once it is.
  useEffect(() => {
    if (screen !== "case-brief" || committedCase === null) return;
    if (committedCase.briefing || committedCase.facts) return;
    advance({ type: "caseArrivedEmpty" });
  }, [screen, committedCase, advance]);

  useEffect(() => {
    if (screen !== "rolling") return undefined;
    const timer = window.setTimeout(() => advance({ type: "rollFinished" }), ROLL_MS);
    return () => window.clearTimeout(timer);
  }, [screen, advance]);

  const handleCancelMicCheck = useCallback(() => {
    cancelRun();
    advance({ type: "micCheckCancelled" });
  }, [advance, cancelRun]);

  const handleToggleMicrophone = useCallback(() => {
    setIsMicrophoneMuted((muted) => !muted);
  }, []);

  // Stable: the waiting screen's patience limit hangs off it.
  const handleAnalysed = useCallback(() => {
    advance({ type: "analysed" });
  }, [advance]);

  // Clears the stored finished Session, or the wrap-up comes back.
  const handleRestart = useCallback(() => {
    restartRun();
    advance({ type: "restarted" });
  }, [advance, restartRun]);

  // F-60/F-61. `reverse` is passed in: a wrong guess would skip the briefing.
  const handleStartFollowUp = useCallback(
    (followUpId: string, followUpPersonaId: string, reverse = false) => {
      void reloadScenarios();
      // Skips the mic check, not the case.
      playFade(() => beginSession(followUpId, followUpPersonaId, { reverse, skipMicCheck: true }));
    },
    [reloadScenarios, beginSession, playFade],
  );

  // The same from a past training, handed over in router state and cleared at
  // once so neither reload nor Back starts a second call. The ref guards
  // against React's double-invoked effects.
  const location = useLocation();
  const navigate = useNavigate();
  const handedOver = useRef(false);

  useEffect(() => {
    const start = (location.state as { start?: TrainingStart } | null)?.start;
    if (!start || handedOver.current) return;
    handedOver.current = true;
    navigate(ROUTES.training, { replace: true, state: null });
    handleStartFollowUp(start.scenarioId, start.personaId, start.reverse ?? false);
  }, [location.state, navigate, handleStartFollowUp]);

  const handleScenarioSaved = (savedId: string | null) => {
    setEditingScenario(null);
    void reloadScenarios(savedId);
  };

  // Looked up, so a reloaded list cannot leave a stale name.
  const infoPersona = personas.find((p) => p.id === infoPersonaId) ?? null;
  const infoScenario = library.scenarios.find((s) => s.id === infoScenarioId) ?? null;

  // Cancel in the editor returns to the library, not the panel.
  const handleEditFromInfo = (id: string) => {
    setInfoScenarioId(null);
    setEditingScenario({ id });
  };

  // Closed first, or its request finishes against a 404.
  const handleDeleteFromInfo = (id: string) => {
    setInfoScenarioId(null);
    handleRemoveScenario(id);
  };

  const scenarioEditor = editingScenario && (
    <ScenarioEditor
      scenarioId={editingScenario.id}
      tenantName={tenantName}
      onClose={() => setEditingScenario(null)}
      onSaved={handleScenarioSaved}
      onRefresh={() => void reloadScenarios()}
    />
  );

  // The slot is claimed before the briefing arrives, or a late panel moves the call.
  const briefPanel = (variant: "prepare" | "call") => {
    if (!committed?.reverse) {
      // Read from the committed case, never the selected card (they differ for a follow-up).
      return (
        <CaseBriefPanel
          briefing={committedCase?.briefing}
          caseFacts={committedCase?.facts}
          variant={variant}
        />
      );
    }
    if (!reverseBrief) {
      return (
        <section
          className={`reverse-brief reverse-brief-${variant}`}
          aria-labelledby="reverse-brief-loading-title"
        >
          <h2 id="reverse-brief-loading-title" className="reverse-brief-title">
            Sie rufen an
          </h2>
          <p className="reverse-brief-lead">Unterlagen werden geladen …</p>
        </section>
      );
    }
    return <ReverseBriefPanel brief={reverseBrief} variant={variant} />;
  };

  // A reverse's pre-call screen; it replaces the mic check (ADR 0042).
  if (screen === "brief") {
    return (
      <BriefScreen onContinue={handleConfirmed} onLeave={handleCancelMicCheck}>
        {briefPanel("prepare")}
      </BriefScreen>
    );
  }

  if (screen === "case-brief") {
    return (
      <BriefScreen onContinue={() => advance({ type: "caseRead" })} onLeave={handleCancelMicCheck}>
        {committedCase === null ? (
          <section className="scenario-briefing">
            <h3 className="scenario-briefing-title">Ihre Ausgangslage</h3>
            <p className="scenario-briefing-body">Wird geladen …</p>
          </section>
        ) : (
          <CaseBriefPanel
            briefing={committedCase.briefing}
            caseFacts={committedCase.facts}
            variant="prepare"
          />
        )}
      </BriefScreen>
    );
  }

  if (screen === "rolling") {
    return (
      <AppLayout step="prepare" navigationLocked pageClassName="rolling-page">
        <section className="rolling-panel" aria-live="polite">
          <h1 className="rolling-title">Es wird gewürfelt …</h1>
          <DiceRoll durationMs={ROLL_MS} />
          <p className="rolling-lead">
            Ihr Gespräch wird gleich verbunden. Worum es geht, erfahren Sie von Ihrem
            Gegenüber.
          </p>
        </section>
      </AppLayout>
    );
  }

  if (screen === "mic-check") {
    // The same function the press goes through; may flip once the case arrives.
    const nextIsBriefing = briefingFollows(flowContext());
    return (
      <AppLayout step="prepare" navigationLocked pageClassName="mic-check-page">
        <MicCheck
          deviceId={micDeviceId}
          devices={micDevices}
          onDeviceChange={setMicDeviceId}
          onDevicesRefresh={refreshMicDevices}
          onConfirmed={handleMicConfirmed}
          onCancel={handleCancelMicCheck}
          briefingFollows={nextIsBriefing}
        />
      </AppLayout>
    );
  }

  if (screen === "incoming") {
    return (
      <AppLayout step="prepare" navigationLocked pageClassName="incoming-page">
        <IncomingCall
          personaName={personaName}
          personaAvatarUrl={selectedPersona?.avatar_url ?? null}
          onAccept={handleConfirmed}
          onDecline={handleCancelMicCheck}
        />
      </AppLayout>
    );
  }

  if (screen === "call") {
    // A reverse's briefing sits beside the call, an ordinary case below it.
    const briefPlacement: BriefPlacement | null = committed?.reverse
      ? "beside"
      : committedCase?.briefing.trim() || committedCase?.facts.trim()
        ? "below"
        : null;
    return (
      <AppLayout
        step="call"
        navigationLocked
        pageClassName={briefPlacement === "beside" ? "call-page call-page-wide" : "call-page"}
      >
        <CallView
          personaName={personaName}
          // A reverse's Persona is on the company's side (ADR 0070).
          personaRole={
            committed?.reverse
              ? "Nimmt Ihren Anruf entgegen"
              : selectedPersona?.role ?? "Gesprächspartner"
          }
          personaAvatarUrl={selectedPersona?.avatar_url ?? null}
          isMicrophoneMuted={isMicrophoneMuted}
          callState={call.displayState}
          audioLevel={call.audioLevel}
          error={call.error ?? vad.micError}
          onToggleMicrophone={handleToggleMicrophone}
          onEndCall={call.endCall}
          brief={
            briefPlacement
              ? { content: briefPanel("call"), placement: briefPlacement }
              : null
          }
        />
      </AppLayout>
    );
  }

  if (screen === "analysing") {
    return (
      <AppLayout
        step="feedback"
        onHome={handleRestart}
        pageClassName="feedback-page"
      >
        <FeedbackWaiting state={feedbackState} onDone={handleAnalysed} />
      </AppLayout>
    );
  }

  if (screen === "transcript") {
    return (
      // These screens are state under the training route, so the brand behaves like the button.
      <AppLayout
        step="feedback"
        onHome={handleRestart}
        pageClassName="feedback-page"
      >
        <FeedbackScreen
          transcript={transcript}
          personaName={personaName}
          scenarioName={scenarioName}
          detail={endedSessionDetail}
          actions={
            <button className="back-to-start-button" type="button" onClick={handleRestart}>
              Zur Vorbereitung
            </button>
          }
          feedback={
            <FeedbackView
              detail={endedSessionDetail}
              state={feedbackState}
              sessionId={endedSessionId}
              onRetry={restartFeedbackPoll}
              followUp={{
                onStart: handleStartFollowUp,
                onCreated: () => void reloadScenarios(),
              }}
              onReverse={handleReverse}
              next={
                <NextCalls
                  offers={nextCalls}
                  onStart={(scenarioId, personaId) =>
                    handleStartFollowUp(scenarioId, personaId)
                  }
                />
              }
            />
          }
        />
        {scenarioEditor}
      </AppLayout>
    );
  }

  return (
    <AppLayout step="prepare" pageClassName="setup-page">
      <SetupView
        scenarioItems={library.visible}
        scenarioId={scenarioId}
        scenarioFilter={library.filters.origin}
        onScenarioFilter={(origin) => setScenarioFilters((f) => ({ ...f, origin }))}
        scenarioOriginCounts={library.counts.origin}
        scenarioCategory={library.filters.category}
        onScenarioCategory={(category) => setScenarioFilters((f) => ({ ...f, category }))}
        scenarioCategoryCounts={library.counts.category}
        showRecommended={library.showRecommended}
        tenantName={tenantName}
        onNewScenario={() => setEditingScenario({ id: null })}
        onShowScenarioInfo={setInfoScenarioId}
        offerRandom={library.offerRandom}
        personas={personas}
        personaId={personaId}
        onShowPersonaInfo={setInfoPersonaId}
        selectedScenario={selectedScenario}
        selectedPersona={selectedPersona}
        loadError={loadError ?? library.error}
        onSelectScenario={setScenarioId}
        onSelectPersona={setPersonaId}
        onStart={handleStartSession}
      />

      {scenarioEditor}

      {infoPersona && (
        <PersonaInfo
          personaId={infoPersona.id}
          personaName={infoPersona.name}
          onClose={() => setInfoPersonaId(null)}
        />
      )}

      {infoScenario && (
        <ScenarioInfo
          scenarioId={infoScenario.id}
          scenarioName={infoScenario.name}
          onClose={() => setInfoScenarioId(null)}
          onEdit={handleEditFromInfo}
          onDelete={handleDeleteFromInfo}
        />
      )}
    </AppLayout>
  );
}
