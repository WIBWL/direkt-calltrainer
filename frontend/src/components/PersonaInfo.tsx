import { useCallback, useEffect, useState } from "react";

import { ApiError, getPersona } from "../api";
import type { PersonaDetail } from "../protocol";
import PersonaAvatar from "./PersonaAvatar";

interface PersonaInfoProps {
  /** The Persona to describe — its `extern_id` (ADR 0050). */
  personaId: string;
  /** Shown as the heading until the fetch lands, so the panel never opens
   * nameless: the card the user just clicked already knows the name. */
  personaName: string;
  onClose: () => void;
}

/** Rows in display order. `traits` may be null and `objections` may be empty;
 * an absent field is left out rather than shown as an empty heading. */
const SECTIONS: {
  key: "role" | "traits" | "training_goal";
  label: string;
}[] = [
  { key: "role", label: "Rolle" },
  { key: "traits", label: "Persönlichkeit" },
  { key: "training_goal", label: "Was Sie hier trainieren" },
];

/**
 * Read-only portrait of a Persona, opened by the "i" on its selection card.
 *
 * Deliberately the same modal shell as ScenarioEditor (`editor-backdrop` /
 * `editor-panel` / `editor-scroll`, Escape and click-outside to dismiss), so
 * the two panels on the setup screen read as one thing. What it does *not*
 * borrow is the form: Personas are curated, not User-authored (ADR 0058), so
 * there is nothing to edit and no Save — the fields are static text, and the
 * only action is closing. There is no unsaved-changes guard for the same
 * reason; dismissing can never lose anything.
 *
 * Everything shown is German display text (ADR 0043). The English `role`,
 * `traits` and `behavior` that brief the model stay on the server, and so does
 * an objection's English `text`; what arrives here are their display twins.
 */
export default function PersonaInfo({ personaId, personaName, onClose }: PersonaInfoProps) {
  const [detail, setDetail] = useState<PersonaDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const dismiss = useCallback(() => onClose(), [onClose]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") dismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dismiss]);

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
    <div
      className="editor-backdrop"
      role="presentation"
      onMouseDown={(e) => {
        // Same rule as the editor: only a press that starts and ends on the
        // backdrop counts, so selecting text and dragging out does not close.
        if (e.target === e.currentTarget) dismiss();
      }}
    >
      <div
        className="editor-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="persona-info-title"
      >
        <div className="editor-scroll">
          <h2 id="persona-info-title">{detail?.name ?? personaName}</h2>

          {error && <p className="error">{error}</p>}

          {!detail && !error && <p>Wird geladen …</p>}

          {detail && (
            <>
              {/* Under the heading rather than above it: the panel is opened
                  from a card that already showed the picture, so what is new
                  here is the text. */}
              <PersonaAvatar
                name={detail.name}
                src={detail.avatar_url}
                className="persona-info-portrait"
              />

              <p className="persona-info-language">Spricht {detail.language}</p>

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
            </>
          )}

          <div className="editor-actions">
            <span className="editor-actions-spacer" />
            <button type="button" onClick={onClose}>
              Schließen
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
