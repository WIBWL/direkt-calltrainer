import { useState } from "react";
import { Link } from "react-router-dom";

import type { Finding, Measurement, MetricAspect, SegmentMeasurement } from "../protocol";
import { ROUTES, sessionMetricPath } from "../routes";
import { loudnessCourse } from "../utils/loudness";
import {
  formatMetricValue,
  METRIC_DISCLAIMER,
  METRIC_KEYS,
  metricParts,
  metricReading,
  metricSubline,
  openHint,
  type MetricPart,
} from "../utils/metrics";
import { metricGroups } from "../utils/reportOutline";
import FilterSlider, { type FilterOption } from "./FilterSlider";
import InfoDetails from "./InfoDetails";
import LoudnessCourse from "./LoudnessCourse";
import SectionHeading from "./SectionHeading";

/**
 * The call's statistics (F-53), computed during the call (ADR 0047/0048), so a Session
 * with no wrap-up still has them. A reading, never a judgement (ADR 0051), and the note
 * under the grid says so.
 */
export default function MetricSection({
  measurements,
  findings = [],
  notes = {},
  sessionId = null,
  segments = [],
}: {
  measurements: Measurement[];
  /** Individual moments noted during the call, e.g. F-51's interruptions.
   *  Used here only to decide which tiles have a page worth opening. */
  findings?: Finding[];
  /** The long explanation behind a metric's "i", by metric key. */
  notes?: Record<string, string>;
  /** The Session these figures belong to, for the per-metric page. Null on a
   *  call that was never stored, where there is nothing to link to. */
  sessionId?: string | null;
  /** The same metrics over the demanding stretches and over the rest
   *  (ADR 0081). Used here only to say that the comparison exists: it is two
   *  figures per metric, which is a table and belongs on the metric's own
   *  page. */
  segments?: SegmentMeasurement[];
}) {
  // Opens on the paraverbal half: the one reading the transcript cannot give.
  const [aspect, setAspect] = useState<MetricAspect>("how");

  const groups = metricGroups(measurements);
  const all = groups.flatMap((group) => group.measurements);

  const options: FilterOption<MetricAspect>[] = groups.map((group) => ({
    value: group.aspect,
    label: group.label,
    count: group.measurements.length,
  }));
  // Nothing to switch between when one half is empty: show what there is.
  const split = options.every((option) => option.count > 0);
  const current = groups.find((group) => group.aspect === aspect)!;
  const shown = split ? current.measurements : all;

  if (all.length === 0) return null;

  const detailed = new Set([
    ...findings.map((f) => f.metric_key).filter((key): key is string => key !== null),
    ...Object.keys(notes),
  ]);

  return (
    <section className="feedback-section feedback-metrics-section">
      <SectionHeading title="Kennzahlen zum Gespräch" />

      {split && (
        <div className="feedback-metrics-filter">
          <FilterSlider
            options={options}
            value={aspect}
            onChange={setAspect}
            label="Kennzahlen nach Art filtern"
          />
          <p className="feedback-metrics-lead">{current.lead}</p>
        </div>
      )}

      <div className="metric-grid">
        {shown.map((measurement) => (
          <Metric
            key={measurement.key}
            measurement={measurement}
            sessionId={sessionId}
            detailed={detailed.has(measurement.key)}
          />
        ))}
      </div>

      {/* Names the exception to the sentence above: two metrics carry a word beside their
          figure. Kept out of `METRIC_DISCLAIMER` because the PDF prints figures without
          readings. */}
      <p className="metric-disclaimer">
        {METRIC_DISCLAIMER} Wo „Einschätzung“ steht, haben wir die Schwellen selbst
        gesetzt; welche das sind, steht jeweils dabei.
      </p>

      <MetricNotes measured={all} segments={segments} />

      {/* Last, pointing to the same figure across trainings, which this screen cannot
          answer. Only for a stored Session: without consent there is nothing to compare
          (ADR 0066). */}
      {sessionId && (
        <p className="metric-progress-link">
          <Link to={ROUTES.progress}>
            Diese Zahlen über Ihre Trainings hinweg ansehen
          </Link>
        </p>
      )}
    </section>
  );
}

/**
 * What the grid cannot say: that a metric could not be measured and so left no tile
 * (ADR 0085; which one is not named, the frontend would have to guess why), and that a
 * second reading exists where the wrap-up marked demanding stretches (ADR 0081).
 */
function MetricNotes({
  measured,
  segments,
}: {
  measured: Measurement[];
  segments: SegmentMeasurement[];
}) {
  const shown = new Set(measured.map((m) => m.key));
  // Counted off the catalogue the frontend already keeps, so a metric added on
  // the backend does not have to be listed here a second time.
  const missing = METRIC_KEYS.filter((key) => !shown.has(key)).length;
  // Distinct metrics, not rows: each one that was compared carries two, one
  // per stretch. The wire never sends the whole call here -- that is what
  // `measurements` is -- so nothing has to be filtered out first.
  const compared = new Set(segments.map((entry) => entry.key)).size;

  if (missing === 0 && compared === 0) return null;

  return (
    <div className="metric-footnotes">
      {compared > 0 && (
        <p>
          Für {compared} dieser Kennzahlen wurde zusätzlich verglichen, wie Sie an den
          fordernden Stellen dieses Gesprächs gesprochen haben und wie im Rest. Der Vergleich
          steht auf der Seite der jeweiligen Kennzahl.
        </p>
      )}
      {missing > 0 && (
        <p>
          Nicht jede Kennzahl ließ sich in diesem Gespräch messen.{" "}
          <InfoDetails label="Woran das liegen kann">
            <p>
              Manche Kennzahlen brauchen eine Mindestlänge: Bei einem Gespräch von wenigen
              Sätzen gibt es zum Beispiel keinen Abschluss, der sich von der Begrüßung
              trennen ließe.
            </p>
            <p>
              Andere brauchen eine Aufnahme, in der sich Stille von Sprache trennen lässt.
              Läuft im Hintergrund ein Geräusch mit, findet das Verfahren keine Pausen mehr.
              Dann werden die betroffenen Kennzahlen weggelassen statt falsch angezeigt.
            </p>
            <p>
              In beiden Fällen sagt das etwas über die Aufnahme und nichts über Ihr Gespräch.
            </p>
          </InfoDetails>
        </p>
      )}
    </div>
  );
}

/** The one metric whose unit a reader cannot place. Matches
 *  `intonation.RANGE_KEY` on the backend. */
const INTONATION_KEY = "intonation";

function Metric({
  measurement,
  sessionId,
  detailed,
}: {
  measurement: Measurement;
  /** Null on a call that was never stored, where there is no page to open. */
  sessionId: string | null;
  /** Whether this metric has a page worth opening. */
  detailed: boolean;
}) {
  // Loudness is shown as a course, not a figure: its dB span reads like a level without
  // being one (ADR 0004/0051). The course arrives in the Measurement's detail (ADR 0091),
  // so the wrap-up's sentence about it cannot disagree with the picture.
  const curve = measurement.key === "loudness" ? loudnessCourse(measurement.detail) : null;
  if (measurement.key === "loudness" && !curve) return null;

  const context = interruptionContext(measurement);
  const detail = metricSubline(measurement);
  // The step this call landed on, in words, and its colour (`metricReading`; F-51's
  // traffic light and F-35's reading). The light colours the figure only, never the
  // whole tile: its thresholds are unvalidated working values (`interruptions.py`).
  // For F-35 the tile leads with the classification word, so the colour sits on that;
  // it must never sit on the semitone figure, a different measurement from the step's.
  const { label: reading, readingLight } = metricReading(measurement);

  const figure = formatMetricValue(measurement);

  // Intonation's unit is one a reader cannot place, so the reading leads and the
  // semitone range stands under it (ADR 0077). Never dropped: without it only the part
  // resting on thresholds would be left (ADR 0004/0051, ADR 0088).
  const melody = measurement.key === INTONATION_KEY;
  const parts = metricParts(measurement);

  const body = curve ? (
    <>
      <span className="metric-name">{measurement.name} im Gesprächsverlauf</span>
      <LoudnessCourse curve={curve} />
    </>
  ) : (
    <>
      <span className="metric-name">{measurement.name}</span>
      {parts ? (
        <MetricParts parts={parts} />
      ) : (
        <span className={`metric-value${readingLight ? ` metric-value-${readingLight}` : ""}`}>
          {melody && reading ? reading : figure}
        </span>
      )}

      {melody ? (
        <span className="metric-subline">
          {reading ? `Einschätzung · ${figure}` : "Zu wenig Stimme für eine Einordnung"}
        </span>
      ) : (
        detail && <span className="metric-subline">{detail}</span>
      )}

      {context && <span className="metric-context">{context}</span>}

      {reading && !melody && (
        <span className="metric-light-label">
          <span className={readingLight ? `metric-value-${readingLight}` : undefined}>
            {reading}
          </span>{" "}
          <span className="metric-light-caveat">(Einschätzung)</span>
        </span>
      )}
    </>
  );

  // One class list for both, so the loudness tile keeps its own width whether
  // or not it opens. It used to return early and could therefore never be a
  // link, which left the one tile carrying a drawing as the one tile with no
  // way to see it larger.
  const className = `metric${curve ? " metric-loudness" : ""}`;

  if (!detailed || !sessionId) {
    return <div className={className}>{body}</div>;
  }

  return (
    <Link
      className={`${className} metric-open`}
      to={sessionMetricPath(sessionId, measurement.key)}
    >
      {body}
      <span className="metric-open-hint">{openHint(measurement.key)}</span>
    </Link>
  );
}

/**
 * The count set against the call it happened in: context beside the figure, never a
 * rate (a rate put one interruption in a short call on the top step). Backchannels are
 * named as not counting, so an attentive call and an absent one read differently.
 */
function interruptionContext(measurement: Measurement): string | null {
  if (measurement.key !== "interruptions") return null;
  const detail = measurement.detail ?? {};
  const callMs = (detail.call_ms as number | undefined) ?? 0;
  const turns = detail.persona_turns as number | undefined;
  const backchannels = (detail.backchannel_count as number | undefined) ?? 0;

  const parts: string[] = [];
  if (callMs > 0) parts.push(`in ${Math.max(1, Math.round(callMs / 60000))} Gesprächsminuten`);
  if (turns) parts.push(`bei ${turns} Redebeiträgen des Gegenübers`);
  if (backchannels > 0) {
    parts.push(
      `${backchannels} bestätigende${backchannels === 1 ? "s Hörsignal" : " Hörsignale"} zählen nicht mit`,
    );
  }
  return parts.length > 0 ? parts.join(", ") : null;
}

/** A checklist metric's headline — the opening's (F-63) or the closing's
 *  (ADR 0089): its parts, each marked, in place of a count that reads like a
 *  grade. The screen reader hears "not recognised", never "missing": a bare
 *  name or a recap worded some other way slips past the patterns. */
function MetricParts({ parts }: { parts: MetricPart[] }) {
  return (
    <span className="metric-parts">
      {parts.map(({ key, label, said }) => (
        <span key={key} className={"metric-part" + (said ? " is-said" : "")}>
          <span aria-hidden="true">{said ? "✓" : "–"}</span> {label}
          <span className="visually-hidden">{said ? " erkannt" : " nicht erkannt"}</span>
        </span>
      ))}
    </span>
  );
}
