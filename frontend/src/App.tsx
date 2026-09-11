import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { apiFetch } from "./api";
import AppLayout from "./components/AppLayout";
import CallView from "./components/CallView";
import DiceRoll from "./components/DiceRoll";
import IncomingCall from "./components/IncomingCall";
import FeedbackView from "./components/FeedbackView";
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
import TranscriptView from "./components/TranscriptView";
import { useMicrophoneDevices } from "./hooks/useMicrophoneDevices";
import { useMicrophoneVAD } from "./hooks/useMicrophoneVAD";
import { useSessionSocket, type CommittedSession } from "./hooks/useSessionSocket";
import { useStreamedAudioPlayback } from "./hooks/useStreamedAudioPlayback";
import type { Persona, TranscriptEntry } from "./protocol";
import ReverseBriefPanel from "./components/ReverseBriefPanel";
import { ROUTES, type TrainingStart } from "./routes";
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

/** "brief" is the reverse's own pre-call screen (ADR 0070): the briefing on
 * its own, and a button to start. It stands where the microphone check stands
 * for an ordinary call — the Session is committed and pre-warming behind it
 * (ADR 0042) — and it exists because walking into a reverse is walking into a
 * case you have to argue, which takes a minute's reading first. */
type Screen = "setup" | "mic-check" | "brief" | "rolling" | "incoming" | "call" | "transcript";

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
  "all", "standard", "own", "followUp", "reverse", "tenant",
];

/** What the selection screen opens on (ADR 0072): everything, on both rows.
 * Opening on a shortlist (Standard + Betrieb & Störung, which this was) hides
 * the User's own Scenarios behind a filter they have to know to press — and
 * what is on screen is capped by `COLLAPSED_CARDS` anyway, so "Alle" is a
 * first page of the library rather than a wall of it. */
const DEFAULT_ORIGIN: LibraryFilter = "all";
const DEFAULT_CATEGORY: CategoryFilter = "all";

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
});

/** The Scenario to start on: the first the default filters actually show, so
 * the summary at the bottom of the screen does not name a card that is not on
 * it. Falls back to the first of all, for a library those filters leave empty. */
function firstSelectable(scenarios: ScenarioCard[]): string | null {
  const items = scenarios.map(toLibraryItem);
  const visible = items.find(
    (item) => matchesFilter(item, DEFAULT_ORIGIN) && matchesCategory(item, DEFAULT_CATEGORY),
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
  // from inside it (ADR 0076), so this opens first and the editor second.
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
  // Holds a just-received session.ended until playback actually finishes —
  // see the effect below.
  const [pendingEnd, setPendingEnd] = useState<PendingEnd | null>(null);
  // The committed Session: set when the user actually commits to one (the
  // "Session starten" click), never by the selection itself — see ADR 0042.
  // Nothing connects on its own, which is also what keeps a persistently
  // failing backend from looping: a failed Session is only ever retried by
  // another deliberate click, never automatically.
  const [committed, setCommitted] = useState<CommittedSession | null>(null);
  // The briefing shown during a reverse (ADR 0070). Held here rather than in
  // the screens because both the mic check and the call show it, and because
  // it is fetched once per committed Session rather than once per screen.
  const [reverseBrief, setReverseBrief] = useState<ReverseBrief | null>(null);
  // The drawn Scenario's name while it is still a secret (F-62): set only for
  // a Zufallsszenario, and the one thing the call screen must not show. Null
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
  // Whether there is anything to draw (F-62). Against the whole library, not
  // the filtered view, because that is what the draw itself reads.
  const offerRandom = scenarios.some(isDrawable);
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
        if (!restored) setScenarioId(firstSelectable(data));
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
      // Kept so a reverse started from this screen after a reload still knows
      // which Persona to put on the other end (ADR 0070).
      personaId,
      // The reveal is the payoff of a Zufallsszenario (F-62), so it survives a
      // reload of this screen for the same reason `personaName` does.
      revealedScenario: secretScenario,
    });
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
  // check. Taken by the setup screen's button and by the follow-up's "Starten"
  // alike, so the second one is the same act as the first and not a shortcut
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
      // What is not skipped is the screen that starts the call: a reverse gets
      // its briefing to read before arguing the case, everything else the
      // ringing phone (F-63). Nothing goes straight into a conversation — the
      // last press before someone has to speak is always their own.
      setScreen(skipMicCheck ? (reverse ? "brief" : "incoming") : "mic-check");
      if (skipMicCheck) setIsMicrophoneMuted(false);
    },
    [],
  );

  const handleStartSession = useCallback(() => {
    if (personaId === null || scenarioId === null) return;

    // The Zufallsszenario (F-62) is drawn here and nowhere earlier: selecting
    // the tile is not yet a case, and a draw made on selection would be a
    // different one each time the User changed their mind about the Persona.
    if (scenarioId === RANDOM_SCENARIO_ID) {
      const drawn = drawRandomScenario(scenarios);
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
  }, [personaId, scenarioId, scenarios, selectedScenario, beginSession]);

  // From the post-call screen into the reverse (F-61, ADR 0070): the same
  // Persona, the new Scenario, no detour through the setup screen. Taken by the
  // card's second button, once the Scenario exists and the User has read what
  // it is — the first one only wrote it. Goes through the same `beginSession`
  // as the follow-up's "Starten", which lands it on the briefing screen rather
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
    setScreen("call");
  }, [playback, socket.sendActivate]);

  // The microphone check's own button. A Zufallsszenario gets the die in
  // between (F-62); everything else goes straight through. Under reduced
  // motion the screen is skipped rather than shown still: the animation is the
  // whole of what it has to say, and without it it is two seconds of nothing.
  const handleMicConfirmed = useCallback(() => {
    // A reverse does not go from here into the call: it goes to its briefing,
    // behind the card turn (F-61). That is the same screen the offer under a
    // wrap-up leads to, reached the same way, so the two arrive at an
    // identical place from opposite ends of the app. The call itself starts on
    // that screen's own button — nothing is activated here.
    //
    // The two branches cannot both apply: a reverse is never drawn, because
    // reverses are not in the Zufallsszenario's pool.
    if (committed?.reverse) {
      playReverse(() => setScreen("brief"));
      return;
    }
    // A Zufallsszenario is dealt its case first and goes straight to the die:
    // the fade belongs between the throw and the call, not in front of the
    // throw, so the cut it covers is the one into the ringing phone (F-63).
    if (secretScenario !== null && !prefersReducedMotion()) {
      setScreen("rolling");
      return;
    }
    playFade(() => setScreen("incoming"));
  }, [committed, secretScenario, playReverse, playFade]);

  // The throw ends where every ordinary call now begins: at the ringing phone,
  // through the same fade an ordinary call gets. Nothing can cancel it, so the
  // timer is the whole of the screen's logic.
  useEffect(() => {
    if (screen !== "rolling") return undefined;
    const timer = window.setTimeout(() => playFade(() => setScreen("incoming")), ROLL_MS);
    return () => window.clearTimeout(timer);
  }, [screen, playFade]);

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
      // has just been read, not from the selection screen. The fade is the
      // same one the check's own button plays, because the screen it covers is
      // the same one — the wrap-up giving way to the ringing phone.
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

  const scenarioItems = scenarios.map(toLibraryItem);
  // The two levels combine: level 1 picks whose Scenario it is, level 2 what
  // kind of call it is (ADR 0072).
  const byOrigin = scenarioItems.filter((s) => matchesFilter(s, scenarioFilter));
  const byCategory = scenarioItems.filter((s) => matchesCategory(s, scenarioCategory));
  const visibleScenarios = byOrigin.filter((s) => matchesCategory(s, scenarioCategory));
  // Each row is counted against the *other* row's selection, never its own, so
  // an option's number is what picking it would actually yield.
  const scenarioOriginCounts = Object.fromEntries(
    ORIGIN_FILTERS.map((f) => [f, byCategory.filter((s) => matchesFilter(s, f)).length]),
  ) as Record<LibraryFilter, number>;
  const scenarioCategoryCounts = Object.fromEntries(
    CATEGORY_FILTERS.map((c) => [c, byOrigin.filter((s) => matchesCategory(s, c)).length]),
  ) as Record<CategoryFilter, number>;

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
    if (!committed?.reverse) return null;
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
          {/* Same door out as the microphone check's: leaving drops the
              committed Session rather than holding its connection open. */}
          <button type="button" className="cancel-button" onClick={handleCancelMicCheck}>
            Abbrechen
          </button>
        </div>
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
    return (
      <AppLayout step="prepare" navigationLocked pageClassName="mic-check-page">
        <MicCheck
          deviceId={micDeviceId}
          devices={micDevices}
          onDeviceChange={setMicDeviceId}
          onDevicesRefresh={refreshMicDevices}
          onConfirmed={handleMicConfirmed}
          onCancel={handleCancelMicCheck}
          briefing={selectedScenario?.briefing}
        />
      </AppLayout>
    );
  }

  if (screen === "incoming") {
    return (
      <AppLayout step="prepare" navigationLocked pageClassName="incoming-page">
        <IncomingCall
          personaName={personaName}
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
    const brief = briefPanel("call");
    return (
      <AppLayout
        step="call"
        navigationLocked
        // Wider only while a briefing is beside the call: the 800px column is
        // right for a screen whose whole content is one animation.
        pageClassName={committed?.reverse ? "call-page call-page-wide" : "call-page"}
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

  if (screen === "transcript") {
    return (
      <AppLayout step="feedback">
        <TranscriptView
          transcript={transcript}
          personaName={personaName}
          onRestart={handleRestart}
          revealedScenario={secretScenario ?? restored?.revealedScenario ?? null}
          feedback={
            <FeedbackView
              sessionId={endedSessionId}
              followUp={{
                onEdit: (id) => setEditingScenario({ id }),
                onStart: handleStartFollowUp,
                // The new row is not in this screen's library copy yet, and
                // the setup screen reads its names off that.
                onCreated: () => void reloadScenarios(),
              }}
              onReverse={handleReverse}
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
