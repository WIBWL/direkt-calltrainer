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


/** How long the die is on screen before the call begins (F-62). Long enough to
 * read as a throw and land, short enough not to become a wait — the Session is
 * already connected behind it, so this is the only thing it costs. */
const ROLL_MS = 2000;

/** null = closed; { id: null } = new; { id } = editing that row. */
type EditorState = { id: string | null } | null;

/**
 * Owns the training flow: which screen is showing, what has been selected, and
 * the live Session behind it. Everything visible is delegated to a screen
 * component — what stays here is the state those screens share.
 */
export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editingScenario, setEditingScenario] = useState<EditorState>(null);
  // The Persona whose read-only info panel is open, or null. Held here for
  // the same reason the editor's state is: SetupView is presentational.
  const [infoPersonaId, setInfoPersonaId] = useState<string | null>(null);
  // The Scenario whose read-only info panel is open, or null. Editing starts
  // from inside it (ADR 0062), so this opens first and the editor second.
  const [infoScenarioId, setInfoScenarioId] = useState<string | null>(null);
  // The caller's company (ADR 0060); null = default tenant, no company chip.
  const [tenantName, setTenantName] = useState<string | null>(null);
  // Tracks intentional muting separately from entering or leaving the call screen.
  const [isMicrophoneMuted, setIsMicrophoneMuted] = useState(false);
  // The input device picked in the mic-check screen; null = browser default.
  // Carries over into the call the same way isMicrophoneMuted does.
  const [micDeviceId, setMicDeviceId] = useState<string | null>(null);
  const { devices: micDevices, refresh: refreshMicDevices } = useMicrophoneDevices();
  // The fade that covers a change of screen, played over whichever screen starts it.
  const { playFade } = useScreenTransition();
  // The training run: the committed Session, its case or briefing, what was
  // said once it ended and what survives a reload (see useTrainingRun.ts).
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
  // The wrap-up, polled once for the waiting screen, the post-call screen and
  // the downloadable report (F-64), so the file carries exactly what the page
  // shows. Polled only while one of those screens is up. Null while on its way
  // and for a call never stored — the file is then the protocol alone.
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

  // The library, its two filter rows and which case is picked. A restored
  // wrap-up owns the screen, so nothing is preselected behind it.
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

  // A reload restores the post-call screen without a selection to look the
  // name up in, so the stored one stands in.
  const personaName = selectedPersona?.name ?? restored?.personaName ?? "Persona";
  // The played case, resolved the same way and for the same screen. A
  // random Scenario needs nothing special: `beginSession` sets `scenarioId` to
  // the drawn row, so the selection already *is* the case that was played.
  const scenarioName = selectedScenario?.name ?? restored?.scenarioName ?? null;

  // Loaded apart from the library, so either one failing leaves the other
  // usable and names itself in the error line.
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

  // A selected microphone that gets unplugged (mid-test or mid-call) falls
  // back to the browser default rather than failing every getUserMedia call
  // with a stale exact deviceId from then on.
  useEffect(() => {
    if (micDeviceId !== null && !micDevices.some((d) => d.deviceId === micDeviceId)) {
      setMicDeviceId(null);
    }
  }, [micDevices, micDeviceId]);


  // Render state the flow routes on, refreshed every render and read only from
  // handlers, so `advance` keeps one identity: `handleAnalysed` feeds the
  // waiting screen's patience timer, and a new identity would restart it.
  // What only one handler knows travels on its event (see `FlowEvent`).
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
  // The whole context at the moment of a press. Reduced motion is asked here
  // rather than per render: it is a media query, and only the throw needs it.
  const flowContext = (): FlowContext => ({
    ...flowRef.current,
    reducedMotion: prefersReducedMotion(),
  });

  /**
   * The only way the screen changes; every destination comes from
   * `trainingFlow.nextScreen`. Facts only a handler knows (skipped mic check,
   * whether the call was stored) ride on the event, so omitting one fails to compile.
   */
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


  // What happens once a call is over and its goodbye has been heard: the run
  // keeps the transcript and remembers the finished Session across a reload,
  // and the flow moves on. When that moment is due is `useLiveCall`'s to
  // decide (see `endIsDue`).
  const handleCallOver = (ended: EndedCall) => {
    // The names are kept because a reload restores the post-call screen
    // without a selection to look them up in; the Persona's id so a reverse
    // started from there after a reload still knows who answers (ADR 0070).
    run.finish(ended, { personaName, scenarioName, personaId });
    // Straight to the wrap-up's own waiting screen where one is being written,
    // and straight past it where none is: no stored Session, no wrap-up, and a
    // wait for something that is not coming (ADR 0066).
    advance({ type: "callEnded", stored: ended.sessionId !== null });
  };

  // The Session (WebSocket + playback + VAD) lives at App level, not in a
  // screen: it connects on commit and buffers the opening line during the mic
  // check, so the Persona speaks the moment the call screen appears (ADR 0042).
  const call = useLiveCall(committed, handleCallOver);
  const { accept } = call;

  const vad = useMicrophoneVAD(call.bargeIn, call.sendTurnAudio, micDeviceId);

  useEffect(() => {
    vad.preload();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- preload once, on mount
  }, []);

  // Armed for the whole call, not just while it's nominally the user's turn
  // — see the barge-in handling above.
  const { startListening, stopListening } = vad;
  useEffect(() => {
    if (screen !== "call" || isMicrophoneMuted) {
      // Pausing keeps the preloaded VAD instance warm without capturing speech.
      stopListening();
      return;
    }

    void startListening();
    return () => stopListening();
  }, [isMicrophoneMuted, screen, startListening, stopListening]);

  // The one way into a call: commit to a pairing and go to the microphone
  // check. Taken by the setup screen's button and by the follow-up's start
  // button alike, so the second is the same act as the first and not a shortcut
  // past it. Committing also forgets the stored finished Session (`commit`),
  // so the previous wrap-up does not come back on the next reload.
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
      // Straight from a finished training (F-60/F-61) the microphone was just
      // in use, so the check is skipped. The case is not: a reverse gets its
      // briefing, everything else the case screen, then the ringing phone
      // (F-63) — nothing goes straight into a conversation.
      advance({ type: "sessionCommitted", reverse, skipMicCheck });
      if (skipMicCheck) setIsMicrophoneMuted(false);
    },
    // All three keep one identity (`advance` by its own empty-context design,
    // `commit` by its empty list, the other is a state setter), so this does
    // too -- but it says so now rather than relying on it silently (ADR 0094).
    [advance, setScenarioId, commit],
  );

  const handleStartSession = useCallback(() => {
    if (personaId === null || scenarioId === null) return;

    // The random Scenario (F-62) is drawn here and nowhere earlier: selecting
    // the tile is not yet a case, and a draw made on selection would be a
    // different one each time the User changed their mind about the Persona.
    if (scenarioId === RANDOM_SCENARIO_ID) {
      const drawn = drawRandomScenario(drawPool);
      if (drawn === null) return; // nothing to draw from; the tile is not offered
      beginSession(drawn.id, personaId, { drawnName: drawn.name });
      return;
    }

    // A reverse picked from the library keeps the microphone check and reaches
    // its briefing on the way *out* of it — see `handleMicConfirmed`. Coming
    // from a finished call there is no check to pass, so that path goes to the
    // briefing straight away.
    beginSession(scenarioId, personaId, { reverse: selectedScenario?.reverse ?? false });
  }, [personaId, scenarioId, drawPool, selectedScenario, beginSession]);

  // Post-call screen into the reverse (F-61, ADR 0070): same Persona, new
  // Scenario, via `beginSession` onto the briefing screen. The card's second
  // button — the first only wrote it. The library is reloaded and the filter
  // follows the row so it is not hidden behind the active chip.
  const handleReverse = useCallback(
    (reverse: ReverseScenario) => {
      const persona = personaId ?? restored?.personaId ?? null;
      if (persona === null) return;
      setScenarioFilters({ origin: "reverse", category: "all" });
      void reloadScenarios();
      // The briefing is seeded from the answer that just came back, so its
      // screen has something to show immediately rather than one request later.
      beginSession(reverse.id, persona, {
        reverse: true,
        skipMicCheck: true,
        brief: reverse.reverse_brief,
      });
    },
    [personaId, restored, reloadScenarios, setScenarioFilters, beginSession],
  );

  const handleConfirmed = useCallback(() => {
    // Reveal the buffered opening line and switch to live playback.
    // This is also the point at which the Session timeline starts.
    setIsMicrophoneMuted(false);
    accept();
    advance({ type: "callAccepted" });
  }, [accept, advance]);

  // The mic check's button; `trainingFlow` decides where it leads. Its label
  // asks the same function via `briefingFollows`, so the two cannot disagree.
  const handleMicConfirmed = useCallback(() => {
    advance({ type: "micConfirmed" });
  }, [advance]);

  // The same question asked once more, for the way in that cannot answer it at
  // the door: a follow-up commits and lands on this screen before its case has
  // been fetched. An empty panel with a button under it stops the User for no
  // reason, so the screen moves on by itself the moment the answer is in.
  useEffect(() => {
    if (screen !== "case-brief" || committedCase === null) return;
    if (committedCase.briefing || committedCase.facts) return;
    advance({ type: "caseArrivedEmpty" });
  }, [screen, committedCase, advance]);

  // The throw ends where every ordinary call now begins: at the ringing phone,
  // through the same fade an ordinary call gets. Nothing can cancel it, so the
  // timer is the whole of the screen's logic.
  useEffect(() => {
    if (screen !== "rolling") return undefined;
    const timer = window.setTimeout(() => advance({ type: "rollFinished" }), ROLL_MS);
    return () => window.clearTimeout(timer);
  }, [screen, advance]);

  // Abandoning the microphone check drops the Session that was committed to
  // — the opening line generated for it is already spent, but there is no
  // point holding the connection (and the server-side Session) open for it.
  const handleCancelMicCheck = useCallback(() => {
    cancelRun();
    advance({ type: "micCheckCancelled" });
  }, [advance, cancelRun]);

  // The effect above owns VAD pause/resume; the button only changes UI state.
  const handleToggleMicrophone = useCallback(() => {
    setIsMicrophoneMuted((muted) => !muted);
  }, []);

  // The wrap-up has settled, or the User would rather not wait for it. Stable,
  // because the waiting screen hangs its own patience limit off it.
  const handleAnalysed = useCallback(() => {
    advance({ type: "analysed" });
  }, [advance]);

  // Clears the stored finished Session too, so the wrap-up does not come
  // back when the next Session ends (ADR 0042 handles the reconnect side).
  const handleRestart = useCallback(() => {
    restartRun();
    advance({ type: "restarted" });
  }, [advance, restartRun]);

  // Starts a follow-up (F-60) or reverse (F-61) against the training's Persona.
  // The library predates the new row, hence the reload — and why `reverse` is
  // passed in rather than looked up: a wrong guess would start the call
  // without the briefing the User needs.
  const handleStartFollowUp = useCallback(
    (followUpId: string, followUpPersonaId: string, reverse = false) => {
      void reloadScenarios();
      // Skips the microphone check: this call is begun from a training that
      // has just been read, not from the selection screen. What it does not
      // skip is the case — the wrap-up gives way to the briefing screen, and
      // the call is started from there.
      playFade(() => beginSession(followUpId, followUpPersonaId, { reverse, skipMicCheck: true }));
    },
    [reloadScenarios, beginSession, playFade],
  );

  // The same, started from a past training instead (F-60/F-61). That screen is
  // a route of its own, so it hands the pairing over in the router's location
  // state; this consumes it and clears it immediately, so neither a reload nor
  // the Back button starts a second call. The ref guards against React's
  // double-invoked effects, which would otherwise commit twice.
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
    // Selects the saved row, so it is already picked for the next Session.
    void reloadScenarios(savedId);
  };

  // The card the info panel was opened from. Looked up rather than stored so
  // a reload of the Persona list cannot leave a stale name in the heading;
  // if the Persona is gone the panel closes with the list.
  const infoPersona = personas.find((p) => p.id === infoPersonaId) ?? null;
  const infoScenario = library.scenarios.find((s) => s.id === infoScenarioId) ?? null;

  // Reading hands over to writing: the panel closes as the editor opens, so
  // Cancel in the editor returns to the library rather than to the panel.
  const handleEditFromInfo = (id: string) => {
    setInfoScenarioId(null);
    setEditingScenario({ id });
  };

  // The panel closes first: it is reading a row that is about to be gone, and
  // the request behind it would otherwise finish against a 404.
  const handleDeleteFromInfo = (id: string) => {
    setInfoScenarioId(null);
    handleRemoveScenario(id);
  };

  // Rendered over the setup screen and the post-call screen alike: the
  // follow-up (F-60) can be edited from either.
  const scenarioEditor = editingScenario && (
    <ScenarioEditor
      scenarioId={editingScenario.id}
      tenantName={tenantName}
      onClose={() => setEditingScenario(null)}
      onSaved={handleScenarioSaved}
      onRefresh={() => void reloadScenarios()}
    />
  );

  // Shown on the briefing screen and during the call only. The slot is claimed
  // as soon as the Scenario is known to be a reverse, before its briefing
  // arrives: the call screen lays out around it, and a late panel would move the call.
  const briefPanel = (variant: "prepare" | "call") => {
    if (!committed?.reverse) {
      // An ordinary call keeps its facts in view too (same ADR 0033 exception:
      // fixed before the call). Null for a random Scenario. Read from the
      // committed case, never the selected card, which differs for a follow-up.
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
        <section className={`reverse-brief reverse-brief-${variant}`}>
          <div className="reverse-brief-eyebrow">IHRE UNTERLAGEN</div>
          <p className="reverse-brief-lead">Werden geladen …</p>
        </section>
      );
    }
    return <ReverseBriefPanel brief={reverseBrief} variant={variant} />;
  };

  // The reverse's own pre-call screen: the briefing and nothing else, then the
  // button that begins the call. The Session is already committed behind it and
  // the opening line is generating (ADR 0042), exactly as it does while the
  // microphone check is on screen — this screen replaces that one, it does not
  // come after it.
  if (screen === "brief") {
    return (
      <BriefScreen onContinue={handleConfirmed} onLeave={handleCancelMicCheck}>
        {briefPanel("prepare")}
      </BriefScreen>
    );
  }

  // The ordinary call's own pre-call screen: the briefing and the facts, then
  // the button that rings the phone. The same `BriefScreen` as the reverse's,
  // because it is the same moment in the flow.
  if (screen === "case-brief") {
    return (
      <BriefScreen onContinue={() => advance({ type: "caseRead" })} onLeave={handleCancelMicCheck}>
        {committedCase === null ? (
          // The reverse's briefing screen says the same thing in the same
          // place while its own text is in flight. Reached with the case
          // already fetched from the microphone check, and without it from a
          // wrap-up, where the commit and the request are the same moment.
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
    // Same function the press goes through, so the label cannot promise a call
    // and deliver a page of text. May flip once while the case is in flight.
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
          // The same door out as the microphone check's and the briefing's:
          // declining drops the committed Session rather than holding its
          // connection open for a call nobody is going to take.
          onDecline={handleCancelMicCheck}
        />
      </AppLayout>
    );
  }

  if (screen === "call") {
    // Asked of the data, not the element: `CaseBriefPanel` renders nothing
    // without facts. A reverse's briefing sits beside the call; ordinary case
    // facts go below it, so the live call keeps visual priority.
    const briefPlacement: BriefPlacement | null = committed?.reverse
      ? "beside"
      : committedCase?.facts.trim()
        ? "below"
        : null;
    return (
      <AppLayout
        step="call"
        navigationLocked
        // Wider only while a briefing is beside the call: facts below it keep
        // the standard call width.
        pageClassName={briefPlacement === "beside" ? "call-page call-page-wide" : "call-page"}
      >
        <CallView
          personaName={personaName}
          // In a reverse the Persona is on the company's side, not the role it
          // carries (ADR 0070) — the same reason the prompt drops that field.
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
      // The brand in the header leaves for the same place the preparation button
      // at the foot does, and has to do the same thing to get there: these two
      // screens are a state under the training route, not a route of their own.
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
                // The new row is not in this screen's library copy yet, and
                // the setup screen reads its names off that.
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
