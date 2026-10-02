import type { ReactNode } from "react";

import type { Measurement, SessionTurn } from "../protocol";
import { formatNumber, metricParts } from "../utils/metrics";
import { fillerHits, questionsIn } from "../utils/transcriptEvidence";
import { loudnessCourse } from "../utils/loudness";
import { formatOffset } from "../utils/time";
import LoudnessCourse from "./LoudnessCourse";

/**
 * What a figure was read off, on the metric's own page (ADR 0098). Nothing is recomputed: blocks read the stored
 * `detail` (ADR 0029) or quote the transcript, since a second client-side arithmetic would eventually disagree.
 * Missing detail is said, not derived. Nothing judges (ADR 0004/0051). Intonation and interruptions have own blocks.
 */
export default function MetricEvidence({
  measurement,
  turns,
}: {
  measurement: Measurement;
  turns: SessionTurn[];
}) {
  const detail = measurement.detail ?? {};
  const userTurns = turns.filter((turn) => turn.speaker === "user");

  switch (measurement.key) {
    case "talk_share":
      return <TalkShare detail={detail} />;
    case "questions":
      return <Questions detail={detail} turns={userTurns} />;
    case "word_count":
      return <WordCount detail={detail} />;
    case "pace":
      return <Pace detail={detail} />;
    case "fillers":
      return <Fillers detail={detail} turns={userTurns} />;
    case "repetitions":
      return <Repetitions detail={detail} />;
    case "opening":
      return <Opening measurement={measurement} detail={detail} turns={userTurns} />;
    case "closing":
      return <Closing measurement={measurement} detail={detail} turns={userTurns} />;
    case "pauses":
      return <Pauses detail={detail} />;
    case "phonation_share":
      return <Phonation detail={detail} />;
    case "run_length":
      return <RunLength detail={detail} />;
    case "reaction_time":
      return <ReactionTime detail={detail} turns={turns} />;
    case "hesitations":
      return <Hesitations detail={detail} turns={userTurns} />;
    case "loudness":
      return <Loudness detail={detail} />;
    default:
      return null;
  }
}

/** A block with the heading every other section on this page carries. */
function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <>
      <h2>{title}</h2>
      <div className="card">{children}</div>
    </>
  );
}

/** One quoted stretch of the call, with the moment it was said. */
function Quote({ at, children }: { at?: number; children: ReactNode }) {
  return (
    <blockquote className="evidence-quote">
      {at !== undefined && <span className="evidence-time">{formatOffset(at)}</span>}
      <p>{children}</p>
    </blockquote>
  );
}

/** A figure with its name under it, for the two or three numbers a detail
 *  holds beside the measurement itself. */
function Facts({ items }: { items: { label: string; value: string }[] }) {
  return (
    <ul className="evidence-facts">
      {items.map((item) => (
        <li key={item.label}>
          <span className="evidence-fact-value">{item.value}</span>
          <span className="evidence-fact-label">{item.label}</span>
        </li>
      ))}
    </ul>
  );
}

function seconds(ms: unknown): string | null {
  return typeof ms === "number" ? `${formatNumber(ms / 1000, 1)} s` : null;
}

function number(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

// --- The blocks --------------------------------------------------------------

/**
 * Both sides' speaking time. The Persona's bar carries no comment: it is a synthesized voice at a fixed rate,
 * so a remark about it would be about a setting (ADR 0051).
 */
function TalkShare({ detail }: { detail: Record<string, unknown> }) {
  const user = number(detail.user_ms);
  const persona = number(detail.persona_ms);
  if (user === null || persona === null || user + persona <= 0) return null;

  const share = (user * 100) / (user + persona);

  return (
    <Block title="Woraus der Anteil entsteht">
      <ul className="evidence-bars">
        <Bar label="Sie" ms={user} share={share} />
        <Bar label="Ihr Gegenüber" ms={persona} share={100 - share} />
      </ul>
      <p className="muted">
        Gemessen wird gesprochene Zeit. Die Zeit, in der beide Seiten schwiegen, steht in
        keiner der beiden Zeilen.
      </p>
    </Block>
  );
}

function Bar({ label, ms, share }: { label: string; ms: number; share: number }) {
  return (
    <li className="evidence-bar">
      <span className="evidence-bar-label">{label}</span>
      <span className="evidence-bar-track">
        <span className="evidence-bar-fill" style={{ width: `${share}%` }} />
      </span>
      <span className="evidence-bar-value">
        {formatNumber(share, 0)} % · {formatOffset(ms)}
      </span>
    </li>
  );
}

/**
 * Every question that was counted, quoted. Cut at the question marks, not at sentence boundaries, so the list
 * holds exactly as many entries as the figure says.
 */
function Questions({
  detail,
  turns,
}: {
  detail: Record<string, unknown>;
  turns: SessionTurn[];
}) {
  const asked = turns.flatMap((turn) =>
    questionsIn(turn.transcript).map((text) => ({ text, at: turn.start_offset_ms })),
  );
  const open = number(detail.open);
  const closed = number(detail.closed);

  if (asked.length === 0) {
    return (
      <Block title="Ihre Fragen">
        <p>In diesem Gespräch steht in Ihren Beiträgen keine Frage.</p>
      </Block>
    );
  }

  return (
    <Block title={asked.length === 1 ? "Ihre Frage" : "Ihre Fragen"}>
      {open !== null && closed !== null && (
        <Facts
          items={[
            { label: open === 1 ? "offene Frage" : "offene Fragen", value: String(open) },
            {
              label: closed === 1 ? "geschlossene Frage" : "geschlossene Fragen",
              value: String(closed),
            },
          ]}
        />
      )}
      {asked.map((question, index) => (
        <Quote key={`${question.at}-${index}`} at={question.at}>
          {question.text}
        </Quote>
      ))}
    </Block>
  );
}

function WordCount({ detail }: { detail: Record<string, unknown> }) {
  const sentences = number(detail.sentence_count);
  const perSentence = number(detail.words_per_sentence);
  if (sentences === null) return null;

  return (
    <Block title="Wie sich das verteilt">
      <Facts
        items={[
          { label: sentences === 1 ? "Satz" : "Sätze", value: String(sentences) },
          ...(perSentence === null
            ? []
            : [{ label: "Wörter je Satz", value: formatNumber(perSentence, 1) }]),
        ]}
      />
      <p className="muted">
        Als Satzende zählt ein Punkt, ein Ausrufezeichen oder ein Fragezeichen im Transkript.
        Was Sie ohne Punkt aneinandergereiht haben, steht hier als ein Satz.
      </p>
    </Block>
  );
}

/**
 * The filler words (from the stored detail) and the sentences they fell in (from the transcript). The marked
 * word is the same string that was counted, so the count can be checked against the call.
 */
function Fillers({
  detail,
  turns,
}: {
  detail: Record<string, unknown>;
  turns: SessionTurn[];
}) {
  const words = detail.words;
  const counted =
    words && typeof words === "object"
      ? Object.entries(words as Record<string, number>)
      : [];

  if (counted.length === 0) {
    return (
      <Block title="Ihre Füllwörter">
        <p>In diesem Gespräch ist keines der gesuchten Wörter vorgekommen.</p>
      </Block>
    );
  }

  const hits = fillerHits(
    turns.map((turn) => ({ text: turn.transcript, at: turn.start_offset_ms })),
    counted.map(([word]) => word),
  );

  return (
    <Block title="Ihre Füllwörter">
      <ul className="evidence-chips">
        {counted.map(([word, count]) => (
          <li key={word} className="evidence-chip">
            {word}
            <span className="evidence-chip-count">{count}×</span>
          </li>
        ))}
      </ul>

      {hits.length > 0 && (
        <>
          <p className="evidence-lead">
            {hits.length === 1 ? "Die Stelle im Gespräch" : `Die ersten ${hits.length} Stellen`}:
          </p>
          {hits.map((hit, index) => (
            <Quote key={`${hit.at}-${index}`} at={hit.at}>
              {hit.before}
              <span className="evidence-hit">{hit.word}</span>
              {hit.after}
            </Quote>
          ))}
        </>
      )}
    </Block>
  );
}

function Repetitions({ detail }: { detail: Record<string, unknown> }) {
  const passages = Array.isArray(detail.passages) ? (detail.passages as string[]) : [];
  const share = number(detail.share_of_words);

  if (passages.length === 0) {
    return (
      <Block title="Wiederholte Passagen">
        <p>
          In diesem Gespräch hat sich keine Passage von vier Wörtern oder mehr wörtlich
          wiederholt.
        </p>
      </Block>
    );
  }

  return (
    <Block title="Wiederholte Passagen">
      {share !== null && (
        <p className="evidence-lead">
          {formatNumber(share, 0)} % Ihrer Wörter stehen in einer solchen Passage.
        </p>
      )}
      {passages.map((passage, index) => (
        <Quote key={index}>{passage}</Quote>
      ))}
      <p className="muted">
        Gezeigt werden höchstens fünf. Gesucht wird wörtliche Übereinstimmung; dasselbe mit
        anderen Worten gesagt steht hier nicht.
      </p>
    </Block>
  );
}

/** The user's first turn, with the parts that were looked for beside it. */
function Opening({
  measurement,
  detail,
  turns,
}: {
  measurement: Measurement;
  detail: Record<string, unknown>;
  turns: SessionTurn[];
}) {
  const first = turns[0];
  const ratio = number(detail.pace_ratio);

  return (
    <Block title="Ihr erster Beitrag">
      {first ? <Quote at={first.start_offset_ms}>{first.transcript}</Quote> : null}
      <PartList measurement={measurement} />
      {ratio !== null && (
        <p className="muted">
          Ihr Tempo lag hier bei {formatNumber(ratio * 100, 0)} % Ihres Tempos im übrigen
          Gespräch. Schneller oder langsamer ist beides möglich; einen richtigen Wert dafür
          gibt es nicht.
        </p>
      )}
    </Block>
  );
}

/** The last turns the closing was read in, and the parts that were looked for. */
function Closing({
  measurement,
  detail,
  turns,
}: {
  measurement: Measurement;
  detail: Record<string, unknown>;
  turns: SessionTurn[];
}) {
  // How many turns were read travels in the detail, so this quotes exactly the
  // window that was checked rather than a number written twice (ADR 0063).
  const window = number(detail.turns_read) ?? 2;
  const read = turns.slice(-window);

  return (
    <Block title={read.length === 1 ? "Ihr letzter Beitrag" : `Ihre letzten ${read.length} Beiträge`}>
      {read.map((turn) => (
        <Quote key={turn.turn_id} at={turn.start_offset_ms}>
          {turn.transcript}
        </Quote>
      ))}
      <PartList measurement={measurement} />
    </Block>
  );
}

/**
 * A checklist's parts, in words. "Nicht erkannt", never "fehlt": parts are found by their usual phrasing, and a
 * greeting worded differently slips past (ADR 0086).
 */
function PartList({ measurement }: { measurement: Measurement }) {
  const parts = metricParts(measurement);
  if (!parts) return null;

  return (
    <ul className="evidence-parts">
      {parts.map((part) => (
        <li key={part.key} className={part.said ? "is-said" : undefined}>
          <span aria-hidden="true">{part.said ? "✓" : "–"}</span> {part.label}
          <span className="evidence-part-state">{part.said ? "erkannt" : "nicht erkannt"}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Every pause that went into the average, in order, on the user's own speaking time: the stored offsets count
 * the user's turns concatenated, so nothing in the strip stands for the Persona talking.
 */
function Pauses({ detail }: { detail: Record<string, unknown> }) {
  const events = Array.isArray(detail.pause_events)
    ? (detail.pause_events as { start_ms: number; duration_ms: number }[])
    : [];
  const count = number(detail.count);
  const total = number(detail.total_s);

  if (events.length === 0) return null;

  const end = Math.max(...events.map((e) => e.start_ms + e.duration_ms));
  const longest = Math.max(...events.map((e) => e.duration_ms));

  return (
    <Block title={count === 1 ? "Die gemessene Pause" : `Die ${events.length} gemessenen Pausen`}>
      <Facts
        items={[
          ...(total === null
            ? []
            : [{ label: "zusammen", value: `${formatNumber(total, 1)} s` }]),
          { label: "längste", value: `${formatNumber(longest / 1000, 1)} s` },
        ]}
      />

      <div
        className="evidence-strip"
        role="img"
        aria-label={`${events.length} Pausen, verteilt über Ihre Sprechzeit, die längste ${formatNumber(longest / 1000, 1)} Sekunden`}
      >
        {events.map((event, index) => (
          <span
            key={index}
            className="evidence-strip-mark"
            style={{
              left: `${(event.start_ms / end) * 100}%`,
              width: `${Math.max(0.6, (event.duration_ms / end) * 100)}%`,
            }}
          />
        ))}
      </div>
      <p className="evidence-axis">Anfang Ihrer Sprechzeit → Ende</p>
      <p className="muted">
        Jeder Strich ist eine Pause, seine Breite ihre Länge. Aufgetragen ist Ihre eigene
        Sprechzeit, nicht die Uhr des Gesprächs: Die Beiträge Ihres Gegenübers liegen nicht
        dazwischen.
      </p>
    </Block>
  );
}

function Phonation({ detail }: { detail: Record<string, unknown> }) {
  const speech = number(detail.speech_ms);
  const phonation = number(detail.phonation_ms);
  if (speech === null || phonation === null || speech <= 0) return null;

  const share = (phonation * 100) / speech;

  return (
    <Block title="Woraus der Anteil entsteht">
      <ul className="evidence-bars">
        <Bar label="gesprochen" ms={phonation} share={share} />
        <Bar label="Stille darin" ms={speech - phonation} share={100 - share} />
      </ul>
      <p className="muted">
        Beides zusammen ist die Länge Ihrer Aufnahmen. Der kurze Vorlauf und Nachlauf, den
        jede Aufnahme mitschneidet, zählt zur Stille.
      </p>
    </Block>
  );
}

function RunLength({ detail }: { detail: Record<string, unknown> }) {
  const runs = number(detail.runs);
  const phonation = seconds(detail.phonation_ms);
  const utterances = number(detail.utterances);
  const pauses = number(detail.pause_count);
  if (runs === null) return null;

  return (
    <Block title="Woraus der Wert entsteht">
      <Facts
        items={[
          { label: runs === 1 ? "Sprechabschnitt" : "Sprechabschnitte", value: String(runs) },
          ...(phonation === null ? [] : [{ label: "reine Sprechzeit", value: phonation }]),
        ]}
      />
      <p className="muted">
        {utterances !== null && pauses !== null ? (
          <>
            Ihre {utterances} Beiträge wurden von {pauses} Pausen geteilt, das ergibt {runs}{" "}
            Abschnitte. Die Kennzahl ist Ihre Sprechzeit geteilt durch diese Zahl.
          </>
        ) : (
          <>Die Kennzahl ist Ihre reine Sprechzeit geteilt durch die Zahl der Abschnitte.</>
        )}
      </p>
    </Block>
  );
}

/**
 * Every silence that went into the average, and the exchange the longest one stood in — the question waiting
 * through a pause usually explains it. Takes every Turn, not only the user's: the Persona's line before the
 * silence is matched on the offset the gap was measured from, so the two cannot disagree.
 */
function ReactionTime({
  detail,
  turns,
}: {
  detail: Record<string, unknown>;
  turns: SessionTurn[];
}) {
  const longest = number(detail.longest_s);
  const count = number(detail.count);
  const gaps = Array.isArray(detail.gaps)
    ? (detail.gaps as { at_ms: number; duration_ms: number }[])
    : [];
  if (longest === null && count === null) return null;

  // The longest by measurement, not by a second comparison of our own: the
  // stored figure decides, and the entry is the one that carries it.
  const peak = gaps.reduce<{ at_ms: number; duration_ms: number } | null>(
    (best, gap) => (best === null || gap.duration_ms > best.duration_ms ? gap : best),
    null,
  );
  const reply = peak ? turns.find((turn) => turn.start_offset_ms === peak.at_ms) : undefined;
  const asked = peak
    ? turns.filter((turn) => turn.speaker === "persona" && turn.start_offset_ms < peak.at_ms).pop()
    : undefined;

  return (
    <Block title="Woraus der Mittelwert entsteht">
      <Facts
        items={[
          ...(count === null
            ? []
            : [{ label: count === 1 ? "gemessene Pause" : "gemessene Pausen", value: String(count) }]),
          ...(longest === null
            ? []
            : [{ label: "längste davon", value: `${formatNumber(longest, 1)} s` }]),
        ]}
      />

      {peak && (asked || reply) && (
        <>
          <p className="evidence-lead">Die längste Pause stand hier:</p>
          {asked && <Quote at={asked.start_offset_ms}>{asked.transcript}</Quote>}
          <p className="evidence-gap">
            {formatNumber(peak.duration_ms / 1000, 1)} s Pause
          </p>
          {reply && <Quote at={reply.start_offset_ms}>{reply.transcript}</Quote>}
        </>
      )}

      {gaps.length > 1 && (
        <ul className="evidence-gaps">
          {gaps.map((gap) => (
            <li key={gap.at_ms} className={gap === peak ? "is-peak" : undefined}>
              <span className="evidence-time">{formatOffset(gap.at_ms)}</span>
              <span>{formatNumber(gap.duration_ms / 1000, 1)} s</span>
            </li>
          ))}
        </ul>
      )}

      <p className="muted">
        Gemessen wird vor jedem Ihrer Beiträge, der auf eine Äußerung Ihres Gegenübers folgt.
        Ihr erster Beitrag und ein Beitrag, mit dem Sie hineingegangen sind, zählen nicht mit.
        Was die Technik zum Antworten braucht, liegt außerhalb dieser Zeit.
      </p>
    </Block>
  );
}

/** Words over speaking time, as the division it is. */
function Pace({ detail }: { detail: Record<string, unknown> }) {
  const words = number(detail.words);
  const phonation = number(detail.phonation_ms);
  if (words === null || phonation === null || phonation <= 0) return null;

  return (
    <Block title="Woraus der Wert entsteht">
      <Facts
        items={[
          { label: "gesprochene Wörter", value: String(words) },
          { label: "reine Sprechzeit", value: `${formatNumber(phonation / 60000, 1)} min` },
        ]}
      />
      <p className="muted">
        Das eine geteilt durch das andere. Im Nenner steht nur die Zeit, in der Sie wirklich
        gesprochen haben, nicht die Länge Ihrer Aufnahmen: Deshalb liegt der Wert höher als
        ein Tempo, das über die ganze Gesprächszeit gerechnet ist.
      </p>
    </Block>
  );
}

/**
 * The held sounds, quoted by the utterance they fell in, not pinned to a word: the recogniser removes exactly
 * these sounds from the transcript, so the sentence is as precise as the stored facts allow.
 */
function Hesitations({
  detail,
  turns,
}: {
  detail: Record<string, unknown>;
  turns: SessionTurn[];
}) {
  const total = seconds(detail.total_ms);
  const holds = Array.isArray(detail.holds)
    ? (detail.holds as { turn: number; start_ms: number; duration_ms: number }[])
    : [];

  if (total === null) return null;

  // One row per utterance that held any, newest last, so the quotes read in
  // the order of the call.
  const byTurn = new Map<number, number>();
  for (const hold of holds) byTurn.set(hold.turn, (byTurn.get(hold.turn) ?? 0) + 1);

  return (
    <Block title="Woraus die Zahl entsteht">
      <Facts items={[{ label: "zusammen gehaltene Laute", value: total }]} />

      {byTurn.size === 0 ? (
        <p className="muted">
          Wo genau sie lagen, ist für dieses Training nicht festgehalten. Die Zahl entsteht
          aus dem Tonhöhenverlauf und nicht aus dem Transkript, in dem Verzögerungslaute gar
          nicht auftauchen.
        </p>
      ) : (
        <>
          <p className="evidence-lead">In diesen Beiträgen:</p>
          {[...byTurn.entries()].map(([index, count]) => {
            const turn = turns[index];
            if (!turn) return null;
            return (
              <Quote key={index} at={turn.start_offset_ms}>
                {turn.transcript}
                <span className="evidence-part-state">
                  {count === 1 ? "ein gehaltener Laut" : `${count} gehaltene Laute`}
                </span>
              </Quote>
            );
          })}
          <p className="muted">
            Im Transkript steht der Laut nicht: Die Spracherkennung räumt ihn weg. Deshalb
            wird hier der Beitrag genannt und nicht die Stelle im Satz.
          </p>
        </>
      )}
    </Block>
  );
}

function Loudness({ detail }: { detail: Record<string, unknown> }) {
  // The course arrives read: band, smoothing and stretches are derived by the
  // server on every read (ADR 0091), from the same function that writes the
  // wrap-up's sentence about it. This block only draws it.
  const curve = loudnessCourse(detail);
  if (!curve) return null;

  return (
    <Block title="Ihr Verlauf im Gespräch">
      <LoudnessCourse curve={curve} />
    </Block>
  );
}
