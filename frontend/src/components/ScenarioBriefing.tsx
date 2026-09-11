/**
 * The trainee's own side of the case (ADR 0054).
 *
 * Everything else a Session knows about the case is addressed to the caller:
 * the four prompt fields brief the model that plays it, and the selection card
 * says one line about the situation. This is the only text written to whoever
 * picks up the phone — the role they answer in, the room they have, and what
 * counts as a good outcome.
 *
 * Rendered in two places, which is why it is a component rather than markup in
 * one of them: on the setup screen as soon as a Scenario is picked (it is part
 * of choosing one), and again on the screen between the microphone check and
 * the ringing phone, where it sits above the facts of the case and is the last
 * thing read before the call starts. It used to sit on the check itself, which
 * put the case on the same screen as a level meter.
 *
 * Renders nothing for a Scenario without one. Every built-in carries a
 * briefing, but a Scenario authored before the field existed does not, and an
 * empty panel with a heading is worse than no panel.
 */
export default function ScenarioBriefing({
  briefing,
  className,
}: {
  briefing: string | undefined;
  /** Lets the two call sites space it against what sits above them. */
  className?: string;
}) {
  if (!briefing) return null;

  return (
    <section className={className ? `scenario-briefing ${className}` : "scenario-briefing"}>
      <h3 className="scenario-briefing-title">Ihre Ausgangslage</h3>
      <p className="scenario-briefing-body">{briefing}</p>
    </section>
  );
}
