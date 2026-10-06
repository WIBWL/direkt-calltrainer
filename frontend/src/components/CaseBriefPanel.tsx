import ScenarioBriefing, { StructuredText } from "./ScenarioBriefing";

/** The Wissensstand (ADR 0054) and, for an authored Scenario, the case facts; `call_goal` stays withheld. Not for a random Scenario (F-62). */
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
