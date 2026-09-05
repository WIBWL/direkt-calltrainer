import { Fragment, useEffect, useState } from "react";

import { ApiError } from "../api";
import {
  createScenario,
  deleteScenario,
  EMPTY_DRAFT,
  extractPdf,
  FIELD_LIMITS,
  getScenario,
  setScenarioVisibility,
  updateScenario,
  type ScenarioDraft,
  type Sichtbarkeit,
} from "../scenarioLibrary";
import ShareToggle from "./ShareToggle";

interface ScenarioEditorProps {
  /** null = author a new Scenario; an id = edit that one. */
  scenarioId: string | null;
  /** The caller's company name, or null for the `default` tenant. Sharing is
   * offered only when it is set — "share" means "with my colleagues", which a
   * user with no company does not have (ADR 0060). */
  companyLabel: string | null;
  onClose: () => void;
  /** Called after a successful save or delete. `savedId` is the id to select
   * next (the new/edited Scenario), or null after a delete. Closes the editor. */
  onSaved: (savedId: string | null) => void;
  /** Reload the library list without closing the editor — after the "share"
   * toggle, which applies immediately. */
  onRefresh: () => void;
}

const FIELDS: {
  key: keyof ScenarioDraft;
  label: string;
  hint?: string;
  multiline?: boolean;
  required?: boolean;
}[] = [
  { key: "name", label: "Titel", required: true },
  { key: "kurzbeschreibung", label: "Kurzbeschreibung (auf der Karte)", required: true },
  { key: "szenariotyp", label: "Kategorie (optional)" },
  {
    key: "beschreibung",
    label: "Situation",
    hint: "Worum geht es im Anruf? Wird dem Modell als Kontext gegeben — kurz, aber konkret.",
    multiline: true,
    required: true,
  },
  {
    key: "fallfakten",
    label: "Fakten des Falls (optional)",
    hint: "Konkrete Zahlen, Namen, Daten. Leer lassen heißt: das Modell improvisiert.",
    multiline: true,
  },
  { key: "anrufziel", label: "Ziel des Anrufs (optional)", multiline: true },
  { key: "erfolgsbedingung", label: "Erfolgsbedingung (optional)", multiline: true },
];

/** Create / edit / delete a user-authored Scenario (ADR 0058). Rendered as a
 * modal over the setup screen. */
export default function ScenarioEditor({
  scenarioId,
  companyLabel,
  onClose,
  onSaved,
  onRefresh,
}: ScenarioEditorProps) {
  const isNew = scenarioId === null;
  const [draft, setDraft] = useState<ScenarioDraft>(EMPTY_DRAFT);
  const [sichtbarkeit, setSichtbarkeit] = useState<Sichtbarkeit>("privat");
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfNote, setPdfNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (scenarioId === null) return;
    let cancelled = false;
    setLoading(true);
    getScenario(scenarioId)
      .then((detail) => {
        if (cancelled) return;
        const { id: _id, sichtbarkeit: sicht, ...rest } = detail;
        setDraft(rest);
        setSichtbarkeit(sicht);
      })
      .catch((e: unknown) =>
        setError(e instanceof ApiError && e.status === 404
          ? "Dieses Szenario gibt es nicht mehr."
          : "Szenario konnte nicht geladen werden."),
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [scenarioId]);

  const canSave =
    !saving &&
    draft.name.trim().length > 0 &&
    draft.kurzbeschreibung.trim().length > 0 &&
    draft.beschreibung.trim().length > 0;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const saved = isNew
        ? await createScenario(draft)
        : await updateScenario(scenarioId as string, draft);
      // A new Scenario is created private; if the user ticked "share" in the
      // form, apply that now that it has an id.
      if (isNew && sichtbarkeit === "unternehmen") {
        await setScenarioVisibility(saved.id, "unternehmen");
      }
      onSaved(saved.id);
    } catch (e: unknown) {
      setError(
        e instanceof ApiError && e.status === 422
          ? "Ein Feld ist zu lang."
          : "Speichern fehlgeschlagen.",
      );
      setSaving(false);
    }
  };

  const handleShareToggle = async (next: Sichtbarkeit) => {
    const previous = sichtbarkeit;
    setSichtbarkeit(next); // optimistic; for a new Scenario handleSave applies it
    if (scenarioId === null) return;
    try {
      await setScenarioVisibility(scenarioId, next);
      onRefresh(); // the library list's badge/filter now change
    } catch {
      setSichtbarkeit(previous);
      setError("Freigabe konnte nicht geändert werden.");
    }
  };

  const handlePdf = async (file: File) => {
    setPdfBusy(true);
    setPdfNote(null);
    setError(null);
    try {
      const doc = await extractPdf(file);
      const replace =
        draft.fallfakten.trim().length === 0 ||
        window.confirm("Das Fakten-Feld mit den Fakten aus dem PDF ersetzen?");
      if (replace) {
        setDraft((d) => ({ ...d, fallfakten: doc.text }));
        setPdfNote(
          doc.zusammengefasst
            ? `${doc.seiten} Seiten gelesen und zusammengefasst — bitte prüfen.`
            : `${doc.seiten} Seiten gelesen. Zusammenfassung nicht möglich, Rohtext übernommen.`,
        );
      }
    } catch (e: unknown) {
      setError(e instanceof ApiError && e.detail ? e.detail : "Das PDF konnte nicht gelesen werden.");
    } finally {
      setPdfBusy(false);
    }
  };

  const handleDelete = async () => {
    if (scenarioId === null) return;
    if (!window.confirm("Dieses Szenario wirklich löschen?")) return;
    setSaving(true);
    setError(null);
    try {
      await deleteScenario(scenarioId);
      onSaved(null);
    } catch {
      setError("Löschen fehlgeschlagen.");
      setSaving(false);
    }
  };

  return (
    <div className="editor-backdrop" role="dialog" aria-modal="true" aria-labelledby="editor-title">
      <div className="editor-panel">
        <h2 id="editor-title">{isNew ? "Neues Szenario" : "Szenario bearbeiten"}</h2>

        {loading ? (
          <p>Wird geladen …</p>
        ) : (
          <>
            <div className="editor-fields">
              {FIELDS.map((field) => (
                <Fragment key={field.key}>
                  <label className="editor-field">
                    <span className="editor-field-label">
                      {field.label}
                      {field.required && <span aria-hidden="true"> *</span>}
                    </span>
                    {field.hint && <span className="editor-field-hint">{field.hint}</span>}
                    {field.multiline ? (
                      <textarea
                        value={draft[field.key]}
                        maxLength={FIELD_LIMITS[field.key]}
                        rows={3}
                        onChange={(e) =>
                          setDraft((d) => ({ ...d, [field.key]: e.target.value }))
                        }
                      />
                    ) : (
                      <input
                        type="text"
                        value={draft[field.key]}
                        maxLength={FIELD_LIMITS[field.key]}
                        onChange={(e) =>
                          setDraft((d) => ({ ...d, [field.key]: e.target.value }))
                        }
                      />
                    )}
                  </label>

                  {field.key === "fallfakten" && (
                    <div className="pdf-upload">
                      <label className="pdf-upload-button">
                        {pdfBusy ? "PDF wird ausgewertet …" : "Fakten aus PDF (KI)"}
                        <input
                          type="file"
                          accept="application/pdf,.pdf"
                          disabled={pdfBusy}
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            e.target.value = ""; // allow re-selecting the same file
                            if (file) void handlePdf(file);
                          }}
                        />
                      </label>
                      <span className="editor-field-hint">
                        Nur PDFs mit auslesbarem Text (keine Scans). Die KI zieht die
                        relevanten Fakten heraus; das Ergebnis landet im Feld und kann
                        dort bearbeitet werden.
                      </span>
                      {pdfNote && <span className="pdf-upload-note">{pdfNote}</span>}
                    </div>
                  )}
                </Fragment>
              ))}
            </div>

            {companyLabel !== null && (
              <ShareToggle
                sichtbarkeit={sichtbarkeit}
                onChange={handleShareToggle}
                label={`Mit ${companyLabel} teilen`}
                hint="Kolleginnen und Kollegen sehen dieses Szenario dann in ihrer Bibliothek."
              />
            )}

            {error && <p className="error">{error}</p>}

            <div className="editor-actions">
              {!isNew && (
                <button
                  type="button"
                  className="editor-delete"
                  onClick={handleDelete}
                  disabled={saving}
                >
                  Löschen
                </button>
              )}
              <span className="editor-actions-spacer" />
              <button type="button" onClick={onClose} disabled={saving}>
                Abbrechen
              </button>
              <button
                type="button"
                className="editor-save"
                onClick={handleSave}
                disabled={!canSave}
              >
                {saving ? "Speichert …" : "Speichern"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
