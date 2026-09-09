import { Link, useParams } from "react-router-dom";

import { useStoredSession } from "../hooks/useStoredSession";
import type { Finding, SessionTurn, TrafficLight } from "../protocol";
import { ROUTES, sessionPath } from "../routes";
import { formatOffset } from "../utils/time";
import AppLayout from "./AppLayout";
import { LIGHT_LABEL } from "./FeedbackView";
import IntonationReading from "./IntonationReading";

/**
 * One Kennzahl of one training, in full (F-51's interruptions today).
 *
 * Its own page rather than a panel inside the wrap-up. The excerpts run to
 * several lines each, a call with four interruptions would push everything
 * below it off the screen, and this is something a user may want to link to or
 * come back to. Back is the browser's.
 *
 * Reads the Session once and never polls, like `PastSessionView`: whatever the
 * database holds for a finished call is final.
 */
/** Counts read without decimals, everything else with one. The unit follows,
 *  except for "Anzahl", which the figure already is. */
function formatFigure(value: number, unit: string | null): string {
  const text = unit === "Anzahl" ? value.toFixed(0) : value.toFixed(1);
  return unit && unit !== "Anzahl" ? `${text} ${unit}` : text;
}

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
      <AppLayout pageClassName="app-page-narrow">
        {back}
        <p className="muted">Wird geladen …</p>
      </AppLayout>
    );
  }

  const measurement = detail?.measurements.find((m) => m.key === metricKey);
  if (!detail || !measurement) {
    return (
      <AppLayout pageClassName="app-page-narrow">
        {back}
        <h1>Kennzahl</h1>
        <div className="card">
          <p>Zu diesem Training gibt es diese Kennzahl nicht.</p>
        </div>
      </AppLayout>
    );
  }

  const findings = detail.findings.filter((f) => f.metric_key === metricKey);
  const steps = detail.metric_scales[metricKey ?? ""] ?? [];
  const note = detail.metric_notes[metricKey ?? ""];
  const light = measurement.detail?.light as TrafficLight | undefined;

  return (
    <AppLayout pageClassName="app-page-narrow">
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
          {light && (
            <span className="metric-light-label">
              {LIGHT_LABEL[light]} <span className="metric-light-caveat">(Einschätzung)</span>
            </span>
          )}
        </p>

        {steps.length > 0 && (
          <dl className="metric-steps">
            {steps.map((step) => (
              <div className={`metric-step metric-step-${step.light}`} key={step.light}>
                <dt>{LIGHT_LABEL[step.light]}</dt>
                <dd>{step.range}</dd>
              </div>
            ))}
          </dl>
        )}

        {note && <p className="metric-note">{note}</p>}
      </div>

      {metricKey === "intonation" && <IntonationReading measurement={measurement} />}

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

