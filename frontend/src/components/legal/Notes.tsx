import { Link } from "react-router-dom";

import { ROUTES } from "../../routes";
import LegalPage from "../LegalPage";

/**
 * What the Calltrainer is and what it is not.
 *
 * The footer has linked this since before there was a page behind it. What
 * belongs here is the thing the interface cannot say often enough without
 * getting in the way: the person on the other end does not exist, the machine
 * makes things up, and the feedback is a training aid rather than an
 * assessment of anyone.
 *
 * Written plainly and kept short. A disclaimer nobody reads protects nobody,
 * and the temptation with this kind of page is to make it long enough to feel
 * thorough.
 */
export default function Notes() {
  return (
    <LegalPage title="Wichtige Hinweise">
      <div className="legal-body">
        <p className="legal-lead">
          Der Calltrainer ist ein Übungswerkzeug. Sie sprechen darin mit einem
          Computerprogramm, nicht mit einem Menschen.
        </p>

        <h2>Ihr Gegenüber ist eine KI</h2>
        <p>
          Die Person, mit der Sie sprechen, gibt es nicht. Name, Rolle, Tonfall und
          Lebenslauf sind erfunden und dienen allein der Übung. Auch die Stimme ist erzeugt.
        </p>
        <p>
          Die KI kann überzeugend klingen und trotzdem Unsinn sagen. Sie erfindet gelegentlich
          Zahlen, Verträge oder Vorgeschichten, die es nie gab, und merkt das selbst nicht.
          Nehmen Sie nichts aus dem Gespräch als Auskunft über die Wirklichkeit.
        </p>

        <h2>Das Feedback ist maschinell erzeugt</h2>
        <p>
          Die Rückmeldung nach dem Gespräch stammt ebenfalls von einer KI. Sie ist ein
          Denkanstoß, keine Bewertung Ihrer Person und keine Beurteilung Ihrer beruflichen
          Eignung. Sie fließt nirgendwo ein und wird niemandem vorgelegt.
        </p>
        <p>
          Die Kennzahlen daneben sind reine Messwerte ohne Zielbereich. Es gibt für diese
          Nutzergruppe keinen belegten Normwert, an dem sich ablesen ließe, ob ein Sprechtempo
          oder ein Redeanteil gut oder schlecht ist. Wenn Ihnen ein Wert seltsam vorkommt,
          heißt das erst einmal nur, dass er gemessen wurde.
        </p>

        <h2>Es ersetzt keine Beratung</h2>
        <p>
          Was im Training gesagt wird, ist keine rechtliche, medizinische, finanzielle oder
          fachliche Beratung. Für echte Fragen wenden Sie sich an Menschen, die dafür zuständig
          sind.
        </p>

        <h2>Nennen Sie keine echten Daten Dritter</h2>
        <p>
          Bitte sprechen Sie im Training keine echten Kundennamen, Vertragsnummern,
          Gesundheitsangaben oder andere Daten aus, die andere Personen betreffen. Ein
          abgeschlossenes Gespräch wird, wenn Sie zugestimmt haben, als Text gespeichert, und
          was Sie sagen, steht dann darin.
        </p>
        <p>
          Was mit Ihren eigenen Daten passiert, steht in der{" "}
          <Link to={ROUTES.privacy}>Datenschutzerklärung</Link>. Löschen können Sie Ihre
          Trainings jederzeit im Profil.
        </p>

        <h2>Technische Grenzen</h2>
        <p>
          Die Spracherkennung versteht nicht immer richtig, besonders bei Nebengeräuschen,
          starkem Dialekt oder wenn mehrere Personen im Raum sind. Das Programm erkennt am
          Klang, wann Sie zu Ende gesprochen haben, und liegt dabei manchmal daneben. Ein
          Gespräch kann außerdem abbrechen, wenn ein beteiligter Dienst gerade nicht erreichbar
          ist. Sie verlieren dadurch nichts außer diesem einen Durchgang.
        </p>
      </div>
    </LegalPage>
  );
}
