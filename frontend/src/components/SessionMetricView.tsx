import { Link, useParams } from "react-router-dom";

import { useStoredSession } from "../hooks/useStoredSession";
import type { Finding, SessionTurn } from "../protocol";
import { ROUTES, progressMetricPath, sessionPath } from "../routes";
import { comparableAcrossCalls, formatValue, metricReading } from "../utils/metrics";
import { formatOffset } from "../utils/time";
import { pairFor } from "../utils/segmentStats";
import AppLayout from "./AppLayout";
import IntonationReading from "./IntonationReading";
import MetricEvidence from "./MetricEvidence";
import MetricScale from "./MetricScale";
import SegmentComparison from "./SegmentComparison";

/** One metric of one training, on its own route. Read once, like `PastSessionView`. */
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
  // ADR 0081; absent where nobody pushed back.
  const pair = pairFor(detail.segments, metricKey ?? "");
  const steps = detail.metric_scales[metricKey ?? ""] ?? [];
  const note = detail.metric_notes[metricKey ?? ""];
  // F-51's light colours the figure; F-35's only the word (ADR 0077).
  const {
    label: reading,
    step: current,
    figureLight: light,
    readingLight,
  } = metricReading(measurement);

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
            {formatValue(measurement.key, measurement.value, measurement.unit)}
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

        {/* Not for loudness (`comparableAcrossCalls`). */}
        {comparableAcrossCalls(measurement.key) && (
          <p className="metric-page-across">
            <Link to={progressMetricPath(measurement.key)}>
              Diese Kennzahl über alle Trainings ansehen
            </Link>
          </p>
        )}
      </div>

      {metricKey === "intonation" && (
        <div className="card">
          <IntonationReading
            measurement={measurement}
            toneFit={detail.feedback?.tone_fit ?? null}
          />
        </div>
      )}

      {/* Every tile leads here, so the page must say more than the tile. */}
      <MetricEvidence measurement={measurement} turns={detail.turns} />

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

/** The user's line, the Persona's line it cut into, and what the Persona was
 * about to say, which was never heard (ADR 0035) and is styled as such. */
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
        // Matched on the finding's own offsets.
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

