/**
 * The trainee's own side of the case (ADR 0054).
 *
 * Everything else a Session knows about the case addresses the caller: the four
 * prompt fields brief the model that plays it. This is the only text written to
 * whoever picks up the phone — the role they answer in, the room they have, and
 * what counts as a good outcome.
 *
 * A component rather than markup because it is rendered twice: on the setup
 * screen as soon as a Scenario is picked, and again between the microphone
 * check and the ringing phone, where it is the last thing read before the call.
 *
 * Renders nothing for a Scenario without one — a Scenario authored before the
 * field existed has none, and an empty panel with a heading is worse than no
 * panel.
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
