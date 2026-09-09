import { useState } from "react";

import type { ReverseBrief } from "../scenarioLibrary";

/**
 * What the User holds while playing a reverse (F-61, ADR 0070): the briefing
 * the Persona had for the original call, plus the goals to get through it with.
 *
 * This is the one deliberate exception to ADR 0033's "no text during the live
 * call, only a state animation". That rule exists so the trainee listens
 * instead of reading a transcript of what was just said; this text says nothing
 * about the conversation in progress. It is fixed before the call starts, it is
 * the User's own briefing, and without it the exercise is not possible at all —
 * you cannot argue a case you have not been told.
 *
 * During the call it sits *beside* the state animation rather than under it, so
 * that checking a goal off never scrolls the call off the screen. On a narrow
 * screen the two stack, which is the one case where scrolling is unavoidable.
 *
 * The goals are the call's agenda — the concrete things to raise, ask and come
 * away with — and they tick off. Purely local, stored nowhere: it is a place to
 * keep your finger while talking, not a record of anything, and a "progress"
 * that outlived the call would be a score by the back door (ADR 0004). Which is
 * also why the counter says how many are done and never how well.
 */
export default function ReverseBriefPanel({
  brief,
  variant,
}: {
  brief: ReverseBrief;
  /** "prepare" on the mic-check screen, where there is room to read it before
   * the call; "call" beside the state animation, where it is a reference. */
  variant: "prepare" | "call";
}) {
  const [ticked, setTicked] = useState<Set<number>>(new Set());

  const toggle = (index: number) =>
    setTicked((current) => {
      const next = new Set(current);
      if (!next.delete(index)) next.add(index);
      return next;
    });

  const goals = brief.goals ?? brief.watch_points ?? [];
  const done = goals.filter((_, index) => ticked.has(index)).length;

  return (
    <section
      className={`reverse-brief reverse-brief-${variant}`}
      aria-labelledby="reverse-brief-title"
    >
      <div className="reverse-brief-eyebrow">IHRE UNTERLAGEN</div>
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
        <Field label="Erledigt ist es, wenn" text={brief.settled} />
      </dl>

      {goals.length > 0 && (
        <div className="reverse-brief-watch">
          <div className="reverse-brief-watch-head">
            <h3 className="reverse-brief-watch-title">Ihre Ziele im Gespräch</h3>
            <span className="reverse-brief-watch-count">
              {done} von {goals.length} erledigt
            </span>
          </div>

          {/* Width, not a colour or a grade: it says how much of the list has
              been worked through and nothing about how the call is going. */}
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
              // The index is the key because the list is fixed for the life of
              // the panel: it comes from the stored briefing and nothing
              // reorders, inserts or removes an entry.
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

/** One labelled paragraph, left out entirely when the model had nothing to put
 * in it — an empty heading reads as a missing fact rather than an absent one. */
function Field({ label, text }: { label: string; text: string }) {
  if (!text.trim()) return null;
  return (
    <div className="reverse-brief-field">
      <dt>{label}</dt>
      <dd>{text}</dd>
    </div>
  );
}
