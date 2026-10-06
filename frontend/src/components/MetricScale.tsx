import { cx } from "../utils/cx";
import type { MetricStep } from "../protocol";

/** The whole scale, since the thresholds are unvalidated (ADR 0004/0051); colours come from the backend (ADR 0077). */
export default function MetricScale({
  steps,
  current,
}: {
  steps: MetricStep[];
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
