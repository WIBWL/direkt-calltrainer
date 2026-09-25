import ScenarioBriefing from "./ScenarioBriefing";

/**
 * The trainee's briefing (ADR 0054) and the case facts, which the info panel already
 * serves; `call_goal`, the answer key, stays withheld. "prepare" shows both; "call" shows
 * the facts alone mid-call (ADR 0070's exception to ADR 0033). Not for a random Scenario (F-62).
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

    return (
      <section
        className="case-brief case-brief-call"
        aria-labelledby="case-brief-call-title"
      >
        <h3 id="case-brief-call-title" className="case-brief-title">
          Fakten des Falls
        </h3>
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
        <section className="case-brief" aria-labelledby="case-brief-title">
          <h3 id="case-brief-title" className="case-brief-title">
            Fakten des Falls
          </h3>
          <p className="case-brief-body">{facts}</p>
        </section>
      )}
    </>
  );
}
