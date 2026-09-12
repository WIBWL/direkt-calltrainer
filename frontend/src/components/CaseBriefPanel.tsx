import ScenarioBriefing from "./ScenarioBriefing";

/**
 * What the trainee holds for an ordinary call: their own briefing (ADR 0054)
 * and the facts of the case.
 *
 * The facts are the caller's own material — they are what the model playing
 * the caller is briefed with. Showing them is not a leak: the read-only info
 * panel behind a card's "i" already serves them for every Scenario, on the
 * argument that the situation comes up in the call anyway. What stays withheld
 * is `call_goal`, which is the answer key.
 *
 * Two variants, like `ReverseBriefPanel`: "prepare" is the screen between the
 * microphone check and the ringing phone and carries both halves; "call" sits
 * beside the state animation and carries the *facts* alone, since what one
 * reaches back for mid-call is a number, a date or a name.
 *
 * The "call" variant is the same deliberate exception to ADR 0033 that ADR 0070
 * takes for a reverse: the text says nothing about the conversation in
 * progress, is fixed before the call, and is never the Persona's lines. Not
 * shown for a random Scenario — there not knowing is the exercise (F-62).
 */
export default function CaseBriefPanel({
  briefing,
  caseFacts,
  variant,
}: {
  briefing: string | undefined;
  caseFacts: string | undefined;
  variant: "prepare" | "call";
}) {
  const facts = caseFacts?.trim();

  if (variant === "call") {
    if (!facts) return null;
    // The eyebrow is the heading here, so the section takes its name from a
    // label rather than from a heading hidden for the eye only.
    return (
      <section className="case-brief case-brief-call" aria-label="Fakten des Falls">
        <div className="case-brief-eyebrow">FAKTEN DES FALLS</div>
        <p className="case-brief-body">{facts}</p>
      </section>
    );
  }

  return (
    <>
      {/* The same component the setup screen uses, so the briefing reads
          identically in both places rather than being written twice. */}
      <ScenarioBriefing briefing={briefing} />

      {facts && (
        <section className="case-brief case-brief-prepare">
          <div className="case-brief-eyebrow">FAKTEN DES FALLS</div>
          <p className="case-brief-body">{facts}</p>
        </section>
      )}
    </>
  );
}
