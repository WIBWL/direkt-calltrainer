import { cx } from "../utils/cx";
import type { MetricStep } from "../protocol";

/**
 * The scale a reading was taken off, with this call's step marked.
 *
 * Two Kennzahlen carry a reading — F-51's traffic light and F-35's three-step
 * Sprachmelodie — and both are judgements on thresholds nothing has validated
 * for this population (ADR 0004/0051). Showing the whole scale is what keeps
 * that arguable: a boundary the reader cannot see is a verdict they cannot
 * disagree with.
 *
 * Marked rather than merely listed, because the reader has to see not only
 * where the boundaries are but which side of them they came down on. The mark
 * is weight and a filled ground; the colour is a second channel on top of it,
 * so a reader who cannot tell the three tints apart still sees which step they
 * landed on. Both scales carry a colour now (ADR 0077 gave F-35 one), and it
 * always rides on the step's own `light`, set by the backend beside the
 * threshold it belongs to. This component maps nothing to any colour itself.
 */
export default function MetricScale({
  steps,
  current,
}: {
  steps: MetricStep[];
  /** The step this call landed on, or undefined when it has no reading. */
  current?: string | undefined;
}) {
  if (steps.length === 0) return null;

  return (
    <dl className="metric-steps">
      {steps.map((step) => (
        <div
          className={cx(
            "metric-step",
            step.light && `metric-step-${step.light}`,
            step.step === current && "is-current",
          )}
          key={step.step}
          aria-current={step.step === current ? "true" : undefined}
        >
          <dt>{step.label}</dt>
          <dd>{step.range}</dd>
        </div>
      ))}
    </dl>
  );
}
