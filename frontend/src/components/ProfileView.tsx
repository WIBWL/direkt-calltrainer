import { useAuth } from "react-oidc-context";

import { useAccount } from "../hooks/useAccount";
import AppLayout from "./AppLayout";
import ConsentSettings from "./ConsentSettings";
import DataOverview from "./DataOverview";
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
 * Everything shown is read-only, and everything shown is a claim the realm
 * actually asserts — nothing is derived, invented or filled in. Identity lives
 * in Keycloak and the app has no User table (ADR 0031), so there is nothing
 * here the backend could accept an edit for; the screen says so rather than
 * offering fields that would have to fail on save.
 *
 * What is deliberately *not* shown: the Keycloak `sub` and the realm URL, which
 * answer no question a user has and only invite them to worry about an
 * identifier they cannot act on, and the access token's expiry, which describes
 * a five-minute token rather than their session (see `useAccount`).
 */
export default function ProfileView() {
  const account = useAccount();
  const auth = useAuth();

  return (
    <AppLayout accountActive pageClassName="app-page-narrow profile-page">
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
        <p className="profile-note">
          Diese Angaben stammen aus Ihrem DiReKT-Konto und werden dort verwaltet, nicht im
          Calltrainer. Sie lassen sich hier deshalb ansehen, aber nicht ändern.
        </p>
      </section>

      <section className="card">
        <h2>Speicherung Ihrer Trainings</h2>
        <ConsentSettings />
      </section>

      <section className="profile-section">
        <h2>Ihre Trainings</h2>
        <SessionHistory />
      </section>

      <section className="card">
        <h2>Ihre Daten</h2>
        <p>
          Von einem Training bleiben drei Dinge: der Gesprächsverlauf als Text, die gemessenen
          Kennzahlen und Ihre Rückmeldung. Gespeichert wird erst, wenn Sie das Gespräch zu Ende
          führen. Brechen Sie ab, bleibt nichts zurück.
        </p>
        <p>
          <strong>Ihre Tonaufnahme wird nicht gespeichert.</strong> Sie wird während des
          Gesprächs ausgewertet und danach gelöscht.
        </p>

        <DataOverview />

        <ProcessingNotice />

        <p className="profile-note">
          Ihre Trainings liegen unter einer technischen Kennung, nicht unter Ihrem Namen. Das
          schützt Sie allerdings nur begrenzt. Wer Zugriff auf Anmeldung und Datenbank hat, kann
          beides zusammenbringen, und im Gesprächsverlauf steht ohnehin, was Sie gesagt haben.
        </p>
      </section>

      <section className="card">
        <h2>Daten löschen</h2>

        <dl className="deletion-paths">
          <dt>Ein einzelnes Training</dt>
          <dd>
            Öffnen Sie es in der Liste oben. Ganz unten auf der Seite steht der Löschknopf.
          </dd>

          <dt>Alle Ihre Trainings</dt>
          <dd>
            Widerrufen Sie oben die Einwilligung zur Speicherung. Damit werden alle
            gespeicherten Trainings gelöscht, und es wird auch nichts Neues mehr gespeichert.
          </dd>

          <dt>Ihr ganzes DiReKT-Konto</dt>
          <dd>
            Schreiben Sie an <a href={`mailto:${DIREKT_CONTACT}`}>{DIREKT_CONTACT}</a>. Das
            Konto gilt für alle Anwendungen des EFRE-Projekts DiReKT, nicht nur für den
            Calltrainer.
          </dd>
        </dl>

        <p className="profile-warning">
          <strong>Wichtig:</strong> Die Löschung Ihres DiReKT-Kontos löscht Ihre Trainings hier
          nicht mit. Beides ist getrennt. Wenn Sie beides loswerden wollen, widerrufen Sie
          zuerst hier die Einwilligung und schreiben Sie danach die Mail. Andersherum kommen Sie
          nicht mehr an Ihre Trainings heran, weil Sie sich ohne Konto nicht mehr anmelden
          können.
        </p>
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
