import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { apiFetch } from "./api";
import AppLayout from "./components/AppLayout";
import CallView from "./components/CallView";
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
import type { CommittedSession } from "./hooks/useSessionSocket";
import { useNextCalls } from "./hooks/useNextCalls";
import { useScenarioLibrary } from "./hooks/useScenarioLibrary";
import NextCalls from "./components/NextCalls";
import { useSessionFeedback } from "./hooks/useSessionFeedback";
import type { Persona, TranscriptEntry } from "./protocol";
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
  getScenario,
  getTenant,
  RANDOM_SCENARIO_ID,
  type ReverseBrief,
  type ReverseScenario,
} from "./scenarioLibrary";
import { loadFinishedSession, saveFinishedSession } from "./utils/finishedSession";
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
  // Lazy initializer: read once on mount, not on every render.
  const [restored] = useState(loadFinishedSession);
  const [screen, setScreen] = useState<Screen>(restored ? "transcript" : "setup");
  const [transcript, setTranscript] = useState<TranscriptEntry[]>(restored?.turns ?? []);
  // Names the persisted Session so its Feedback can be fetched once the
  // worker has produced it. Not kept anywhere but here: the wrap-up is
  // reachable for as long as this screen is, and no longer.
  const [endedSessionId, setEndedSessionId] = useState<string | null>(restored?.sessionId ?? null);
  // The wrap-up, polled once for the two screens that show it: the waiting
  // screen hands over when it settles, the post-call screen renders it, and the
  // downloadable report (F-64) reads the same `detail`, so the file carries
  // exactly what the page shows. Polled only while one of those screens is up,
  // so nothing keeps asking once the User has moved on. Null while it is on its
  // way, and for a call that was never stored — the file is then the protocol
  // alone.
  const {
    detail: endedSessionDetail,
    state: feedbackState,
    restart: restartFeedbackPoll,
  } = useSessionFeedback(
    screen === "analysing" || screen === "transcript" ? endedSessionId : null,
  );
  // The committed Session: set when the user actually commits to one (the
  // start-the-session press), never by the selection itself — see ADR 0042.
  // Nothing connects on its own, which is also what keeps a persistently
  // failing backend from looping: a failed Session is only ever retried by
  // another deliberate click, never automatically.
  const [committed, setCommitted] = useState<CommittedSession | null>(null);
  // The pairing just played, kept past the end of the call for the offers of
  // what to play next (F-64): `committed` is cleared the moment the call ends.
  const [lastPlayed, setLastPlayed] = useState<{
    scenarioId: string;
    personaId: string;
  } | null>(null);
  const nextCalls = useNextCalls(
    lastPlayed?.scenarioId ?? null,
    lastPlayed?.personaId ?? null,
    screen === "transcript",
  );
  // The briefing shown during a reverse (ADR 0070). Held here rather than in
  // the screens because both the mic check and the call show it, and because
  // it is fetched once per committed Session rather than once per screen.
  const [reverseBrief, setReverseBrief] = useState<ReverseBrief | null>(null);
  // The drawn Scenario's name while it is still a secret (F-62): set only for
  // a random Scenario, and the one thing the call screen must not show. Null
  // means the User picked the case themselves and knows what it is.
  const [secretScenario, setSecretScenario] = useState<string | null>(null);

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
    apiFetch<Persona[]>("/api/personas")
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

  // The facts of the committed case, for the screen before the call and the
  // panel beside it. Fetched rather than read off the card: the listing
  // deliberately withholds the case (ADR 0045) and only the detail route
  // serves it — the same text the info panel behind a card's "i" shows.
  //
  // Withheld for a random Scenario, which is the one case the User is meant
  // to walk into unread (F-62), and for a reverse, which has a briefing of
  // its own and would otherwise be given two.
  //
  // The briefing comes from here rather than off the selection card, although
  // the card carries one: a follow-up is started from a wrap-up, and its row
  // is not in this screen's copy of the library yet — the reload runs beside
  // the commit, not before it. One fetch for both halves is also one moment at
  // which the case screen is ready, instead of two.
  //
  // `null` means "not fetched yet" and is what the briefing screen waits on;
  // empty strings mean the case has nothing to read.
  const [committedCase, setCommittedCase] = useState<
    { briefing: string; facts: string } | null
  >(null);

  // What the flow routes on that render state can answer, refreshed every
  // render and read only from event handlers — which is what lets `advance`
  // keep one identity for the life of the component. That matters:
  // `handleAnalysed` is a dependency of the waiting screen's own patience
  // timer, and a new identity would restart it. What only one handler knows
  // travels on that handler's event instead (see `FlowEvent`).
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
   * The only way the screen changes.
   *
   * Every destination comes from `trainingFlow.nextScreen`, so the machine is
   * the table there and not the sum of the call sites. The facts a handler
   * knows and the render does not — whether this commit skips the microphone
   * check, whether the call that just ended was stored — ride on the event
   * itself, so leaving one out does not compile.
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

  // One request for whichever half the committed Scenario has: the case of an
  // ordinary call (see the note on `committedCase` above), or the briefing of a
  // reverse (ADR 0070). Both come from the detail route — the reverse's case is
  // only ever served there, for the caller's own rows, which is what keeps the
  // exception to ADR 0043 down to the one Session the User actually played.
  //
  // `handleReverse` has already put the briefing in place for a reverse it
  // just created, so this runs for one too and overwrites it with the same
  // content — which is why a failure must leave the existing value alone
  // rather than clearing it.
  useEffect(() => {
    setCommittedCase(null);
    if (!committed?.reverse) setReverseBrief(null);
    // Nothing to fetch for a random Scenario, whose case is withheld (F-62).
    if (!committed || (!committed.reverse && secretScenario !== null)) return undefined;

    let cancelled = false;
    getScenario(committed.scenarioId)
      .then((detail) => {
        if (cancelled) return;
        if (!committed.reverse) {
          setCommittedCase({ briefing: detail.briefing, facts: detail.case_facts });
        } else if (detail.reverse_brief) {
          setReverseBrief(detail.reverse_brief);
        }
      })
      .catch(() => {
        // The call is the point; it runs with or without the panel.
      });
    return () => {
      cancelled = true;
    };
  }, [committed, secretScenario]);

  // What happens once a call is over and its goodbye has been heard: the
  // transcript is kept, the finished Session is remembered across a reload,
  // and the flow moves on. When that moment is due is `useLiveCall`'s to
  // decide (see `endIsDue`).
  const handleCallOver = (ended: EndedCall) => {
    setTranscript(ended.turns);
    setEndedSessionId(ended.sessionId);
    saveFinishedSession({
      sessionId: ended.sessionId,
      turns: ended.turns,
      personaName,
      scenarioName,
      // Kept so a reverse started from this screen after a reload still knows
      // which Persona to put on the other end (ADR 0070).
      personaId,
    });
    // Straight to the wrap-up's own waiting screen where one is being written,
    // and straight past it where none is: no stored Session, no wrap-up, and a
    // wait for something that is not coming (ADR 0066).
    advance({ type: "callEnded", stored: ended.sessionId !== null });
    if (committed) {
      setLastPlayed({ scenarioId: committed.scenarioId, personaId: committed.personaId });
    }
    // This Session is over — the next one connects when the user commits
    // to it, not while the transcript is still being read (ADR 0042).
    setCommitted(null);
  };

  // The Session (WebSocket + audio playback, with the VAD below) lives here,
  // at the App level, not inside whichever screen happens to be showing — it
  // connects once the user commits to a Session, and its opening line is
  // generated and buffered while the microphone check is still on screen, so
  // the Persona can start speaking the moment the call screen appears
  // (ADR 0042).
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
  // past it. The stored finished Session goes here rather than in whoever
  // called: once a new call is committed to, the previous wrap-up must not come
  // back on the next reload.
  const beginSession = useCallback(
    (nextScenarioId: string, nextPersonaId: string, reverse = false, skipMicCheck = false) => {
      saveFinishedSession(null);
      // Cleared here rather than in each caller, so a path that forgets about
      // it gets the safe answer: a Scenario shown, not one wrongly hidden.
      setSecretScenario(null);
      setScenarioId(nextScenarioId);
      setPersonaId(nextPersonaId);
      // A new object every time: that identity is what makes this a new
      // Session for useSessionSocket, even when the pairing is unchanged.
      setCommitted({ personaId: nextPersonaId, scenarioId: nextScenarioId, reverse });
      // Straight from a finished training (F-60/F-61) the microphone has just
      // been used for the call this one follows from, and its device is still
      // selected — so the check would be a screen between the button and the
      // conversation and nothing else, and it is skipped.
      //
      // What is not skipped is the case: a reverse gets the briefing it has to
      // argue from, and everything else the screen with its own Briefing
      // on it — the same one the microphone check leads to. A follow-up used to
      // go from the wrap-up straight to the ringing phone, which was the one
      // way into a call that never showed the User what they were walking
      // into. From there the ringing phone (F-63) is one further press:
      // nothing goes straight into a conversation, and the last press before
      // someone has to speak is always their own.
      advance({ type: "sessionCommitted", reverse, skipMicCheck });
      if (skipMicCheck) setIsMicrophoneMuted(false);
    },
    // Both keep one identity (`advance` by its own empty-context design, the
    // other is a state setter), so this does too -- but it says so now rather
    // than relying on it silently (ADR 0094).
    [advance, setScenarioId],
  );

  const handleStartSession = useCallback(() => {
    if (personaId === null || scenarioId === null) return;

    // The random Scenario (F-62) is drawn here and nowhere earlier: selecting
    // the tile is not yet a case, and a draw made on selection would be a
    // different one each time the User changed their mind about the Persona.
    if (scenarioId === RANDOM_SCENARIO_ID) {
      const drawn = drawRandomScenario(drawPool);
      if (drawn === null) return; // nothing to draw from; the tile is not offered
      beginSession(drawn.id, personaId, false);
      // After `beginSession`, which clears it: both run in the same event, so
      // this is the value that survives.
      setSecretScenario(drawn.name);
      return;
    }

    // A reverse picked from the library keeps the microphone check and reaches
    // its briefing on the way *out* of it — see `handleMicConfirmed`. Coming
    // from a finished call there is no check to pass, so that path goes to the
    // briefing straight away.
    beginSession(scenarioId, personaId, selectedScenario?.reverse ?? false);
  }, [personaId, scenarioId, drawPool, selectedScenario, beginSession]);

  // From the post-call screen into the reverse (F-61, ADR 0070): the same
  // Persona, the new Scenario, no detour through the setup screen. Taken by the
  // card's second button, once the Scenario exists and the User has read what
  // it is — the first one only wrote it. Goes through the same `beginSession`
  // as the follow-up's start button, which lands it on the briefing screen rather
  // than in the call. The library is reloaded so the row is there when the User
  // comes back to it, and the filter follows it, so it is not hidden behind
  // whichever chip happened to be active.
  const handleReverse = useCallback(
    (reverse: ReverseScenario) => {
      const persona = personaId ?? restored?.personaId ?? null;
      if (persona === null) return;
      setScenarioFilters({ origin: "reverse", category: "all" });
      void reloadScenarios();
      // Seeded from the answer that just came back, so the briefing screen has
      // something to show immediately rather than one request later; the
      // effect above refetches it and lands on the same content.
      setReverseBrief(reverse.reverse_brief);
      beginSession(reverse.id, persona, true, true);
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

  // The microphone check's own button. Where it leads is `trainingFlow`'s to
  // decide: a reverse to its briefing, a drawn Scenario to
  // the die (skipped under reduced motion, where it would be three seconds of
  // nothing), a case with nothing in it straight to the phone, everything else
  // to the case screen. The check's label asks the same function through
  // `briefingFollows` when the screen renders, so the two cannot disagree.
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
    setCommitted(null);
    advance({ type: "micCheckCancelled" });
  }, [advance]);

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
    saveFinishedSession(null);
    advance({ type: "restarted" });
  }, [advance]);

  // Starts a Scenario written out of a finished training as the next call,
  // against the Persona that training was played with: the follow-up (F-60)
  // and the reverse (F-61) alike. The call itself needs only the two ids, but
  // the screens read the names off the library — which was fetched before that
  // call ended and so does not hold the new row yet, hence the reload
  // alongside.
  //
  // `reverse` cannot be looked up off the library here for the same reason:
  // the row may not be in it yet, and getting it wrong would start the call
  // without the briefing the User needs to play it at all.
  const handleStartFollowUp = useCallback(
    (followUpId: string, followUpPersonaId: string, reverse = false) => {
      void reloadScenarios();
      // Skips the microphone check: this call is begun from a training that
      // has just been read, not from the selection screen. What it does not
      // skip is the case — the wrap-up gives way to the briefing screen, and
      // the call is started from there.
      playFade(() => beginSession(followUpId, followUpPersonaId, reverse, true));
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

  // Shown on the briefing screen and during the call, and nowhere else — the
  // microphone check used to carry it too, which put the case the User is
  // about to argue on the same screen as a level meter. It has its own screen
  // now and holds nothing else.
  //
  // The slot is claimed as soon as the committed Scenario is known to be a
  // reverse, before its briefing has arrived: the call screen lays itself out
  // around this, and a panel that appeared a request later would move the
  // call.
  const briefPanel = (variant: "prepare" | "call") => {
    if (!committed?.reverse) {
      // An ordinary call keeps its facts in view the same way, which is the
      // same exception to ADR 0033 for the same reason: fixed before the call,
      // never the Persona's lines. The case is already null for a
      // random Scenario, so nothing is revealed there.
      //
      // Briefing and facts both from the committed case: the selected card is
      // not the committed Scenario when a follow-up starts from a wrap-up, and
      // two sources for one case is the defect `briefingFollows` was built to
      // end on the microphone check.
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
          <div className="eyebrow">ZUFALLSSZENARIO</div>
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
    // Asked of the same function the button's press goes through, so the label
    // cannot promise a call and deliver a page of text. It used to be a second
    // expression reading a *different* source — the card's briefing where the
    // router read the committed case's — and the two disagreed for a Scenario
    // carrying facts but no card briefing. The label may flip once while the
    // case is still in flight; it is no longer ever wrong.
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
    // A real answer and not "an element exists": `CaseBriefPanel` renders
    // nothing when there are no facts, and the page widens to two columns on
    // this, so asking the element would leave an empty second column.
    const hasBrief = committed?.reverse === true || Boolean(committedCase?.facts.trim());
    const brief = hasBrief ? briefPanel("call") : null;
    return (
      <AppLayout
        step="call"
        navigationLocked
        // Wider only while a briefing is beside the call: the 800px column is
        // right for a screen whose whole content is one animation.
        pageClassName={hasBrief ? "call-page call-page-wide" : "call-page"}
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
          brief={brief}
        />
      </AppLayout>
    );
  }

  if (screen === "analysing") {
    return (
      <AppLayout step="feedback" onHome={handleRestart}>
        <FeedbackWaiting state={feedbackState} onDone={handleAnalysed} />
      </AppLayout>
    );
  }

  if (screen === "transcript") {
    return (
      // The brand in the header leaves for the same place the home button at
      // the foot does, and has to do the same thing to get there: these two
      // screens are a state under the training route, not a route of their own.
      <AppLayout step="feedback" onHome={handleRestart}>
        <FeedbackScreen
          transcript={transcript}
          personaName={personaName}
          scenarioName={scenarioName}
          detail={endedSessionDetail}
          actions={
            <button className="back-to-start-button" type="button" onClick={handleRestart}>
              Zur Startseite
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
