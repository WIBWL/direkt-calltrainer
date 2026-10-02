import { cx } from "../utils/cx";
import type { MetricStep } from "../protocol";

/**
 * The scale a reading was taken off, this call's step marked; the whole scale is shown because the thresholds are
 * unvalidated (ADR 0004/0051). Marked by weight and a filled ground; colour is a second channel from the step's
 * own `light`, set by the backend (ADR 0077). This component maps nothing to a colour itself.
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
