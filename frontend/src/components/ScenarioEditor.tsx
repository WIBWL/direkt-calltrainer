import { Fragment, useEffect, useState } from "react";

import { ApiError } from "../api";
import {
  createScenario,
  deleteScenario,
  EMPTY_DRAFT,
  extractPdf,
  FALLBACK_FIELD_LIMITS,
  getFieldLimits,
  getScenario,
  setScenarioVisibility,
  updateScenario,
  type FieldLimits,
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

/** The placeholder is the field's guidance in one short line, greyed out while
 * the field is empty — so there is no separate always-visible hint. */
const FIELDS: {
  key: keyof ScenarioDraft;
  label: string;
  placeholder: string;
  multiline?: boolean;
  required?: boolean;
}[] = [
  { key: "name", label: "Titel", placeholder: "Kurzer, sprechender Titel", required: true },
  {
    key: "short_description",
    label: "Kurzbeschreibung",
    placeholder: "Ein Satz für die Auswahlkarte",
    required: true,
  },
  {
    key: "description",
    label: "Situation",
    placeholder: "Worum geht es im Anruf? Kurz, aber konkret.",
    multiline: true,
    required: true,
  },
  {
    key: "case_facts",
    label: "Fakten des Falls (optional)",
    placeholder: "Zahlen, Namen, Daten. Leer = Modell improvisiert.",
    multiline: true,
  },
  {
    key: "call_goal",
    label: "Ziel des Anrufs (optional)",
    placeholder: "Was will der Anrufer erreichen?",
    multiline: true,
  },
  {
    key: "success_condition",
    label: "Erfolgsbedingung (optional)",
    placeholder: "Woran ist das Anliegen geklärt?",
    multiline: true,
  },
];

/** Seconds as m:ss, for the "PDF wird ausgewertet …" counter. */
const formatElapsed = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

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
  const [limits, setLimits] = useState<FieldLimits>(FALLBACK_FIELD_LIMITS);
  const [visibility, setVisibility] = useState<Visibility>("private");
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfElapsed, setPdfElapsed] = useState(0);
  const [pdfNote, setPdfNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Cap the inputs from the same limits the API validates against, rather
    // than a bundled copy that drifts (ADR 0063). On failure the fallback
    // stands and the server still rejects an over-long field.
    getFieldLimits()
      .then((l) => !cancelled && setLimits(l))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

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
    // No real ETA is possible (thinking-mode length varies), so just count up
    // so the user can see it is still working, not frozen.
    setPdfElapsed(0);
    const started = Date.now();
    const ticker = window.setInterval(
      () => setPdfElapsed(Math.round((Date.now() - started) / 1000)),
      1000,
    );
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
      window.clearInterval(ticker);
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
              {FIELDS.map((field) => {
                const value = draft[field.key];
                const limit = limits[field.key];
                return (
                  <Fragment key={field.key}>
                    <label className="editor-field">
                      <span className="editor-field-label">
                        <span>
                          {field.label}
                          {field.required && <span aria-hidden="true"> *</span>}
                        </span>
                        <span
                          className={
                            "editor-field-count" +
                            (value.length >= limit ? " is-full" : "")
                          }
                          aria-hidden="true"
                        >
                          {value.length} / {limit}
                        </span>
                      </span>
                      {field.multiline ? (
                        <textarea
                          value={value}
                          placeholder={field.placeholder}
                          maxLength={limit}
                          rows={3}
                          onChange={(e) =>
                            setDraft((d) => ({ ...d, [field.key]: e.target.value }))
                          }
                        />
                      ) : (
                        <input
                          type="text"
                          value={value}
                          placeholder={field.placeholder}
                          maxLength={limit}
                          onChange={(e) =>
                            setDraft((d) => ({ ...d, [field.key]: e.target.value }))
                          }
                        />
                      )}
                    </label>

                    {field.key === "case_facts" && (
                      <div className="pdf-upload">
                        <label className="pdf-upload-button">
                          {pdfBusy
                            ? `PDF wird ausgewertet … (${formatElapsed(pdfElapsed)})`
                            : "Fakten aus PDF (KI)"}
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
                          dort bearbeitet werden. Bei großen Dokumenten kann das über
                          eine Minute dauern.
                        </span>
                        {pdfNote && <span className="pdf-upload-note">{pdfNote}</span>}
                      </div>
                    )}
                  </Fragment>
                );
              })}
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
