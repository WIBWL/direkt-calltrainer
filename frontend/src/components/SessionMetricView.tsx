import { Link, useParams } from "react-router-dom";

import { useStoredSession } from "../hooks/useStoredSession";
import type { Finding, SessionTurn, TrafficLight } from "../protocol";
import { ROUTES, sessionPath } from "../routes";
import { formatOffset } from "../utils/time";
import { pairFor } from "../utils/segmentStats";
import AppLayout from "./AppLayout";
import IntonationReading from "./IntonationReading";
import MetricScale from "./MetricScale";
import SegmentComparison from "./SegmentComparison";

/** Counts read without decimals, everything else with one. The unit follows,
 *  except for "count", which the figure already is. */
function formatFigure(value: number, unit: string | null): string {
  const text = unit === "Anzahl" ? value.toFixed(0) : value.toFixed(1);
  return unit && unit !== "Anzahl" ? `${text} ${unit}` : text;
}

/**
 * One metric of one training, in full (F-51's interruptions, F-35's intonation).
 *
 * Its own page rather than a panel inside the wrap-up. The excerpts run to
 * several lines each, a call with four interruptions would push everything
 * below it off the screen, and this is something a user may want to link to or
 * come back to. Back is the browser's.
 *
 * Reads the Session once and never polls, like `PastSessionView`: whatever the
 * database holds for a finished call is final.
 */
export default function SessionMetricView() {
  const { sessionId, metricKey } = useParams<{ sessionId: string; metricKey: string }>();
  const { detail, state } = useStoredSession(sessionId ?? null);

  const back = (
    <Link to={sessionId ? sessionPath(sessionId) : ROUTES.profile} className="back-link">
      Zurück zum Training
    </Link>
  );

  if (state === "loading") {
    return (
      <AppLayout pageClassName="app-page-narrow metric-page">
        {back}
        <p className="muted">Wird geladen …</p>
      </AppLayout>
    );
  }

  const measurement = detail?.measurements.find((m) => m.key === metricKey);
  if (!detail || !measurement) {
    return (
      <AppLayout pageClassName="app-page-narrow metric-page">
        {back}
        <h1>Kennzahl</h1>
        <div className="card">
          <p>Zu diesem Training gibt es diese Kennzahl nicht.</p>
        </div>
      </AppLayout>
    );
  }

  const findings = detail.findings.filter((f) => f.metric_key === metricKey);
  // The same metric over the demanding stretches and over the rest, where
  // this call had any (ADR 0081). Absent on a call nobody pushed back in, and
  // on every call recorded before the per-utterance facts were kept.
  const pair = pairFor(detail.segments, metricKey ?? "");
  const steps = detail.metric_scales[metricKey ?? ""] ?? [];
  const note = detail.metric_notes[metricKey ?? ""];
  const light = measurement.detail?.light as TrafficLight | undefined;
  // Which step of the scale this call landed on, and how it is said. Both come
  // from the backend beside the thresholds they belong to, so a recalibration
  // cannot leave a stale word behind here (`api/sessions.py::_served_detail`).
  const current = (measurement.detail?.liveliness ?? light) as string | undefined;
  const reading = (measurement.detail?.light_label ??
    measurement.detail?.liveliness_label) as string | undefined;
  // F-51's light belongs to the figure and colours it. F-35's belongs to the
  // liveliness, which is a different figure from the range shown here, so it
  // colours the word and never the number: a green semitone count would be a
  // colour sitting over something it was not read from (ADR 0077).
  const readingLight = (measurement.detail?.liveliness_light ?? light) as
    | TrafficLight
    | undefined;

  return (
    <AppLayout pageClassName="app-page-narrow metric-page">
      {back}
      <h1>{measurement.name}</h1>
      <p className="page-lead">
        {detail.scenario} · Gespräch mit {detail.persona}
      </p>

      <div className="card">
        <p className="metric-page-figure">
          <span className={light ? `metric-value-${light}` : undefined}>
            {formatFigure(measurement.value, measurement.unit)}
          </span>
          {reading && (
            <span className="metric-light-label">
              <span className={readingLight ? `metric-value-${readingLight}` : undefined}>
                {reading}
              </span>{" "}
              <span className="metric-light-caveat">(Einschätzung)</span>
            </span>
          )}
        </p>

        <MetricScale steps={steps} current={current} />

        {note && <p className="metric-note">{note}</p>}
      </div>

      {metricKey === "intonation" && (
        <div className="card">
          <IntonationReading
            measurement={measurement}
            toneFit={detail.feedback?.tone_fit ?? null}
          />
        </div>
      )}

      {pair && (
        <>
          <h2>Unter Druck und sonst</h2>
          <div className="card">
            <SegmentComparison pairs={[pair]} />
          </div>
        </>
      )}

      {findings.length > 0 && (
        <>
          <h2>
            {findings.length === 1
              ? "Die Stelle im Gespräch"
              : `Die ${findings.length} Stellen im Gespräch`}
          </h2>
          <div className="card">
            <InterruptionDetail findings={findings} turns={detail.turns} />
          </div>
        </>
      )}
    </AppLayout>
  );
}

/**
 * The transcript around one interruption (F-51).
 *
 * A timestamp alone tells the user that something happened at 2:48, which they
 * cannot check against a memory of the call. What they can check is the
 * sentence: their own line, the Persona's line it cut into, and what the
 * Persona had been about to say next.
 *
 * That last part is the counterfactual and is styled as one. It is not part of
 * the transcript and never was heard: the server keeps it aside precisely so it
 * cannot leak into the conversation the model reads (ADR 0035). For calls
 * recorded before it was kept it is simply absent, which the block says rather
 * than leaving a gap.
 */
function InterruptionDetail({
  findings,
  turns,
}: {
  findings: Finding[];
  turns: SessionTurn[];
}) {
  if (findings.length === 0) return null;

  return (
    <ol className="interruptions">
      {findings.map((finding) => {
        const at = finding.offset_ms ?? 0;
        // The user line that starts at this moment, and the Persona line that
        // was still running when it did. Matched on the offsets the finding was
        // computed from, so the two cannot disagree.
        const user = turns.find((turn) => turn.speaker === "user" && turn.start_offset_ms === at);
        const persona = turns
          .filter(
            (turn) =>
              turn.speaker === "persona" &&
              turn.start_offset_ms <= at &&
              at < turn.start_offset_ms + (turn.duration_ms ?? 0),
          )
          .pop();

        return (
          <li className="interruption" key={`${finding.category}-${at}`}>
            <div className="interruption-time">{formatOffset(at)}</div>

            {persona && (
              <p className="interruption-line">
                <span className="interruption-speaker">Gegenüber:</span>{" "}
                <span>{persona.transcript.replace(" ... [unterbrochen]", "")}</span>
                <span className="interruption-cut" aria-hidden="true" />
                {persona.unheard_text ? (
                  <span className="interruption-unheard" title="nicht mehr gesprochen">
                    {persona.unheard_text}
                  </span>
                ) : (
                  <span className="interruption-unheard is-missing">
                    (was danach kam, wurde für dieses Training nicht mitgeschrieben)
                  </span>
                )}
              </p>
            )}

            {user && (
              <p className="interruption-line interruption-user">
                <span className="interruption-speaker">Sie:</span> {user.transcript}
              </p>
            )}

            {!persona && !user && (
              <p className="interruption-line muted">{finding.description}</p>
            )}
          </li>
        );
      })}
    </ol>
  );
}

