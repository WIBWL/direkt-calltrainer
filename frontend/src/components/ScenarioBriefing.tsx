/**
 * The trainee's own side of the case (ADR 0054) — the only text addressed to whoever picks up, not to the
 * model. Rendered on the setup screen and again just before the ringing phone. Renders nothing for a Scenario
 * without one.
 */
export default function ScenarioBriefing({ briefing }: { briefing: string | undefined }) {
  if (!briefing) return null;

  return (
    <section className="scenario-briefing">
      <h3 className="scenario-briefing-title">Ihre Ausgangslage</h3>
      <p className="scenario-briefing-body">{briefing}</p>
    </section>
  );
}
