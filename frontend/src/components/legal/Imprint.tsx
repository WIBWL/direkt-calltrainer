import LegalPage from "../LegalPage";

/**
 * The imprint of the EFRE DiReKT project, reproduced from
 * https://efre-direkt.de/imprint/ without changes.
 *
 * Adopted rather than written: the Calltrainer is part of that project and
 * runs under the same responsible body, so a second imprint saying something
 * slightly different would be worse than one saying the same thing.
 */
export default function Imprint() {
  return (
    <LegalPage title="Impressum">
      <div className="legal-body">
        <p>
          Universität Würzburg
          <br />
          Lehrstuhl für BWL und Wirtschaftsinformatik
        </p>

        <p>
          Prof. Dr. Axel Winkelmann
          <br />
          Sanderring 2
          <br />
          97070 Würzburg
          <br />
          Tel.: +49 (0)931 31-89640
          <br />
          E-Mail:{" "}
          <a href="mailto:axel.winkelmann@uni-wuerzburg.de">
            axel.winkelmann@uni-wuerzburg.de
          </a>
        </p>

        <h2>Pressekontakt</h2>
        <p>
          Sanderring 2
          <br />
          97070 Würzburg
          <br />
          Tel.: +49 (0)931 31-80501
          <br />
          Fax.: +49 (0)931 31-80680
          <br />
          E-Mail:{" "}
          <a href="mailto:wiwi-direkt@uni-wuerzburg.de">wiwi-direkt@uni-wuerzburg.de</a>
        </p>

        <h2>Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV</h2>
        <p>
          Prof. Dr. Axel Winkelmann
          <br />
          Universität Würzburg
          <br />
          Lehrstuhl für BWL und Wirtschaftsinformatik
          <br />
          Sanderring 2
          <br />
          97070 Würzburg
        </p>

        <h2>Rechtsform und Vertretung</h2>
        <p>
          Die Julius-Maximilians-Universität Würzburg ist eine Körperschaft des Öffentlichen
          Rechts und zugleich staatliche Einrichtung nach Art. 4 Abs. 1 BayHIG. Sie wird
          gesetzlich vertreten durch den Präsidenten Prof. Dr. Paul Pauli.
        </p>

        <h2>Zuständige Aufsichtsbehörde</h2>
        <p>
          Bayerisches Staatsministerium für Wissenschaft und Kunst
          <br />
          Postanschrift: Salvatorstraße 2, 80327 München
        </p>

        <h2>Umsatzsteuer-Identifikationsnummer</h2>
        <p>
          Die Umsatzsteuer-Identifikationsnummer gemäß § 27a Umsatzsteuergesetz lautet
          DE 134187690.
        </p>

        <p>
          Die Julius-Maximilians-Universität Würzburg übernimmt keine Haftung für die
          Richtigkeit, Vollständigkeit und Verfügbarkeit der bereit gestellten Inhalte,
          insbesondere wird eine Haftung für Schäden der Nutzer des Internetangebotes
          ausgeschlossen. Dies gilt insbesondere auch für IT-Schäden, die durch den Download von
          Inhalten entstehen.
        </p>

        <p>
          Die Julius-Maximilians-Universität Würzburg übernimmt darüber hinaus keine Haftung für
          die Inhalte externer Links und Kommentare von Dritten, insbesondere auf den
          Social-Media-Kanälen der Julius-Maximilians-Universität Würzburg. Für den Inhalt der
          verlinkten Seiten sind ausschließlich deren Betreiberinnen und Betreiber
          verantwortlich.
        </p>

        <p>
          Dieses Impressum gilt auch für alle zentralen Social-Media-Accounts der Universität
          Würzburg:
        </p>
        <ul className="legal-links">
          <li>https://www.facebook.com/uniwue</li>
          <li>https://www.twitter.com/uni_wue</li>
          <li>https://www.instagram.com/uniwuerzburg</li>
          <li>https://www.youtube.com/uniwuerzburg</li>
          <li>https://www.linkedin.com/school/julius-maximilians-universitat-wurzburg/</li>
          <li>https://www.tiktok.com/@uniwuerzburg</li>
          <li>https://www.pinterest.de/uniwue/</li>
        </ul>

        <p>
          Ferner gilt dieses Impressum auch für alle dienstlichen Social-Media-Accounts der
          Universität, darunter Accounts von Einrichtungen, Fakultäten, Fachbereichen,
          Forschungsprojekten, Lehrstühlen und Lehrbereichen auf folgenden Plattformen:
        </p>
        <ul className="legal-links">
          <li>https://www.facebook.com/</li>
          <li>https://www.twitter.com/</li>
          <li>https://www.instagram.com/</li>
          <li>https://www.youtube.com/</li>
          <li>https://de.linkedin.com/</li>
          <li>https://tiktok.com/</li>
          <li>https://uninow.de/</li>
          <li>https://www.pinterest.de/</li>
        </ul>
      </div>
    </LegalPage>
  );
}
