import { cx } from "../utils/cx";

// The header uses the current screen to highlight the matching training step.
export type TrainingStep = "prepare" | "call" | "feedback";

interface AppHeaderProps {
  activeStep: TrainingStep;
}

// Keeping the step configuration here avoids duplicating the markup.
const trainingSteps: { id: TrainingStep; label: string }[] = [
  { id: "prepare", label: "Vorbereiten" },
  { id: "call", label: "Gespräch" },
  { id: "feedback", label: "Feedback" },
];

export default function AppHeader({ activeStep }: AppHeaderProps) {
  const activeStepIndex = trainingSteps.findIndex((step) => step.id === activeStep);

  return (
    <header className="app-header">
      <div className="app-header-inner">
        <div className="app-brand">
          <span className="app-brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>

          <span className="app-brand-name">Calltrainer</span>
        </div>

        <ol className="training-progress" aria-label="Trainingsfortschritt">
          {trainingSteps.map((step, index) => {
            const isActive = step.id === activeStep;
            const isComplete = index < activeStepIndex;

            return (
              <li
                key={step.id}
                className={cx(
                  "training-progress-step",
                  isActive && "is-active",
                  isComplete && "is-complete",
                )}
                aria-current={isActive ? "step" : undefined}
              >
                <span className="training-progress-number">{index + 1}</span>
                <span className="training-progress-label">{step.label}</span>

                {index < trainingSteps.length - 1 && (
                  <span className="training-progress-connector" aria-hidden="true" />
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </header>
  );
}