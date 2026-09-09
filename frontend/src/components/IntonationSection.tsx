import { Link } from "react-router-dom";

import type { Measurement, MetricStep } from "../protocol";
import { sessionMetricPath } from "../routes";
import IntonationReading from "./IntonationReading";
import MetricScale from "./MetricScale";

/**
 * F-35's Sprachmelodie, in full, inside the wrap-up (`FeedbackView`) and inside
 * a stored training (`PastSessionView`).
 *
 * The one Kennzahl that gets a block of its own rather than a tile. A tile can
 * carry a figure; what this measurement is actually about — whether the voice
 * moved, where it moved, and what the movement looked like across the call — is
 * a shape, and a shape has to be drawn. The other Kennzahlen keep their tiles
 * above precisely because a number is all they are.
 *
 * The order is the argument: the figure, then the scale it was read against,
 * then the contour it came off, then the four factors, then what the whole
 * thing rests on. A reader who stops after the first line has the reading; a
 * reader who goes on can check it against the drawing.
 *
 * The block is skipped entirely when there is no contour — a Session measured
 * before the curve was kept, or a call too short to have one. The tile above
 * still shows the figure, and the detail page still explains why there is
 * nothing more.
 */
export default function IntonationSection({
  measurement,
  steps = [],
  note,
  sessionId,
}: {
  measurement: Measurement;
  /** The five steps, from the backend beside their thresholds. */
  steps?: MetricStep[] | undefined;
  /** The long explanation behind the Kennzahl's "i". */
  note?: string | undefined;
  /** For the link to the Kennzahl's own page; null on a call that was never
   *  stored, where there is no page to open. */
  sessionId: string | null;
}) {
  const detail = measurement.detail ?? {};
  const curve = detail.curve_hz as (number | null)[] | undefined;
  if (!curve || !detail.median_hz) return null;

  const step = detail.liveliness as string | undefined;
  const reading = detail.liveliness_label as string | undefined;
  const voicedMs = detail.voiced_ms as number | undefined;

  return (
    <section className="feedback-intonation">
      <div className="feedback-metrics-eyebrow">SPRACHMELODIE</div>
      <h2 className="feedback-metrics-title">Wie Ihre Stimme geklungen hat</h2>

      <div className="card">
        <p className="intonation-figure">
          <span className="intonation-figure-value">
            {measurement.value.toFixed(1)} Halbtöne
          </span>
          {reading ? (
            <span className="metric-light-label">
              {reading} <span className="metric-light-caveat">(Einschätzung)</span>
            </span>
          ) : (
            // No step, on purpose: below the floor in `intonation.py` there is
            // not enough voiced speech to read one, and saying so is better
            // than a word the material cannot carry.
            <span className="metric-light-label">
              Für eine Einordnung haben Sie in diesem Training zu wenig gesprochen
              {voicedMs ? ` (${Math.round(voicedMs / 1000)} Sekunden Stimme)` : ""}.
            </span>
          )}
        </p>

        <MetricScale steps={steps} current={step} />

        <IntonationReading measurement={measurement} />

        {note && <p className="metric-note">{note}</p>}

        {sessionId && (
          <Link
            className="intonation-more"
            to={sessionMetricPath(sessionId, measurement.key)}
          >
            Diese Kennzahl auf einer eigenen Seite ansehen
          </Link>
        )}
      </div>
    </section>
  );
}
