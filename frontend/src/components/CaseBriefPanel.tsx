import ScenarioBriefing, { StructuredText } from "./ScenarioBriefing";

/**
 * What the trainee holds for an ordinary call: their Wissensstand (the
 * `briefing`, ADR 0054) and, for an authored Scenario, the facts of the case.
 *
 * A built-in serves no facts to the client (ADR 0054's amendment): its
 * Wissensstand already lists what the trainee's own company knows about this
 * customer, and the facts are the caller's side, notes and budget included. An
 * authored Scenario still shows them, because its author wrote them to be read
 * and its briefing is usually a few sentences of role. What stays withheld
 * everywhere is `call_goal`, which is the answer key.
 *
 * Two variants, like `ReverseBriefPanel`: "prepare" is the screen between the
 * microphone check and the ringing phone; "call" sits beside the state
 * animation. They carry the same text, because what one reaches back for
 * mid-call — a number, a date, a name — is exactly what the Wissensstand is
 * written as a list for.
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

  if (variant === "call" && !facts && !briefing?.trim()) return null;

  return (
    <div className={variant === "call" ? "case-brief-call" : undefined}>
      {/* The same component in both places, so the Wissensstand reads
          identically before and during the call. */}
      <ScenarioBriefing briefing={briefing} />

      {facts && (
        <section className="case-brief" aria-label="Fakten des Falls">
          <div className="case-brief-eyebrow">FAKTEN DES FALLS</div>
          <div className="case-brief-body">
            <StructuredText text={facts} />
          </div>
        </section>
      )}
    </div>
  );
}
