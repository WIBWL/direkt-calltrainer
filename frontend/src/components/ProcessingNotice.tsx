/** Where speech is processed (F-49); one copy for the consent dialog and the profile. */
export default function ProcessingNotice({ compact = false }: { compact?: boolean }) {
  return (
    <div className={compact ? "processing-notice is-compact" : "processing-notice"}>
      <p className="processing-notice-lead">
        Ihre Stimme verlässt beim Training Ihren Rechner. Das ist technisch nötig, damit das
        Gespräch funktioniert.
      </p>

      <ul className="processing-notice-list">
        <li>
          <strong>Was Sie sagen</strong> geht zur Spracherkennung an den Sprachdienst des Projekts
          DiReKT auf Servern der Hetzner Online GmbH in Nürnberg und wird dort in Text
          umgewandelt. Derselbe Dienst erzeugt daraus
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
          Hetzner Online GmbH in Nürnberg. Ihre Daten verlassen Deutschland dabei nicht.
        </li>
      </ul>
    </div>
  );
}
