import LegalPage from "../LegalPage";

/**
 * The accessibility statement of the EFRE DiReKT project, reproduced from
 * https://efre-direkt.de/accessibility/.
 *
 * One deliberate change, in "Geltungsbereich": the original names
 * efre-direkt.de and then excludes the university's other web offerings. Copied
 * unaltered it would have said, on this page, that it does not apply to this
 * page. The scope sentence therefore names the Calltrainer as well. Everything
 * else is the original wording.
 *
 * Note for whoever maintains this: the listed barriers (event registration,
 * newsletter) belong to the project website and not to the Calltrainer, and
 * this application has never been through the BITV self-assessment the
 * statement describes. Both are for the next review of this text, not for a
 * silent edit here.
 */
export default function Accessibility() {
  return (
    <LegalPage title="Erklärung zur Barrierefreiheit">
      <div className="legal-body">
        <h2>Geltungsbereich</h2>
        <p>
          Die Julius-Maximilians-Universität Würzburg ist bemüht, ihre Websites und mobilen
          Anwendungen im Einklang mit Art. 13 des Bayerischen
          Behindertengleichstellungsgesetzes (BayBGG) in Verbindung mit der Bayerischen
          Digitalverordnung (BayDiV) barrierefrei zugänglich zu machen.
        </p>
        <p>
          Diese Erklärung zur Barrierefreiheit gilt für die Website https://efre-direkt.de des
          Projekts EFRE DiReKT der Julius-Maximilians-Universität Würzburg sowie für den
          Calltrainer dieses Projekts. Sie gilt nicht für die übrigen Webangebote der
          Universität; für diese gelten die dort veröffentlichten Erklärungen.
        </p>

        <h2>Stand der Vereinbarkeit mit den Anforderungen</h2>
        <p>
          Diese Website ist mit den Anforderungen des § 9 BayDiV in Verbindung mit der
          harmonisierten europäischen Norm EN 301 549 (diese entspricht im Wesentlichen den Web
          Content Accessibility Guidelines 2.1, Konformitätsstufe AA) teilweise vereinbar. Die
          nachstehend aufgeführten Inhalte sind aus den jeweils genannten Gründen nicht oder
          nicht vollständig barrierefrei.
        </p>

        <h2>Nicht barrierefreie Inhalte</h2>
        <ul>
          <li>
            <strong>Redaktionell gepflegte Inhalte.</strong> Die Inhalte dieser Website werden
            über ein Redaktionssystem gepflegt. Trotz redaktioneller Prüfung kann nicht
            ausgeschlossen werden, dass einzelne Bilder ohne aussagekräftigen Alternativtext,
            Überschriften außerhalb der logischen Gliederung oder Links ohne selbsterklärende
            Beschriftung veröffentlicht werden.
          </li>
          <li>
            <strong>Fremdsprachige Fachbegriffe.</strong> Einzelne englischsprachige
            Fachbegriffe im ansonsten deutschsprachigen Text sind nicht durchgängig als
            fremdsprachig ausgezeichnet. Sprachausgaben können solche Stellen falsch
            aussprechen.
          </li>
          <li>
            <strong>Anmeldung zu Veranstaltungen.</strong> Für die Anmeldung zu Veranstaltungen
            binden wir auf den Veranstaltungsseiten das Anmeldesystem pretix unter
            tickets.efre-direkt.de ein. Das Anmeldeformular benötigt JavaScript und stammt aus
            einer Fremdsoftware, auf deren Barrierefreiheit wir nur eingeschränkt Einfluss
            haben. Sie können sich zu jeder Veranstaltung stattdessen formlos per E-Mail an{" "}
            <a href="mailto:wiwi-direkt@uni-wuerzburg.de">wiwi-direkt@uni-wuerzburg.de</a>{" "}
            anmelden. Wir nehmen Ihre Anmeldung dann manuell entgegen; Ihnen entstehen dadurch
            keine Nachteile.
          </li>
          <li>
            <strong>Anmeldung zum Newsletter.</strong> Der Newsletter wird über den Listendienst
            Sympa des Deutschen Forschungsnetzes (DFN) versendet. Für die An- und Abmeldung
            verlassen Sie diese Website und nutzen die Oberfläche des DFN, auf deren
            Barrierefreiheit wir keinen Einfluss haben. Sie können sich auch hier formlos per
            E-Mail an{" "}
            <a href="mailto:wiwi-direkt@uni-wuerzburg.de">wiwi-direkt@uni-wuerzburg.de</a> an-
            und abmelden.
          </li>
          <li>
            <strong>Deutsche Gebärdensprache.</strong> Informationen zu dieser Website in
            Deutscher Gebärdensprache stehen derzeit nicht zur Verfügung.
          </li>
        </ul>

        <h2>Leichte Sprache</h2>
        <p>
          Die wichtigsten Informationen zu diesem Angebot finden Sie in Leichter Sprache. Dort
          erklären wir, worum es im Projekt EFRE DiReKT geht, was Sie auf dieser Website finden
          und wie Sie uns erreichen.
        </p>

        <h2>Erstellung dieser Erklärung</h2>
        <p>Diese Erklärung wurde am 07.08.2026 erstellt.</p>
        <p>
          Grundlage ist eine dokumentierte Selbstbewertung der Website. Geprüft wurde im
          Zeitraum Juli und August 2026 anhand der Prüfschritte des BITV-Selbsttests, die die
          Anforderungen der EN 301 549 abbilden. Die Erklärung wurde zuletzt am 07.08.2026
          überprüft.
        </p>

        <h2>Barrieren melden: Kontakt zu uns</h2>
        <p>
          Sie möchten uns bestehende Barrieren mitteilen, Inhalte in einer zugänglichen Form
          anfordern oder Auskunft über die Umsetzung der Barrierefreiheit erhalten? Wenden Sie
          sich bitte an:
        </p>
        <p>
          Julius-Maximilians-Universität Würzburg
          <br />
          Lehrstuhl für BWL und Wirtschaftsinformatik
          <br />
          Projekt EFRE DiReKT
          <br />
          Sanderring 2
          <br />
          97070 Würzburg
          <br />
          E-Mail:{" "}
          <a href="mailto:wiwi-direkt@uni-wuerzburg.de">wiwi-direkt@uni-wuerzburg.de</a>
        </p>
        <p>
          Alternativ können Sie unser Kontaktformular verwenden. Bitte beschreiben Sie möglichst
          genau, um welche Seite und um welche Barriere es geht. Wir antworten Ihnen innerhalb
          eines Monats.
        </p>

        <h2>Durchsetzungsverfahren</h2>
        <p>
          Wenn Sie auf Ihre Mitteilung keine oder aus Ihrer Sicht keine zufriedenstellende
          Antwort erhalten, können Sie sich an die Durchsetzungs- und Überwachungsstelle für
          barrierefreie Informationstechnik wenden. Dort können Sie nach § 11 BayDiV einen
          Antrag auf Überprüfung der Einhaltung der Anforderungen an die Barrierefreiheit
          stellen. Der Antrag ist möglich, wenn Sie innerhalb von sechs Wochen keine oder keine
          zufriedenstellende Antwort von uns erhalten haben.
        </p>
        <p>
          Landesamt für Digitalisierung, Breitband und Vermessung
          <br />
          IT-Dienstleistungszentrum des Freistaats Bayern
          <br />
          Durchsetzungs- und Überwachungsstelle für barrierefreie Informationstechnik
          <br />
          St.-Martin-Straße 47
          <br />
          81541 München
          <br />
          E-Mail: <a href="mailto:bitv@bayern.de">bitv@bayern.de</a>
          <br />
          Internet: www.ldbv.bayern.de/digitalisierung/bitv.html
        </p>
      </div>
    </LegalPage>
  );
}
