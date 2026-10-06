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

/** The call's statistics (F-53), measured during the call (ADR 0048). A reading, never a judgement (ADR 0051). */
export default function MetricSection({
  measurements,
  findings = [],
  notes = {},
  sessionId = null,
  segments = [],
}: {
  measurements: Measurement[];
  /** Only decides which tiles open a page. */
  findings?: Finding[];
  notes?: Record<string, string>;
  /** Null for an unstored call. */
  sessionId?: string | null;
  /** Only to say a comparison exists (ADR 0081); it lives on the metric's page. */
  segments?: SegmentMeasurement[];
}) {
  // Paraverbal first: the reading the transcript cannot give.
  const [aspect, setAspect] = useState<MetricAspect>("how");

  const groups = metricGroups(measurements);
  const all = groups.flatMap((group) => group.measurements);

  const options: FilterOption<MetricAspect>[] = groups.map((group) => ({
    value: group.aspect,
    label: group.label,
    count: group.measurements.length,
  }));
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

      {/* Not in `METRIC_DISCLAIMER`: the PDF prints no readings. */}
      <p className="metric-disclaimer">
        {METRIC_DISCLAIMER} Wo „Einschätzung“ steht, haben wir die Schwellen selbst
        gesetzt; welche das sind, steht jeweils dabei.
      </p>

      <MetricNotes measured={all} segments={segments} />

      {/* Only for a stored Session (ADR 0066). */}
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

/** That a metric left no tile (ADR 0085), and that a stretch comparison exists (ADR 0081). */
function MetricNotes({
  measured,
  segments,
}: {
  measured: Measurement[];
  segments: SegmentMeasurement[];
}) {
  const shown = new Set(measured.map((m) => m.key));
  const missing = METRIC_KEYS.filter((key) => !shown.has(key)).length;
  // Distinct metrics: each compared one carries two rows.
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

/** Matches `intonation.RANGE_KEY` on the backend. */
const INTONATION_KEY = "intonation";

function Metric({
  measurement,
  sessionId,
  detailed,
}: {
  measurement: Measurement;
  sessionId: string | null;
  detailed: boolean;
}) {
  // Loudness as a course: a dB span reads like a level (ADR 0004/0051).
  const curve = measurement.key === "loudness" ? loudnessCourse(measurement.detail) : null;
  if (measurement.key === "loudness" && !curve) return null;

  const context = interruptionContext(measurement);
  const detail = metricSubline(measurement);
  // The light colours the reading only, never the tile (unvalidated thresholds),
  // and never F-35's semitone figure, a different measurement.
  const { label: reading, readingLight } = metricReading(measurement);

  const figure = formatMetricValue(measurement);

  // The reading leads, the semitone range stays under it (ADR 0077, 0088).
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

/** Context, never a rate: a rate put one interruption in a short call on the top step. */
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

/** A checklist's parts, each marked (F-63, ADR 0089). "Not recognised", never "missing". */
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
