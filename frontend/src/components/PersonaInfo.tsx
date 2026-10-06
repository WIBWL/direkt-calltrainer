import { useEffect, useState } from "react";

import { ApiError } from "../api";
import { getPersona } from "../personas";
import type { PersonaDetail } from "../protocol";
import Modal from "./Modal";
import PersonaAvatar from "./PersonaAvatar";

interface PersonaInfoProps {
  personaId: string;
  /** The heading until the fetch lands. */
  personaName: string;
  onClose: () => void;
}

/** An absent field is left out; `role` sits beside the name instead. */
const SECTIONS: {
  key: "traits" | "training_goal";
  label: string;
}[] = [
  { key: "traits", label: "Persönlichkeit" },
  { key: "training_goal", label: "Was Sie hier trainieren" },
];

/** Read-only (Personas are curated, ADR 0058), German display text only (ADR 0043). */
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
      {/* Rendered before the fetch lands, with the initials as fallback. */}
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
              {/* ADR 0045: tendencies, not a checklist. */}
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
