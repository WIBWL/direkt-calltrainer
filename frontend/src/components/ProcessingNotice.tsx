/**
 * Where the data goes (F-49).
 *
 * The feature asks for a notice covering the *kind*, the *purpose* and the
 * *place* of processing. The first two are said wherever this is used; the
 * place is here, because it is the part a user cannot guess and the part this
 * app was silent about: speech leaves the machine.
 *
 * One component rather than a paragraph repeated in the consent dialog and on
 * the profile. Those two must not drift, and a claim about where personal data
 * travels is the worst possible thing to keep two copies of.
 *
 * A full privacy statement and an imprint are planned as their own pages. When
 * they land, this stays as the short version shown in context, and links to
 * them; it should not become the long one.
 */
export default function ProcessingNotice({ compact = false }: { compact?: boolean }) {
  return (
    <div className={compact ? "processing-notice is-compact" : "processing-notice"}>
      <p className="processing-notice-lead">
        Ihre Stimme verlässt beim Training Ihren Rechner. Das ist technisch nötig, damit das
        Gespräch funktioniert.
      </p>

      <ul className="processing-notice-list">
        <li>
          <strong>Was Sie sagen</strong> geht zur Spracherkennung an den DiReKT-Sprachdienst der
          Universität Würzburg und wird dort in Text umgewandelt. Derselbe Dienst erzeugt daraus
          die Antwort Ihres Gesprächspartners.
        </li>
        <li>
          <strong>Die Stimme des Gesprächspartners</strong> wird bei der KugelAudio UG in
          Hannover erzeugt. Dorthin geht ausschließlich der Text, den die Persona sagt. Ihre
          eigene Aufnahme und Ihr Transkript erreichen KugelAudio nicht. Die Verarbeitung
          findet auf Servern in Deutschland und Finnland statt.
        </li>
        <li>
          <strong>Gespeichert</strong> wird, sofern Sie zustimmen, auf einem Server der
          Hetzner Online GmbH in Gunzenhausen. Ihre Daten verlassen Deutschland dabei nicht.
        </li>
      </ul>
    </div>
  );
}
