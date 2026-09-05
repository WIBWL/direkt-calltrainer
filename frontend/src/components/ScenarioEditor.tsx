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
  type Visibility,
} from "../scenarioLibrary";
import ShareToggle from "./ShareToggle";

interface ScenarioEditorProps {
  /** null = author a new Scenario; an id = edit that one. */
  scenarioId: string | null;
  /** The caller's company name, or null for the `default` tenant. Sharing is
   * offered only when it is set — "share" means "with my colleagues", which a
   * user with no company does not have (ADR 0060). */
  tenantName: string | null;
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
  { key: "short_description", label: "Kurzbeschreibung (auf der Karte)", required: true },
  { key: "scenario_type", label: "Kategorie (optional)" },
  {
    key: "description",
    label: "Situation",
    hint: "Worum geht es im Anruf? Wird dem Modell als Kontext gegeben — kurz, aber konkret.",
    multiline: true,
    required: true,
  },
  {
    key: "case_facts",
    label: "Fakten des Falls (optional)",
    hint: "Konkrete Zahlen, Namen, Daten. Leer lassen heißt: das Modell improvisiert.",
    multiline: true,
  },
  { key: "call_goal", label: "Ziel des Anrufs (optional)", multiline: true },
  { key: "success_condition", label: "Erfolgsbedingung (optional)", multiline: true },
];

/** Create / edit / delete a user-authored Scenario (ADR 0058). Rendered as a
 * modal over the setup screen. */
export default function ScenarioEditor({
  scenarioId,
  tenantName,
  onClose,
  onSaved,
  onRefresh,
}: ScenarioEditorProps) {
  const isNew = scenarioId === null;
  const [draft, setDraft] = useState<ScenarioDraft>(EMPTY_DRAFT);
  const [visibility, setVisibility] = useState<Visibility>("private");
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
        const { id: _id, visibility: vis, ...rest } = detail;
        setDraft(rest);
        setVisibility(vis);
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
    draft.short_description.trim().length > 0 &&
    draft.description.trim().length > 0;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const saved = isNew
        ? await createScenario(draft)
        : await updateScenario(scenarioId as string, draft);
      // A new Scenario is created private; if the user ticked "share" in the
      // form, apply that now that it has an id.
      if (isNew && visibility === "tenant") {
        await setScenarioVisibility(saved.id, "tenant");
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

  const handleShareToggle = async (next: Visibility) => {
    const previous = visibility;
    setVisibility(next); // optimistic; for a new Scenario handleSave applies it
    if (scenarioId === null) return;
    try {
      await setScenarioVisibility(scenarioId, next);
      onRefresh(); // the library list's badge/filter now change
    } catch {
      setVisibility(previous);
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
        draft.case_facts.trim().length === 0 ||
        window.confirm("Das Fakten-Feld mit den Fakten aus dem PDF ersetzen?");
      if (replace) {
        setDraft((d) => ({ ...d, case_facts: doc.text }));
        setPdfNote(
          doc.summarised
            ? `${doc.pages} Seiten gelesen und zusammengefasst — bitte prüfen.`
            : `${doc.pages} Seiten gelesen. Zusammenfassung nicht möglich, Rohtext übernommen.`,
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

                  {field.key === "case_facts" && (
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

            {tenantName !== null && (
              <ShareToggle
                visibility={visibility}
                onChange={handleShareToggle}
                label={`Mit ${tenantName} teilen`}
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
