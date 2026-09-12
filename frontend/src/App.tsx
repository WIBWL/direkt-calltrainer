import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { apiFetch } from "./api";
import AppLayout from "./components/AppLayout";
import CallView from "./components/CallView";
import CaseBriefPanel from "./components/CaseBriefPanel";
import DiceRoll from "./components/DiceRoll";
import IncomingCall from "./components/IncomingCall";
import FeedbackView from "./components/FeedbackView";
import FeedbackWaiting from "./components/FeedbackWaiting";
import {
  CATEGORY_FILTERS,
  matchesCategory,
  matchesFilter,
  type CategoryFilter,
  type LibraryFilter,
} from "./components/LibraryPicker";
import MicCheck from "./components/MicCheck";
import PersonaInfo from "./components/PersonaInfo";
import ScenarioEditor from "./components/ScenarioEditor";
import ScenarioInfo from "./components/ScenarioInfo";
import { useScreenTransition } from "./components/ScreenTransition";
import SetupView from "./components/SetupView";
import FeedbackScreen from "./components/FeedbackScreen";
import { useMicrophoneDevices } from "./hooks/useMicrophoneDevices";
import { useMicrophoneVAD } from "./hooks/useMicrophoneVAD";
import { useSessionSocket, type CommittedSession } from "./hooks/useSessionSocket";
import { useNextCalls } from "./hooks/useNextCalls";
import NextCalls from "./components/NextCalls";
import { useStreamedAudioPlayback } from "./hooks/useStreamedAudioPlayback";
import type { Persona, SessionDetail, TranscriptEntry } from "./protocol";
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
  deleteScenario,
  drawRandomScenario,
  getScenario,
  getTenant,
  isDrawable,
  listScenarios,
  RANDOM_SCENARIO_ID,
  type ReverseBrief,
  type ReverseScenario,
  type ScenarioCard,
} from "./scenarioLibrary";
import { loadFinishedSession, saveFinishedSession } from "./utils/finishedSession";
import { prefersReducedMotion } from "./utils/motion";


/** How long the die is on screen before the call begins (F-62). Long enough to
 * read as a throw and land, short enough not to become a wait — the Session is
 * already connected behind it, so this is the only thing it costs. */
const ROLL_MS = 3000;

interface PendingEnd {
  reason: "user" | "error" | "completed";
  turns: TranscriptEntry[];
  sessionId: string | null;
}

/** null = closed; { id: null } = new; { id } = editing that row. */
type EditorState = { id: string | null } | null;

/** Every level 1 value, including "tenant": counting it costs nothing when the
 * caller has no company, and the picker decides whether to offer the option. */
const ORIGIN_FILTERS: LibraryFilter[] = [
  "recommended", "all", "standard", "own", "tenant", "followUp", "reverse",
];

/** What the selection screen opens on (ADR 0072): everything, on both rows.
 * Opening on a shortlist, which this once did, hides the User's own Scenarios
 * behind a filter they have to know to press — and `COLLAPSED_CARDS` caps what
 * is on screen anyway, so the unfiltered row is a first page of the library
 * rather than a wall of it. */
const DEFAULT_ORIGIN: LibraryFilter = "all";
const DEFAULT_CATEGORY: CategoryFilter = "all";

/** Where the screen opens: on the suggestions where there are any (F-62), with
 * the category row unfiltered — suggestions spread over the categories, and one
 * of them alone would often leave nothing. Otherwise the defaults above. */
function startingFilters(scenarios: ScenarioCard[]): [LibraryFilter, CategoryFilter] {
  return scenarios.some((s) => s.recommendation)
    ? ["recommended", "all"]
    : [DEFAULT_ORIGIN, DEFAULT_CATEGORY];
}

/** The card as the picker takes it. Its own function because the first
 * selection is made against the same filters the picker applies, before there
 * is a rendered list to read one off. */
const toLibraryItem = (s: ScenarioCard) => ({
  id: s.id,
  name: s.name,
  subtitle: s.short_description,
  origin: s.origin,
  shared: s.shared,
  category: s.category,
  followUp: s.follow_up,
  reverse: s.reverse,
  originSession: s.origin_session,
  recommendation: s.recommendation,
});

/** The Scenario to start on: the random Scenario (F-62), which is the one tile
 * that stands outside both filters and is therefore always on screen. It is
 * also the only opening selection that cannot be the wrong one — every other
 * default silently proposes a case the User did not choose.
 *
 * It needs a pool to draw from, so for a library holding nothing but reverses
 * and follow-ups this falls back to the first card the default filters show —
 * the first of all, for a library those filters leave empty — which keeps the
 * summary at the bottom of the screen from naming a card that is not on it. */
function firstSelectable(scenarios: ScenarioCard[]): string | null {
  if (scenarios.some(isDrawable)) return RANDOM_SCENARIO_ID;
  const [origin, category] = startingFilters(scenarios);
  const items = scenarios.map(toLibraryItem);
  const visible = items.find(
    (item) => matchesFilter(item, origin) && matchesCategory(item, category),
  );
  return (visible ?? items[0])?.id ?? null;
}

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
  const [scenarioFilter, setScenarioFilter] = useState<LibraryFilter>(DEFAULT_ORIGIN);
  // The F-03 call context filter (ADR 0072), independent of the origin chips.
  const [scenarioCategory, setScenarioCategory] = useState<CategoryFilter>(DEFAULT_CATEGORY);
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
  // The reverse's film cut (F-61), played over whichever screen starts it.
  const { playReverse, playFade } = useScreenTransition();
  // Lazy initializer: read once on mount, not on every render.
  const [restored] = useState(loadFinishedSession);
  const [screen, setScreen] = useState<Screen>(restored ? "transcript" : "setup");
  const [transcript, setTranscript] = useState<TranscriptEntry[]>(restored?.turns ?? []);
  // Names the persisted Session so its Feedback can be fetched once the
  // worker has produced it. Not kept anywhere but here: the wrap-up is
  // reachable for as long as this screen is, and no longer.
  const [endedSessionId, setEndedSessionId] = useState<string | null>(restored?.sessionId ?? null);
  // The wrap-up once FeedbackView has polled it, for the downloadable report
  // (F-64): the file carries everything the page shows, and the page's own
  // poll is the only place that data arrives. Null while it is on its way, and
  // for a call that was never stored — the file is then the protocol alone.
  const [endedSessionDetail, setEndedSessionDetail] = useState<SessionDetail | null>(null);
  // Holds a just-received session.ended until playback actually finishes —
  // see the effect below.
  const [pendingEnd, setPendingEnd] = useState<PendingEnd | null>(null);
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
  // What a random Scenario would be drawn from (F-62): what the two filter
  // rows currently show, minus the two kinds nobody should be walked into
  // unprepared. Held as Scenario *cards* rather than library items because the
  // draw hands its result to `beginSession`, which wants the row.
  const drawPool = useMemo(
    () =>
      scenarios.filter((s) => {
        const item = toLibraryItem(s);
        return (
          isDrawable(s) &&
          matchesFilter(item, scenarioFilter) &&
          matchesCategory(item, scenarioCategory)
        );
      }),
    [scenarios, scenarioFilter, scenarioCategory],
  );
  // No pool, no tile: an offer to draw where there is nothing to draw from is
  // a button that does nothing.
  const offerRandom = drawPool.length > 0;

  // A reload restores the post-call screen without a selection to look the
  // name up in, so the stored one stands in.
  const personaName = selectedPersona?.name ?? restored?.personaName ?? "Persona";
  // The played case, resolved the same way and for the same screen. A
  // random Scenario needs nothing special: `beginSession` sets `scenarioId` to
  // the drawn row, so the selection already *is* the case that was played.
  const scenarioName = selectedScenario?.name ?? restored?.scenarioName ?? null;

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
        if (!restored) {
          const [origin, category] = startingFilters(data);
          setScenarioFilter(origin);
          setScenarioCategory(category);
          setScenarioId(firstSelectable(data));
        }
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

  // What the flow routes on, refreshed every render and read only from event
  // handlers — which is what lets `advance` keep one identity for the life of
  // the component. That matters: `handleAnalysed` is a dependency of the
  // waiting screen's own patience timer, and a new identity would restart it.
  const flowRef = useRef<FlowContext>({
    reverse: false,
    drawn: false,
    committedCase: null,
    reducedMotion: false,
    skipMicCheck: false,
    stored: false,
  });
  flowRef.current = {
    reverse: committed?.reverse === true,
    drawn: secretScenario !== null,
    committedCase,
    // Asked at the moment of the transition rather than per render: it is a
    // media query, and only the throw depends on it.
    reducedMotion: false,
    skipMicCheck: false,
    stored: false,
  };

  /**
   * The only way the screen changes.
   *
   * Every destination comes from `trainingFlow.nextScreen`, so the machine is
   * the table there and not the sum of the call sites. `overrides` carries the
   * facts a handler knows and the render does not — whether this commit skips
   * the microphone check, whether the call that just ended was stored — which
   * are arguments rather than state at the moment they are needed.
   */
  const advance = useCallback(
    (event: FlowEvent, overrides: Partial<FlowContext> = {}) => {
      const context = {
        ...flowRef.current,
        reducedMotion: prefersReducedMotion(),
        ...overrides,
      };
      const { screen: next, cut } = nextScreen(context, event);
      if (cut === "fade") playFade(() => setScreen(next));
      else if (cut === "reverse") playReverse(() => setScreen(next));
      else setScreen(next);
    },
    [playFade, playReverse],
  );

  useEffect(() => {
    if (!committed || committed.reverse || secretScenario !== null) {
      setCommittedCase(null);
      return undefined;
    }
    let cancelled = false;
    getScenario(committed.scenarioId)
      .then((detail) => {
        if (!cancelled) {
          setCommittedCase({ briefing: detail.briefing, facts: detail.case_facts });
        }
      })
      .catch(() => {
        // The call is the point; it runs with or without the panel.
      });
    return () => {
      cancelled = true;
    };
  }, [committed, secretScenario]);

  // The briefing for a committed reverse (ADR 0070). Fetched here rather than
  // carried on the card: the case is only ever served on the detail route, for
  // the caller's own rows, which is what keeps the exception to ADR 0043 down
  // to the one Session the User actually played.
  //
  // `handleReverse` has already put the briefing in place for a reverse it
  // just created, so this only really runs when one is picked from the library
  // — but it runs then too, and overwrites with the same content, which is why
  // a failure must leave the existing value alone rather than clearing it.
  useEffect(() => {
    if (!committed?.reverse) {
      setReverseBrief(null);
      return;
    }
    let cancelled = false;
    getScenario(committed.scenarioId)
      .then((detail) => {
        if (!cancelled && detail.reverse_brief) setReverseBrief(detail.reverse_brief);
      })
      .catch(() => {
        // The call is the point; it runs with or without the panel.
      });
    return () => {
      cancelled = true;
    };
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
    saveFinishedSession({
      sessionId: pendingEnd.sessionId,
      turns: pendingEnd.turns,
      personaName,
      scenarioName,
      // Kept so a reverse started from this screen after a reload still knows
      // which Persona to put on the other end (ADR 0070).
      personaId,
    });
    // Straight to the wrap-up's own waiting screen where one is being written,
    // and straight past it where none is: no stored Session, no wrap-up, and a
    // wait for something that is not coming (ADR 0066).
    advance("callEnded", { stored: pendingEnd.sessionId !== null });
    if (committed) {
      setLastPlayed({ scenarioId: committed.scenarioId, personaId: committed.personaId });
    }
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

  // Ending the call while the persona is still talking is a barge-in too:
  // report the played position first so the transcript keeps only the part of
  // that last reply the user actually heard (ADR 0035), then end. Reads
  // displayStateRef, not playback.isPlaying, for the same reason handleBargeIn
  // does — this callback is created once and must see fresh state.
  const handleEndCall = useCallback(() => {
    if (displayStateRef.current !== "listening") {
      socket.sendInterrupt(playback.interrupt());
    }
    socket.endSession();
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
      advance("sessionCommitted", { reverse, skipMicCheck });
      if (skipMicCheck) setIsMicrophoneMuted(false);
    },
    [],
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

    // A reverse picked from the library keeps the microphone check, and the
    // card is turned over on the way *out* of it rather than into it — see
    // `handleMicConfirmed`. Coming from a finished call there is no check to
    // pass, so that path turns the card straight away.
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
      setScenarioFilter("reverse");
      setScenarioCategory("all");
      void reloadScenarios();
      // Seeded from the answer that just came back, so the briefing screen has
      // something to show immediately rather than one request later; the effect
      // below refetches it and lands on the same content.
      setReverseBrief(reverse.reverse_brief);
      // Behind the card, so the wrap-up is gone and the briefing is there by
      // the time anything is visible again (F-61, ADR 0070).
      playReverse(() => beginSession(reverse.id, persona, true, true));
    },
    [personaId, restored, reloadScenarios, beginSession, playReverse],
  );

  const handleRemoveScenario = useCallback(
    (id: string) => {
      void deleteScenario(id)
        // Selects whatever is first afterwards, so the screen is never left
        // pointing at a row that is gone.
        .then(() => reloadScenarios(null))
        .catch((e) => setLoadError(`Szenario konnte nicht entfernt werden: ${e.message}`));
    },
    [reloadScenarios],
  );

  const handleConfirmed = useCallback(() => {
    // Reveal the buffered opening line and switch to live playback.
    // This is also the point at which the Session timeline starts.
    setIsMicrophoneMuted(false);
    playback.activate();
    socket.sendActivate();
    advance("callAccepted");
  }, [playback, socket.sendActivate, advance]);

  // The microphone check's own button. A random Scenario gets the die in
  // between (F-62); everything else goes straight through. Under reduced
  // motion the screen is skipped rather than shown still: the animation is the
  // whole of what it has to say, and without it it is two seconds of nothing.
  // Where this leads is `trainingFlow`'s to decide: a reverse to its briefing
  // behind the card turn, a drawn Scenario to the die, a case with nothing in
  // it straight to the phone, everything else to the case screen. The button
  // above asks the same function what its own label should say, so the two
  // cannot disagree about it.
  const handleMicConfirmed = useCallback(() => {
    advance("micConfirmed");
  }, [advance]);

  // The same question asked once more, for the way in that cannot answer it at
  // the door: a follow-up commits and lands on this screen before its case has
  // been fetched. An empty panel with a button under it stops the User for no
  // reason, so the screen moves on by itself the moment the answer is in.
  useEffect(() => {
    if (screen !== "case-brief" || committedCase === null) return;
    if (committedCase.briefing || committedCase.facts) return;
    advance("caseArrivedEmpty");
  }, [screen, committedCase, advance]);

  // The throw ends where every ordinary call now begins: at the ringing phone,
  // through the same fade an ordinary call gets. Nothing can cancel it, so the
  // timer is the whole of the screen's logic.
  useEffect(() => {
    if (screen !== "rolling") return undefined;
    const timer = window.setTimeout(() => advance("rollFinished"), ROLL_MS);
    return () => window.clearTimeout(timer);
  }, [screen, advance]);

  // Abandoning the microphone check drops the Session that was committed to
  // — the opening line generated for it is already spent, but there is no
  // point holding the connection (and the server-side Session) open for it.
  const handleCancelMicCheck = useCallback(() => {
    setCommitted(null);
    advance("micCheckCancelled");
  }, [advance]);

  // The effect above owns VAD pause/resume; the button only changes UI state.
  const handleToggleMicrophone = useCallback(() => {
    setIsMicrophoneMuted((muted) => !muted);
  }, []);

  // The wrap-up has settled, or the User would rather not wait for it. Stable,
  // because the waiting screen hangs its own patience limit off it.
  const handleAnalysed = useCallback(() => {
    advance("analysed");
  }, [advance]);

  // Clears the stored finished Session too, so the wrap-up does not come
  // back when the next Session ends (ADR 0042 handles the reconnect side).
  const handleRestart = useCallback(() => {
    saveFinishedSession(null);
    advance("restarted");
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

  // Memoised because the effect below depends on the visible set, and a fresh
  // array every render would re-run it every render.
  const scenarioItems = useMemo(() => scenarios.map(toLibraryItem), [scenarios]);
  // One level applied at a time, for the counts below: each row's numbers are
  // read against the *other* row's selection (ADR 0072), so neither of these
  // is the visible set — that is both of them at once, further down.
  // By name, not by origin group: the grid badges every card with where it
  // comes from, so grouping by that said the same thing twice and left no way
  // to find a Scenario one already knows the name of. `localeCompare` with an
  // explicit locale, because an umlaut has to sort with its base letter rather
  // than after Z.
  // The random Scenario is not in here — the picker draws it in a fixed first
  // place ahead of this list.
  const visibleScenarios = useMemo(
    () =>
      scenarioItems
        .filter((s) => matchesFilter(s, scenarioFilter) && matchesCategory(s, scenarioCategory))
        .sort((a, b) => a.name.localeCompare(b.name, "de")),
    [scenarioItems, scenarioFilter, scenarioCategory],
  );
  // Each row is counted against the *other* row's selection, never its own, so
  // an option's number is what picking it would actually yield.
  const scenarioOriginCounts = Object.fromEntries(
    ORIGIN_FILTERS.map((f) => [
      f,
      scenarioItems.filter((s) => matchesCategory(s, scenarioCategory) && matchesFilter(s, f))
        .length,
    ]),
  ) as Record<LibraryFilter, number>;
  const scenarioCategoryCounts = Object.fromEntries(
    CATEGORY_FILTERS.map((c) => [
      c,
      scenarioItems.filter((s) => matchesFilter(s, scenarioFilter) && matchesCategory(s, c))
        .length,
    ]),
  ) as Record<CategoryFilter, number>;

  // The selection summary must never name a case that is not on the screen
  // above it — the rule the opening selection already follows. A filter change
  // can break it two ways: the random Scenario tile stops being offered, or the
  // card that was picked is filtered away. Either way the selection falls back
  // to the tile, which is where the screen opens; only with nothing left to
  // fall back to does the summary report nothing selected. Falling back rather
  // than clearing is the point: clearing left the summary empty even after the
  // User filtered their way back to a library full of cases.
  useEffect(() => {
    setScenarioId((current) => {
      if (current === RANDOM_SCENARIO_ID) return offerRandom ? current : null;
      if (current !== null && visibleScenarios.some((item) => item.id === current)) {
        return current;
      }
      return offerRandom ? RANDOM_SCENARIO_ID : null;
    });
  }, [offerRandom, visibleScenarios]);

  const handleScenarioSaved = (savedId: string | null) => {
    setEditingScenario(null);
    // Selects the saved row, so it is already picked for the next Session.
    void reloadScenarios(savedId);
  };

  // The card the info panel was opened from. Looked up rather than stored so
  // a reload of the Persona list cannot leave a stale name in the heading;
  // if the Persona is gone the panel closes with the list.
  const infoPersona = personas.find((p) => p.id === infoPersonaId) ?? null;
  const infoScenario = scenarios.find((s) => s.id === infoScenarioId) ?? null;

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
      return (
        <CaseBriefPanel
          briefing={selectedScenario?.briefing}
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
      <AppLayout step="prepare" navigationLocked pageClassName="brief-page">
        {briefPanel("prepare")}
        <div className="brief-actions">
          <button type="button" className="start-call-button" onClick={handleConfirmed}>
            Los geht's
          </button>
        </div>
        {/* Same door out as the microphone check's, and the same button in the
            same place: for a reverse this screen *replaces* that one, so
            leaving must not read as a different act. Leaving drops the
            committed Session rather than holding its connection open. */}
        <button
          type="button"
          className="back-to-start-button"
          onClick={handleCancelMicCheck}
        >
          Zur Startseite
        </button>
      </AppLayout>
    );
  }

  // The ordinary call's own pre-call screen: the briefing and the facts, then
  // the button that rings the phone. Built like the reverse's — same page
  // class, same entrance, same way out — because it is the same moment in the
  // flow: the last thing read before someone has to speak.
  if (screen === "case-brief") {
    return (
      <AppLayout step="prepare" navigationLocked pageClassName="brief-page">
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
        <div className="brief-actions">
          <button
            type="button"
            className="start-call-button"
            onClick={() => advance("caseRead")}
          >
            Los geht's
          </button>
        </div>
        <button
          type="button"
          className="back-to-start-button"
          onClick={handleCancelMicCheck}
        >
          Zur Startseite
        </button>
      </AppLayout>
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
    const nextIsBriefing = briefingFollows({
      ...flowRef.current,
      reducedMotion: prefersReducedMotion(),
    });
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
          callState={displayState}
          audioLevel={playback.audioLevel}
          error={socket.error ?? vad.micError}
          onToggleMicrophone={handleToggleMicrophone}
          onEndCall={handleEndCall}
          brief={brief}
        />
      </AppLayout>
    );
  }

  if (screen === "analysing") {
    return (
      <AppLayout step="feedback" onHome={handleRestart}>
        {/* The wrap-up's own poll lives one screen further on, in FeedbackView
            — this one runs its own and hands over the moment it settles. Two
            pollers, but never at the same time, and the second one's first
            request finds the answer already written. */}
        <FeedbackWaiting sessionId={endedSessionId} onDone={handleAnalysed} />
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
              sessionId={endedSessionId}
              onDetail={setEndedSessionDetail}
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
        scenarioItems={visibleScenarios}
        scenarioId={scenarioId}
        scenarioFilter={scenarioFilter}
        onScenarioFilter={setScenarioFilter}
        scenarioOriginCounts={scenarioOriginCounts}
        scenarioCategory={scenarioCategory}
        onScenarioCategory={setScenarioCategory}
        scenarioCategoryCounts={scenarioCategoryCounts}
        showRecommended={scenarios.some((s) => s.recommendation)}
        tenantName={tenantName}
        onNewScenario={() => setEditingScenario({ id: null })}
        onShowScenarioInfo={setInfoScenarioId}
        offerRandom={offerRandom}
        personas={personas}
        personaId={personaId}
        onShowPersonaInfo={setInfoPersonaId}
        selectedScenario={selectedScenario}
        selectedPersona={selectedPersona}
        loadError={loadError}
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
