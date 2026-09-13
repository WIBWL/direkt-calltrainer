import { useEffect, useState } from "react";

import { ApiError, getPersona } from "../api";
import type { PersonaDetail } from "../protocol";
import Modal from "./Modal";
import PersonaAvatar from "./PersonaAvatar";

interface PersonaInfoProps {
  /** The Persona to describe — its `extern_id` (ADR 0050). */
  personaId: string;
  /** Shown as the heading until the fetch lands, so the panel never opens
   * nameless: the card the user just clicked already knows the name. */
  personaName: string;
  onClose: () => void;
}

/** Rows in display order. `traits` may be null; an absent field is left out
 * rather than shown as an empty heading. `role` is not among them — it is part
 * of the header beside the name, and a second copy under a heading of its own
 * would put the same sentence on the screen twice. */
const SECTIONS: {
  key: "traits" | "training_goal";
  label: string;
}[] = [
  { key: "traits", label: "Persönlichkeit" },
  { key: "training_goal", label: "Was Sie hier trainieren" },
];

/**
 * Read-only portrait of a Persona, opened by the "i" on its selection card.
 *
 * Deliberately the same modal shell as ScenarioEditor (`Modal`: Escape and
 * click-outside to dismiss), so the two panels on the setup screen read as one
 * thing. What it does *not* borrow is the form: Personas are curated, not
 * User-authored (ADR 0058), so there is nothing to edit and no Save — the
 * fields are static text, and the only action is closing. There is no
 * unsaved-changes guard for the same reason; dismissing can never lose
 * anything.
 *
 * Everything shown is German display text (ADR 0043). The English `role`,
 * `traits` and `behavior` that brief the model stay on the server, and so does
 * an objection's English `text`; what arrives here are their display twins.
 */
export default function PersonaInfo({ personaId, personaName, onClose }: PersonaInfoProps) {
  const [detail, setDetail] = useState<PersonaDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setError(null);
    getPersona(personaId)
      .then((d) => !cancelled && setDetail(d))
      .catch((e: unknown) =>
        !cancelled &&
        setError(
          e instanceof ApiError && e.status === 404
            ? "Diese Persona gibt es nicht mehr."
            : "Die Angaben konnten nicht geladen werden.",
        ),
      );
    return () => {
      cancelled = true;
    };
  }, [personaId]);

  return (
    <Modal labelledBy="persona-info-title" onDismiss={onClose}>
      {/* Rendered before the fetch lands too, so the panel opens on the
          Persona rather than on a blank box: the card the user just clicked
          knows the name, and the portrait falls back to the initials until
          the detail arrives. */}
      <div className="persona-info-header">
        <PersonaAvatar
          name={detail?.name ?? personaName}
          src={detail?.avatar_url}
          className="persona-info-portrait"
        />

        <div className="persona-info-identity">
          <h2 id="persona-info-title">{detail?.name ?? personaName}</h2>

          {detail && (
            <>
              <p className="persona-info-role">{detail.role}</p>
              <p className="persona-info-language">Spricht {detail.language}</p>
            </>
          )}
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {!detail && !error && <p>Wird geladen …</p>}

      {detail && (
        <div className="persona-info-sections">
          {SECTIONS.map((section) => {
            const value = detail[section.key];
            if (!value) return null;
            return (
              <section className="persona-info-section" key={section.key}>
                <h3>{section.label}</h3>
                <p>{value}</p>
              </section>
            );
          })}

          {detail.objections.length > 0 && (
            <section className="persona-info-section">
              <h3>Typische Einwände</h3>
              {/* R-12 / ADR 0045: tendencies, not a script. Said plainly,
                  because a user who reads this as a checklist would expect
                  all of them in every call. */}
              <p className="persona-info-hint">
                Damit ist im Gespräch zu rechnen, nicht jedes Mal und nicht in
                dieser Reihenfolge.
              </p>
              <ul className="persona-info-objections">
                {detail.objections.map((objection) => (
                  <li key={objection}>{objection}</li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      <div className="editor-actions">
        <span className="editor-actions-spacer" />
        <button type="button" onClick={onClose}>
          Schließen
        </button>
      </div>
    </Modal>
  );
}
