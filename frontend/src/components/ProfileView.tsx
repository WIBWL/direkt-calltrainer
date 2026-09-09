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
 *
 * The screen leads with what the user came for — their trainings, their
 * settings, their numbers — and folds the explanations into `InfoDetails`. Each
 * section keeps one plain sentence and hands the rest to the "i"; the full text
 * is the privacy statement's job, and it is linked rather than paraphrased,
 * because two copies of the same claim are two things to keep in sync and one
 * of them will lose.
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

      <section className="profile-section">
        <div className="progress-section-head">
          <h2>Ihre Trainings</h2>
          {/* The history lists single calls; the dashboard is the same data
              read across calls. Whoever is looking at one often wants the
              other. */}
          <Link to={ROUTES.progress} className="progress-section-link">
            Fortschritt ansehen
          </Link>
        </div>
        <SessionHistory />
      </section>

      <section className="card">
        <h2>Ihre Daten</h2>
        <p>
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
            schützt Sie allerdings nur begrenzt: wer Zugriff auf Anmeldung und Datenbank hat,
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
          <dd>In der Liste oben öffnen, Löschknopf am Seitenende.</dd>

          <dt>Alle Ihre Trainings</dt>
          <dd>Oben die Einwilligung widerrufen.</dd>

          <dt>Ihr ganzes DiReKT-Konto</dt>
          <dd>
            Mail an <a href={`mailto:${DIREKT_CONTACT}`}>{DIREKT_CONTACT}</a>.
          </dd>
        </dl>

        <InfoDetails label="Konto und Trainings hängen nicht zusammen">
          <p>
            Die Löschung Ihres DiReKT-Kontos löscht Ihre Trainings hier <strong>nicht</strong>{" "}
            mit — das Konto gilt für alle Anwendungen des EFRE-Projekts DiReKT, nicht nur für
            den Calltrainer.
          </p>
          <p>
            Wenn Sie beides loswerden wollen: erst hier die Einwilligung widerrufen, danach die
            Mail schreiben. Andersherum kommen Sie nicht mehr an Ihre Trainings heran, weil Sie
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
