import { useAuth } from "react-oidc-context";
import { Link } from "react-router-dom";

import { useAccount } from "../hooks/useAccount";
import { ROUTES } from "../routes";
import AppLayout from "./AppLayout";
import ConsentSettings from "./ConsentSettings";
import DataOverview from "./DataOverview";
import FocusSettings from "./FocusSettings";
import InfoDetails from "./InfoDetails";
import ProcessingNotice from "./ProcessingNotice";
import SessionHistory from "./SessionHistory";

/** Where a DiReKT account is deleted — the identity provider's owner, not this app. */
const DIREKT_CONTACT = "wiwi-direkt@uni-wuerzburg.de";

/**
 * The account screen (F-31), the privacy notice (F-49) and the deletion paths.
 *
 * A route-level screen, so it brings its own AppLayout the way App.tsx does for
 * the training screens, rather than having the router assemble the frame.
 *
 * Read-only by construction: every value is a claim the realm asserts, nothing
 * derived or filled in. Identity lives in Keycloak and there is no User table
 * (ADR 0031), so nothing here could accept an edit; the screen says so rather
 * than offering fields that would fail on save.
 *
 * Deliberately *not* shown: the Keycloak `sub` and the realm URL, which answer
 * no question a user has, and the access token's expiry, which describes a
 * five-minute token rather than their session (see `useAccount`).
 *
 * Leads with what the user came for and folds explanations into `InfoDetails`.
 * The full text is the privacy statement's job and is linked rather than
 * paraphrased — two copies of a claim are two things to keep in sync, and one
 * will lose.
 */
export default function ProfileView() {
  const account = useAccount();
  const auth = useAuth();

  return (
    <AppLayout accountActive pageClassName="profile-page">
      <h1>Profil</h1>

      <section className="profile-identity">
        <span className="profile-avatar" aria-hidden="true">
          {account.initials}
        </span>

        <div className="profile-identity-text">
          <p className="profile-name">{account.displayName}</p>
          {account.email && <p className="profile-email">{account.email}</p>}
        </div>

        <button
          type="button"
          className="profile-signout"
          onClick={() => void auth.signoutRedirect()}
        >
          Abmelden
        </button>
      </section>

      <section className="card">
        <h2>Kontodaten</h2>
        <dl className="profile-facts">
          <Fact label="Name" value={account.displayName} />
          <Fact label="Benutzername" value={account.username} />
          <Fact
            label="E-Mail"
            value={account.email}
            note={account.email && !account.emailVerified ? "nicht bestätigt" : null}
          />
        </dl>
        <InfoDetails label="Warum lässt sich das hier nicht ändern?">
          <p>
            Diese Angaben stammen aus Ihrem DiReKT-Konto und werden dort verwaltet, nicht im
            Calltrainer.
          </p>
        </InfoDetails>
      </section>

      <section className="card">
        <h2>Speicherung Ihrer Trainings</h2>
        <ConsentSettings />
      </section>

      {/* Above the history, below the storage decision: it is a setting about
          future trainings, which is what the card above it is too, and it says
          nothing about the trainings already listed further down. */}
      <section className="card">
        <h2>Ihre Fokusziele</h2>
        <FocusSettings />
      </section>

      <section className="card">
        <h2>Ihre Trainings</h2>
        <SessionHistory />
      </section>

      <section className="card">
        <h2>Ihre Daten</h2>
        <p className="card-lead">
          Gespeichert werden Gesprächsprotokoll, Kennzahlen und Auswertung, aber{" "}
          <strong>keine Tonaufnahme</strong>.
        </p>

        <DataOverview />

        <InfoDetails label="Was genau gespeichert wird und wo">
          <p>
            Gespeichert wird erst, wenn Sie das Gespräch zu Ende führen. Brechen Sie ab, bleibt
            nichts zurück. Die Tonaufnahme wird während des Gesprächs ausgewertet und danach
            gelöscht.
          </p>

          <ProcessingNotice />

          <p>
            Neben den Trainings selbst werden Ihre Einstellungen gespeichert, also Ihre
            Fokusziele und die Angabe, ob die automatische Löschung ausgesetzt ist. Sie
            enthalten keine Gesprächsinhalte und bleiben erhalten, wenn Trainings gelöscht
            werden.
          </p>

          <p>
            Ihre Trainings liegen unter einer technischen Kennung, nicht unter Ihrem Namen. Das
            schützt Sie allerdings nur begrenzt: Wer Zugriff auf Anmeldung und Datenbank hat,
            kann beides zusammenbringen, und im Gesprächsverlauf steht ohnehin, was Sie gesagt
            haben.
          </p>

          <p>
            Ausführlich in der <Link to={ROUTES.privacy}>Datenschutzerklärung</Link>.
          </p>
        </InfoDetails>
      </section>

      <section className="card">
        <h2>Daten löschen</h2>

        <dl className="deletion-paths">
          <dt>Ein einzelnes Training</dt>
          <dd>
            In der Liste oben auf das Papierkorb-Symbol in der Zeile, oder im geöffneten
            Training am Seitenende. Ein daraus erstellter Rollentausch bleibt dabei
            erhalten — Sie entfernen ihn in der Szenarienauswahl.
          </dd>

          <dt>Alle Ihre Trainings</dt>
          <dd>
            Oben die Einwilligung widerrufen. Damit gehen auch alle Rollentausch-Szenarien.
          </dd>

          <dt>Ihr ganzes DiReKT-Konto</dt>
          <dd>
            Mail an <a href={`mailto:${DIREKT_CONTACT}`}>{DIREKT_CONTACT}</a>.
          </dd>
        </dl>

        <InfoDetails label="Konto und Trainings hängen nicht zusammen">
          <p>
            Die Löschung Ihres DiReKT-Kontos löscht Ihre Trainings hier <strong>nicht</strong>{" "}
            mit. Das Konto gilt für alle Anwendungen des EFRE-Projekts DiReKT, nicht nur für
            den Calltrainer.
          </p>
          <p>
            Wenn Sie beides loswerden wollen, widerrufen Sie erst hier die Einwilligung und
            schreiben danach die Mail. Andersherum kommen Sie nicht mehr an Ihre Trainings heran, weil Sie
            sich ohne Konto nicht mehr anmelden können.
          </p>
        </InfoDetails>
      </section>
    </AppLayout>
  );
}

/** One label/value row. Renders nothing when the claim is absent, so a sparse
 *  account shows a shorter list rather than a column of dashes. */
function Fact({
  label,
  value,
  note,
}: {
  label: string;
  value: string | null;
  note?: string | null;
}) {
  if (!value) return null;
  return (
    <>
      <dt>{label}</dt>
      <dd>
        {value}
        {note && <span className="profile-flag">{note}</span>}
      </dd>
    </>
  );
}
