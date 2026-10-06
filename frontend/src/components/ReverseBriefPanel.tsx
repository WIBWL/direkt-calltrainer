import { useState } from "react";

import type { ReverseBrief } from "../scenarioLibrary";

/** The briefing and goals while playing a reverse (F-61, ADR 0070). Goals tick
 * locally and are stored nowhere; the counter says how many, never how well (ADR 0004). */
export default function ReverseBriefPanel({
  brief,
  variant,
}: {
  brief: ReverseBrief;
  /** "prepare" on its own screen; "call" beside the animation. */
  variant: "prepare" | "call";
}) {
  const [ticked, setTicked] = useState<Set<number>>(new Set());

  const toggle = (index: number) =>
    setTicked((current) => {
      const next = new Set(current);
      if (!next.delete(index)) next.add(index);
      return next;
    });

  const { goals } = brief;
  const done = goals.filter((_, index) => ticked.has(index)).length;

  return (
    <section
      className={`reverse-brief reverse-brief-${variant}`}
      aria-labelledby="reverse-brief-title"
    >
      <h2 id="reverse-brief-title" className="reverse-brief-title">
        Sie rufen an
      </h2>
      <p className="reverse-brief-lead">
        Das hier hatte die KI im letzten Gespräch vor sich. Jetzt gehört es Ihnen.
      </p>

      <dl className="reverse-brief-fields">
        <Field label="Situation" text={brief.situation} />
        <Field label="Was Sie wissen" text={brief.facts} />
        <Field label="Was Sie erreichen wollen" text={brief.goal} />
      </dl>

      {goals.length > 0 && (
        <div className="reverse-brief-watch">
          <div className="reverse-brief-watch-head">
            <h3 className="reverse-brief-watch-title">Ihre Ziele im Gespräch</h3>
            <span className="reverse-brief-watch-count">
              {done} von {goals.length} erledigt
            </span>
          </div>

          {/* Progress through the list, nothing about the call. */}
          <div
            className="reverse-brief-progress"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={goals.length}
            aria-valuenow={done}
            aria-label="Erledigte Ziele"
          >
            <span style={{ width: `${(done / goals.length) * 100}%` }} />
          </div>

          <ul className="reverse-brief-watch-list">
            {goals.map((goal, index) => (
              // The list is fixed for the panel's life.
              <li key={index}>
                <label className={ticked.has(index) ? "is-ticked" : undefined}>
                  <input
                    type="checkbox"
                    checked={ticked.has(index)}
                    onChange={() => toggle(index)}
                  />
                  <span className="reverse-brief-watch-box" aria-hidden="true" />
                  <span className="reverse-brief-watch-text">{goal}</span>
                </label>
              </li>
            ))}
          </ul>

          <p className="reverse-brief-watch-note">
            Nur für Sie, während des Gesprächs — nichts davon wird gespeichert.
          </p>
        </div>
      )}
    </section>
  );
}

/** Left out when empty: an empty heading reads as a missing fact. */
function Field({ label, text }: { label: string; text: string }) {
  if (!text.trim()) return null;
  return (
    <div className="reverse-brief-field">
      <dt>{label}</dt>
      <dd>{text}</dd>
    </div>
  );
}
