import LegalPage from "../LegalPage";

/**
 * The privacy statement, based on https://efre-direkt.de/privacy/ and adapted
 * to what the Calltrainer actually processes.
 *
 * What was kept from the original, because it is about the responsible body
 * rather than about a website: the controller, the data protection officer,
 * the legal bases, the data subject rights, the supervisory authority and the
 * TLS paragraph.
 *
 * What was removed, because the Calltrainer does not do it: the Hetzner
 * hosting, the contact form and Web3Forms, the pretix event registration, the
 * DFN newsletter, the analytics paragraph and the tracking-cookie paragraph.
 * Leaving those in would have described processing that does not happen, which
 * is worse than saying nothing: it makes the whole document untrustworthy.
 *
 * What was added, because it does happen and the original could not know about
 * it: the login through Keycloak, the speech leaving the browser for the DiReKT
 * gateway and KugelAudio, the consent-gated storage, the six-month retention,
 * the account settings that are stored alongside the trainings without being
 * part of them (the focus goals of ADR 0076 and the retention switch), and the
 * rights that are exercisable in the app itself.
 *
 * The two gaps the first draft carried are filled: the hoster is Hetzner in
 * Gunzenhausen, and KugelAudio's seat, DPA and sub-processors come from the
 * Auftragsverarbeitungsvertrag dated 23.01.2026. Everything stated about
 * KugelAudio is attributed to the provider rather than asserted as our own
 * observation, because that is what it is.
 *
 * Still outstanding, and not something a code change can supply: review by the
 * data protection officer before this is relied upon.
 */
export default function Privacy() {
  return (
    <LegalPage title="Datenschutzerklärung">
      <div className="legal-body">
        <p className="legal-date">Stand: 6. September 2026</p>

        <h2>1. Datenschutz auf einen Blick</h2>

        <h3>Allgemeine Hinweise</h3>
        <p>
          Die folgenden Hinweise geben einen einfachen Überblick darüber, was mit Ihren
          personenbezogenen Daten passiert, wenn Sie den Calltrainer nutzen. Personenbezogene
          Daten sind alle Daten, mit denen Sie persönlich identifiziert werden können.
          Ausführliche Informationen entnehmen Sie der unter diesem Text aufgeführten
          Datenschutzerklärung.
        </p>

        <h3>Worum es beim Calltrainer geht</h3>
        <p>
          Der Calltrainer ist ein Übungswerkzeug für Telefongespräche. Sie führen ein Gespräch
          mit einem künstlichen Gesprächspartner und erhalten anschließend eine Rückmeldung
          dazu. Dabei wird gesprochene Sprache verarbeitet, also Daten, die Sie unmittelbar
          betreffen.
        </p>

        <h3>Was dabei am wichtigsten ist</h3>
        <ul>
          <li>
            Ihre Sprachaufnahme wird zur Auswertung an einen Sprachdienst übertragen und
            unmittelbar danach verworfen. Sie wird nicht gespeichert.
          </li>
          <li>
            Gespeichert wird ein Training nur, wenn Sie ausdrücklich eingewilligt haben, und
            auch dann nur der Text des Gesprächs, die daraus errechneten Kennzahlen und die
            Rückmeldung.
          </li>
          <li>
            Ohne Einwilligung können Sie den Calltrainer vollständig nutzen. Es wird dann nach
            dem Gespräch nichts abgelegt.
          </li>
          <li>
            Gespeicherte Trainings werden nach sechs Monaten automatisch gelöscht. Sie können
            das in Ihrem Profil aussetzen.
          </li>
          <li>
            Sie können jederzeit sehen, was gespeichert ist, es herunterladen und es löschen.
          </li>
        </ul>

        <h2>2. Betrieb und Hosting</h2>
        <p>
          Der Calltrainer wird im Rahmen des Projekts EFRE DiReKT der
          Julius-Maximilians-Universität Würzburg betrieben. Anwendung und Datenbank werden
          extern gehostet. Die auf dieser Plattform erfassten personenbezogenen Daten werden
          auf den Servern des Hosters in Deutschland gespeichert. Mit dem Hoster besteht ein
          Vertrag zur Auftragsverarbeitung nach Art. 28 DSGVO; er verarbeitet Ihre Daten nur
          insoweit, wie dies zur Erfüllung seiner Leistungspflichten erforderlich ist, und
          befolgt unsere Weisungen.
        </p>
        <p>
          Wir setzen folgenden Hoster ein:
        </p>
        <p>
          Hetzner Online GmbH
          <br />
          Industriestr. 25
          <br />
          91710 Gunzenhausen
          <br />
          Germany
        </p>
        <p>
          Die Verarbeitung erfolgt, soweit sie der Wahrnehmung unserer öffentlichen Aufgaben
          dient, auf Grundlage von Art. 6 Abs. 1 lit. e DSGVO i. V. m. Art. 4 BayDSG. Soweit
          eine Einwilligung abgefragt wurde, erfolgt die Verarbeitung auf Grundlage von
          Art. 6 Abs. 1 lit. a DSGVO. Die Einwilligung ist jederzeit widerrufbar.
        </p>

        <h2>3. Allgemeine Hinweise und Pflichtinformationen</h2>
        <p>
          Die Betreiber dieses Angebots nehmen den Schutz Ihrer persönlichen Daten sehr ernst.
          Wir behandeln Ihre personenbezogenen Daten vertraulich und entsprechend den
          gesetzlichen Datenschutzvorschriften sowie dieser Datenschutzerklärung. Wir weisen
          darauf hin, dass die Datenübertragung im Internet (z. B. bei der Kommunikation per
          E-Mail) Sicherheitslücken aufweisen kann. Ein lückenloser Schutz der Daten vor dem
          Zugriff durch Dritte ist nicht möglich.
        </p>

        <h3>Verantwortlicher</h3>
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
        <p>
          Die Universität wird durch den amtierenden Präsidenten oder die amtierende
          Präsidentin vertreten.
        </p>

        <h3>Kontaktdaten des bestellten behördlichen Datenschutzbeauftragten</h3>
        <p>
          Datenschutzbeauftragter der Julius-Maximilians-Universität Würzburg
          <br />
          Sanderring 2
          <br />
          Tel. 0931/31-0
          <br />
          <a href="mailto:datenschutz@uni-wuerzburg.de">datenschutz@uni-wuerzburg.de</a>
        </p>

        <h3>Speicherdauer</h3>
        <p>
          Soweit innerhalb dieser Datenschutzerklärung keine speziellere Speicherdauer genannt
          wurde, verbleiben Ihre personenbezogenen Daten bei uns, bis der Zweck für die
          Datenverarbeitung entfällt. Wenn Sie ein berechtigtes Löschersuchen geltend machen
          oder eine Einwilligung zur Datenverarbeitung widerrufen, werden Ihre Daten gelöscht,
          sofern wir keine anderen rechtlich zulässigen Gründe für die Speicherung Ihrer
          personenbezogenen Daten haben; im letztgenannten Fall erfolgt die Löschung nach
          Fortfall dieser Gründe. Für die Trainingsdaten gilt darüber hinaus die im Abschnitt
          „Speicherung und Löschung Ihrer Trainings“ genannte Frist.
        </p>

        <h3>Allgemeine Hinweise zu den Rechtsgrundlagen</h3>
        <p>
          Sofern Sie in die Datenverarbeitung eingewilligt haben, verarbeiten wir Ihre
          personenbezogenen Daten auf Grundlage von Art. 6 Abs. 1 lit. a DSGVO. Sofern Sie in
          die Speicherung von Informationen in Ihrem Endgerät eingewilligt haben, erfolgt die
          Datenverarbeitung zusätzlich auf Grundlage von § 25 Abs. 1 TDDDG. Die Einwilligung
          ist jederzeit widerrufbar. Des Weiteren verarbeiten wir Ihre Daten, sofern diese zur
          Erfüllung einer rechtlichen Verpflichtung erforderlich sind, auf Grundlage von
          Art. 6 Abs. 1 lit. c DSGVO. Im Übrigen erfolgt die Verarbeitung auf Grundlage von
          Art. 6 Abs. 1 lit. e DSGVO i. V. m. Art. 4 BayDSG im Rahmen der Wahrnehmung einer im
          öffentlichen Interesse liegenden Aufgabe. Über die jeweils einschlägige
          Rechtsgrundlage informieren die folgenden Abschnitte.
        </p>

        <h3>Widerruf Ihrer Einwilligung zur Datenverarbeitung</h3>
        <p>
          Die Speicherung Ihrer Trainings ist nur mit Ihrer ausdrücklichen Einwilligung
          möglich. Sie können eine bereits erteilte Einwilligung jederzeit in Ihrem Profil
          widerrufen. Die Rechtmäßigkeit der bis zum Widerruf erfolgten Datenverarbeitung
          bleibt vom Widerruf unberührt. Durch den Widerruf entstehen Ihnen keine Nachteile;
          der Calltrainer bleibt uneingeschränkt nutzbar.
        </p>

        <h3>Beschwerderecht bei der zuständigen Aufsichtsbehörde</h3>
        <p>
          Im Falle von Verstößen gegen die DSGVO steht den Betroffenen ein Beschwerderecht bei
          einer Aufsichtsbehörde zu. Die für uns als bayerische öffentliche Stelle zuständige
          Aufsichtsbehörde ist:
        </p>
        <p>
          Der Bayerische Landesbeauftragte für den Datenschutz (BayLfD)
          <br />
          Postfach 22 12 19, 80502 München
          <br />
          Hausanschrift: Wagmüllerstraße 18, 80538 München
          <br />
          Telefon: +49 89 212672-0
          <br />
          E-Mail:{" "}
          <a href="mailto:poststelle@datenschutz-bayern.de">poststelle@datenschutz-bayern.de</a>
        </p>
        <p>
          Das Beschwerderecht besteht unbeschadet anderweitiger verwaltungsrechtlicher oder
          gerichtlicher Rechtsbehelfe.
        </p>

        <h3>Recht auf Datenübertragbarkeit</h3>
        <p>
          Sie haben das Recht, Daten, die wir auf Grundlage Ihrer Einwilligung oder in
          Erfüllung eines Vertrags automatisiert verarbeiten, an sich oder an einen Dritten in
          einem gängigen, maschinenlesbaren Format aushändigen zu lassen. Im Calltrainer können
          Sie diese Daten in Ihrem Profil jederzeit selbst als JSON-Datei herunterladen.
        </p>

        <h3>Auskunft, Berichtigung und Löschung</h3>
        <p>
          Sie haben im Rahmen der geltenden gesetzlichen Bestimmungen jederzeit das Recht auf
          unentgeltliche Auskunft über Ihre gespeicherten personenbezogenen Daten, deren
          Herkunft und Empfänger und den Zweck der Datenverarbeitung und gegebenenfalls ein
          Recht auf Berichtigung oder Löschung dieser Daten. Auskunft und Löschung können Sie
          im Calltrainer unmittelbar in Ihrem Profil ausüben. Für die Berichtigung der Angaben
          zu Ihrer Person wenden Sie sich bitte an die für Ihr DiReKT-Konto zuständige Stelle:{" "}
          <a href="mailto:wiwi-direkt@uni-wuerzburg.de">wiwi-direkt@uni-wuerzburg.de</a>. Der
          Calltrainer führt keine eigene Nutzerverwaltung.
        </p>

        <h3>Recht auf Einschränkung der Verarbeitung</h3>
        <p>
          Sie haben das Recht, die Einschränkung der Verarbeitung Ihrer personenbezogenen Daten
          zu verlangen. Hierzu können Sie sich jederzeit an uns wenden. Das Recht besteht
          insbesondere, wenn Sie die Richtigkeit Ihrer bei uns gespeicherten Daten bestreiten
          und wir Zeit für die Prüfung benötigen, wenn die Verarbeitung unrechtmäßig geschah
          und Sie statt der Löschung die Einschränkung verlangen, wenn wir Ihre Daten nicht
          mehr benötigen, Sie sie jedoch zur Geltendmachung von Rechtsansprüchen brauchen, oder
          solange nach einem Widerspruch noch nicht feststeht, wessen Interessen überwiegen.
          Eingeschränkte Daten dürfen, von ihrer Speicherung abgesehen, nur mit Ihrer
          Einwilligung oder zur Geltendmachung, Ausübung oder Verteidigung von
          Rechtsansprüchen oder aus Gründen eines wichtigen öffentlichen Interesses verarbeitet
          werden.
        </p>

        <h3>Widerspruchsrecht (Art. 21 DSGVO)</h3>
        <p className="legal-uppercase">
          WENN DIE DATENVERARBEITUNG AUF GRUNDLAGE VON ART. 6 ABS. 1 LIT. E ODER F DSGVO
          ERFOLGT, HABEN SIE JEDERZEIT DAS RECHT, AUS GRÜNDEN, DIE SICH AUS IHRER BESONDEREN
          SITUATION ERGEBEN, GEGEN DIE VERARBEITUNG IHRER PERSONENBEZOGENEN DATEN WIDERSPRUCH
          EINZULEGEN; DIES GILT AUCH FÜR EIN AUF DIESE BESTIMMUNGEN GESTÜTZTES PROFILING. DIE
          JEWEILIGE RECHTSGRUNDLAGE, AUF DER EINE VERARBEITUNG BERUHT, ENTNEHMEN SIE DIESER
          DATENSCHUTZERKLÄRUNG. WENN SIE WIDERSPRUCH EINLEGEN, WERDEN WIR IHRE BETROFFENEN
          PERSONENBEZOGENEN DATEN NICHT MEHR VERARBEITEN, ES SEI DENN, WIR KÖNNEN ZWINGENDE
          SCHUTZWÜRDIGE GRÜNDE FÜR DIE VERARBEITUNG NACHWEISEN, DIE IHRE INTERESSEN, RECHTE UND
          FREIHEITEN ÜBERWIEGEN ODER DIE VERARBEITUNG DIENT DER GELTENDMACHUNG, AUSÜBUNG ODER
          VERTEIDIGUNG VON RECHTSANSPRÜCHEN (WIDERSPRUCH NACH ART. 21 ABS. 1 DSGVO).
        </p>

        <h3>SSL- bzw. TLS-Verschlüsselung</h3>
        <p>
          Diese Anwendung nutzt aus Sicherheitsgründen und zum Schutz der Übertragung
          vertraulicher Inhalte eine SSL- bzw. TLS-Verschlüsselung. Eine verschlüsselte
          Verbindung erkennen Sie daran, dass die Adresszeile des Browsers von „http://“ auf
          „https://“ wechselt und an dem Schloss-Symbol in Ihrer Browserzeile. Wenn die SSL-
          bzw. TLS-Verschlüsselung aktiviert ist, können die Daten, die Sie an uns übermitteln,
          nicht von Dritten mitgelesen werden.
        </p>

        <h2>4. Datenverarbeitung im Calltrainer</h2>

        <h3>Anmeldung</h3>
        <p>
          Die Nutzung des Calltrainers setzt eine Anmeldung mit Ihrem DiReKT-Konto voraus. Die
          Anmeldung selbst erfolgt über den Anmeldedienst des Projekts (Keycloak). Der
          Calltrainer erhält von dort Ihren Namen, Ihren Benutzernamen, Ihre E-Mail-Adresse und
          eine technische Kennung Ihres Kontos. Er führt keine eigene Nutzerverwaltung und
          speichert diese Angaben nicht in seiner Datenbank; sie werden ausschließlich für die
          Dauer Ihrer Sitzung im Browser vorgehalten und angezeigt.
        </p>
        <p>
          Rechtsgrundlage ist Art. 6 Abs. 1 lit. e DSGVO i. V. m. Art. 4 BayDSG: Ohne
          Anmeldung lässt sich nicht sicherstellen, dass jede Person nur ihre eigenen Trainings
          sieht.
        </p>

        <h3>Durchführung eines Trainingsgesprächs</h3>
        <p>
          Während eines Trainings nimmt Ihr Browser Ihre Sprache auf und überträgt sie
          abschnittsweise an unseren Server. Dabei werden drei externe beziehungsweise interne
          Dienste einbezogen:
        </p>
        <ul>
          <li>
            <strong>Spracherkennung und Antwortgenerierung.</strong> Ihre Aufnahme wird an den
            DiReKT-Sprachdienst der Universität Würzburg übertragen und dort in Text
            umgewandelt. Derselbe Dienst erzeugt aus dem bisherigen Gesprächsverlauf die
            Antwort Ihres Gesprächspartners.
          </li>
          <li>
            <strong>Sprachausgabe.</strong> Damit der Gesprächspartner hörbar antwortet, wird
            der von ihm zu sprechende Text an die KugelAudio UG (haftungsbeschränkt),
            Schäfertrift 6, 30657 Hannover, übertragen, die daraus eine Sprachausgabe erzeugt.
            Dorthin gelangt ausschließlich dieser erzeugte Text. Ihre eigene Aufnahme und Ihr
            Transkript werden nicht an diesen Dienst übertragen. Näheres im Abschnitt
            „Sprachausgabe durch KugelAudio“.
          </li>
          <li>
            <strong>Auswertung der Sprechweise.</strong> Aus der Aufnahme werden noch während
            des Gesprächs Kennzahlen berechnet, etwa Sprechtempo, Redeanteil und Lautstärke.
            Diese Berechnung findet auf unserem eigenen Server statt.
          </li>
        </ul>
        <p>
          <strong>Die Aufnahme selbst wird nicht gespeichert.</strong> Sie wird für die
          genannten Schritte im Arbeitsspeicher gehalten und danach verworfen. Was das Gespräch
          überdauern kann, ist der Text und die daraus errechneten Zahlen, und auch das nur
          unter den Voraussetzungen des nächsten Abschnitts.
        </p>
        <p>
          Rechtsgrundlage für die Durchführung des Gesprächs ist Art. 6 Abs. 1 lit. e DSGVO
          i. V. m. Art. 4 BayDSG.
        </p>

        <h3>Sprachausgabe durch KugelAudio</h3>
        <p>
          Für die Sprachausgabe setzen wir die KugelAudio UG (haftungsbeschränkt),
          Schäfertrift 6, 30657 Hannover, Deutschland, ein. Mit dem Anbieter besteht ein
          Vertrag zur Auftragsverarbeitung nach Art. 28 DSGVO.
        </p>
        <p>
          Übertragen wird ausschließlich der Text, den der künstliche Gesprächspartner sprechen
          soll. Ihre Sprachaufnahme und das daraus erzeugte Transkript werden nicht an
          KugelAudio übermittelt. Nach Angaben des Anbieters werden übermittelte Texte nur
          während der Verarbeitung im Arbeitsspeicher gehalten und nicht auf Datenträger
          geschrieben; das erzeugte Audio wird an uns gestreamt und dort nicht dauerhaft
          gespeichert. In den technischen Protokollen des Anbieters werden ausschließlich
          Metadaten festgehalten, keine Inhalte.
        </p>
        <p>
          Die Verarbeitung findet auf Servern in der Europäischen Union statt, konkret in
          Deutschland und Finnland. Der Anbieter setzt hierfür die Verda AI (Finnland) und die
          Hetzner Online GmbH (Deutschland) als Unterauftragsverarbeiter ein. Weitere vom
          Anbieter eingesetzte Dienstleister mit Sitz in den USA verarbeiten ausschließlich
          Geschäfts- und Fehlerprotokolldaten des Anbieters und erhalten keinen Zugriff auf
          Text- oder Audioinhalte. Eine Übermittlung der hier verarbeiteten Inhalte in
          Drittländer findet nicht statt.
        </p>
        <p>
          Rechtsgrundlage ist Art. 6 Abs. 1 lit. e DSGVO i. V. m. Art. 4 BayDSG: Ohne
          Sprachausgabe wäre ein Telefontraining nicht durchführbar.
        </p>

        <h3>Speicherung und Löschung Ihrer Trainings</h3>
        <p>
          Ein abgeschlossenes Training wird nur gespeichert, wenn Sie zuvor eingewilligt haben.
          Die Einwilligung wird beim ersten Aufruf abgefragt und lässt sich jederzeit im Profil
          ändern. Gespeichert werden dann:
        </p>
        <ul>
          <li>der Gesprächsverlauf als Text, mit Zeitpunkten der einzelnen Beiträge,</li>
          <li>die aus der Aufnahme errechneten Kennzahlen,</li>
          <li>die anschließend erzeugte Rückmeldung,</li>
          <li>
            das gewählte Szenario, der gewählte Gesprächspartner sowie Beginn und Ende des
            Gesprächs.
          </li>
        </ul>
        <p>
          Diese Daten werden unter der technischen Kennung Ihres Kontos abgelegt, nicht unter
          Ihrem Namen. Das ist eine Pseudonymisierung und keine Anonymisierung: Wer Zugriff auf
          den Anmeldedienst und die Datenbank zugleich hat, kann beides zusammenführen, und im
          gespeicherten Gesprächsverlauf steht ohnehin, was Sie gesagt haben.
        </p>
        <p>
          Ein Gespräch, das Sie abbrechen, wird nicht gespeichert. Ohne Einwilligung wird nichts
          gespeichert; Sie können den Calltrainer dann weiterhin vollständig nutzen und sehen
          Ihr Gesprächsprotokoll unmittelbar nach dem Gespräch, erhalten aber keine Auswertung
          und keine Trainingshistorie.
        </p>
        <p>
          <strong>Aufbewahrungsdauer:</strong> Gespeicherte Trainings werden sechs Monate nach
          dem Gespräch automatisch gelöscht. Sie können diese automatische Löschung in Ihrem
          Profil aussetzen, wenn Sie Ihre Trainings länger behalten möchten.
        </p>
        <p>
          Rechtsgrundlage ist Ihre Einwilligung nach Art. 6 Abs. 1 lit. a DSGVO.
        </p>

        <h3>Ihre Einstellungen</h3>
        <p>
          Unabhängig von den Trainings speichern wir zu Ihrem Konto Ihre Einstellungen in der
          Anwendung. Das sind Ihre Fokusziele, also die Trainingsziele, die Sie beim ersten
          Start oder später im Profil ausgewählt haben, und die Angabe, ob Sie die automatische
          Löschung nach sechs Monaten ausgesetzt haben. Gespeichert wird dabei die Auswahl
          selbst, verknüpft mit der technischen Kennung Ihres Kontos. Gesprächsinhalte enthalten
          diese Angaben nicht.
        </p>
        <p>
          Sie können Ihre Fokusziele jederzeit im Profil ändern. Ein Widerruf der Einwilligung
          löscht Ihre Trainings, setzt diese Einstellungen aber nicht zurück, weil sie nichts
          über einzelne Gespräche aussagen. Wenn Sie auch sie gelöscht haben möchten, genügt
          eine Nachricht an die oben genannte Adresse.
        </p>
        <p>
          Rechtsgrundlage ist Art. 6 Abs. 1 lit. e DSGVO i. V. m. Art. 4 BayDSG, wie bei der
          Anmeldung: Die Einstellungen dienen der Bereitstellung des Trainings selbst.
        </p>

        <h3>Nachweis Ihrer Einwilligung</h3>
        <p>
          Um nachweisen zu können, dass eine Speicherung gedeckt war, protokollieren wir Ihre
          Entscheidungen zur Einwilligung: den Zeitpunkt, die Fassung des Hinweistextes und ob
          Sie zugestimmt oder widerrufen haben. Dieses Protokoll enthält keine Gesprächsinhalte.
          Es bleibt bestehen, auch wenn Ihre Trainings gelöscht werden, weil es sonst seinen
          Zweck verlöre. Rechtsgrundlage ist Art. 6 Abs. 1 lit. c DSGVO i. V. m.
          Art. 7 Abs. 1 DSGVO.
        </p>

        <h3>Ihre Rechte in der Anwendung</h3>
        <p>In Ihrem Profil können Sie ohne Umweg über uns:</p>
        <ul>
          <li>sehen, wie viele Trainings, Gesprächsbeiträge und Kennzahlen gespeichert sind,</li>
          <li>alle gespeicherten Daten als JSON-Datei herunterladen,</li>
          <li>ein einzelnes Training löschen,</li>
          <li>Ihre Fokusziele ändern,</li>
          <li>
            die Einwilligung widerrufen, wodurch alle gespeicherten Trainings gelöscht werden,
          </li>
          <li>die automatische Löschung nach sechs Monaten aussetzen oder wieder einschalten.</li>
        </ul>

        <h3>Server-Log-Dateien</h3>
        <p>
          Beim Aufruf der Anwendung werden automatisch technische Informationen verarbeitet, die
          Ihr Browser übermittelt: Browsertyp und -version, verwendetes Betriebssystem,
          Hostname des zugreifenden Rechners, Uhrzeit der Anfrage und IP-Adresse. Eine
          Zusammenführung dieser Daten mit anderen Datenquellen findet nicht statt.
        </p>
        <p>
          Im Betriebsprotokoll der Anwendung werden zusätzlich technische Angaben zum Ablauf
          eines Trainings festgehalten, etwa die Dauer eines Beitrags und die Länge des
          erkannten Textes. <strong>Der Inhalt Ihrer Äußerungen wird dabei nicht
          protokolliert.</strong>
        </p>
        <p>
          Rechtsgrundlage ist Art. 6 Abs. 1 lit. e DSGVO i. V. m. Art. 4 BayDSG sowie dem
          Bayerischen Hochschulinnovationsgesetz (BayHIG). Die Verarbeitung ist zur technisch
          fehlerfreien Bereitstellung und zur Sicherheit unserer informationstechnischen
          Systeme erforderlich.
        </p>

        <h3>Speicherung im Browser</h3>
        <p>
          Der Calltrainer setzt keine Cookies zu Analyse-, Tracking- oder Werbezwecken. Für den
          Betrieb notwendig ist die Speicherung folgender Angaben in Ihrem Browser:
        </p>
        <ul>
          <li>
            Ihre Anmeldedaten aus dem Anmeldedienst, damit Sie sich nicht bei jedem Seitenaufruf
            neu anmelden müssen,
          </li>
          <li>
            der Verweis auf ein soeben beendetes Training, damit die Rückmeldung ein Neuladen
            der Seite übersteht.
          </li>
        </ul>
        <p>
          Diese Speicherung ist unbedingt erforderlich, um den von Ihnen aufgerufenen Dienst
          bereitstellen zu können, und erfolgt daher ohne Einwilligung auf Grundlage von
          § 25 Abs. 2 Nr. 2 TDDDG. Sie können sie über die Abmeldung und die Einstellungen
          Ihres Browsers jederzeit beenden.
        </p>

        <h3>Keine Analyse-Werkzeuge</h3>
        <p>
          Der Calltrainer bindet keine Analyse- oder Reichweitenmesswerkzeuge und keine Dienste
          Dritter zu Werbezwecken ein. Ihr Nutzungsverhalten wird nicht statistisch ausgewertet
          und es findet keine Profilbildung statt.
        </p>

        <h3>Grenzen</h3>
        <p>
          Der Vollständigkeit halber: Eine Löschung erreicht die Datenbank der Anwendung.
          Sicherungskopien, die beim Hoster anfallen, werden von einer Löschung in der Anwendung
          nicht erfasst; sie werden erst mit dem üblichen Umlauf der Sicherungen überschrieben. Die Löschung Ihrer Trainings im Calltrainer löscht außerdem nicht Ihr
          DiReKT-Konto, und die Löschung des DiReKT-Kontos löscht nicht Ihre Trainings. Beides
          ist getrennt und muss getrennt veranlasst werden.
        </p>

        <h2>Sonstiges zu unserer Datenschutzerklärung</h2>
        <p>
          Wir behalten uns vor, diese Datenschutzerklärung gelegentlich anzupassen, damit diese
          stets den aktuellen rechtlichen Anforderungen entspricht oder um Änderungen unserer
          Leistungen umzusetzen. Für Ihren erneuten Besuch gilt dann die neue
          Datenschutzerklärung.
        </p>
        <p>
          Wenn Sie Fragen haben oder Ihre Rechte gegenüber uns ausüben möchten, können Sie sich
          neben den Datenschutzbeauftragten auch an{" "}
          <a href="mailto:wiwi-direkt@uni-wuerzburg.de">wiwi-direkt@uni-wuerzburg.de</a> wenden.
        </p>
      </div>
    </LegalPage>
  );
}
