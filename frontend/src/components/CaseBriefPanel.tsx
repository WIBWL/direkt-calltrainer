import ScenarioBriefing, { StructuredText } from "./ScenarioBriefing";

/**
 * The trainee's Wissensstand (`briefing`, ADR 0054) and, for an authored Scenario, the case facts;
 * a built-in serves no facts (ADR 0054's amendment), and `call_goal`, the answer key, stays withheld
 * everywhere. "prepare" and "call" carry the same text, the latter below the live call (ADR 0070's
 * exception to ADR 0033). Not for a random Scenario (F-62).
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

  const titleId = variant === "call" ? "case-brief-call-title" : "case-brief-title";

  return (
    <div className={variant === "call" ? "case-brief-call" : undefined}>
      {/* The same component in both places, so the Wissensstand reads
          identically before and during the call. */}
      <ScenarioBriefing briefing={briefing} />

      {facts && (
        <section className="case-brief" aria-labelledby={titleId}>
          <h3 id={titleId} className="case-brief-title">
            Fakten des Falls
          </h3>
          <div className="case-brief-body">
            <StructuredText text={facts} />
          </div>
        </section>
      )}
    </div>
  );
}
