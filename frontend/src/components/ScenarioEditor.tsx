import { Fragment, useEffect, useId, useRef, useState } from "react";

import { ApiError } from "../api";
import {
  CATEGORIES,
  CATEGORY_LABELS,
  createScenario,
  deleteScenario,
  EMPTY_DRAFT,
  extractPdfs,
  FALLBACK_FIELD_LIMITS,
  getFieldLimits,
  getScenario,
  MAX_DOCUMENT_MB,
  MAX_DOCUMENTS_TOTAL_MB,
  setScenarioVisibility,
  updateScenario,
  type CategoryChoice,
  type FieldLimits,
  toDraft,
  type ScenarioDraft,
  type TextField,
  type Visibility,
} from "../scenarioLibrary";
import { cx } from "../utils/cx";
import ConfirmDialog from "./ConfirmDialog";
import Modal from "./Modal";
import ShareToggle from "./ShareToggle";

interface ScenarioEditorProps {
  scenarioId: string | null;
  /** Sharing needs a company (ADR 0060). */
  tenantName: string | null;
  onClose: () => void;
  /** `savedId` is the row to select next, or null after a delete. */
  onSaved: (savedId: string | null) => void;
  /** After the share toggle, which applies at once. */
  onRefresh: () => void;
}

/** The placeholder is the field's only guidance. */
const FIELDS: {
  key: TextField;
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
    key: "briefing",
    label: "Briefing für die trainierende Person (optional)",
    placeholder: "Ihre Rolle, Ihr Spielraum, was ein gutes Ergebnis ist.",
    multiline: true,
  },
  // Goal and bar in one field: a goal without its bar is half a case.
  {
    key: "call_goal",
    label: "Ziel des Anrufs (optional)",
    placeholder: "Was will der Anrufer erreichen, und woran ist das Anliegen geklärt?",
    multiline: true,
  },
  {
    key: "case_facts",
    label: "Fakten des Falls (optional)",
    placeholder: "Zahlen, Namen, Daten. Leer = Modell improvisiert.",
    multiline: true,
  },
];

const formatElapsed = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

const MB = 1024 * 1024;

/** A drag does not filter by `accept`, and often carries no type. */
const isPdf = (file: File) =>
  file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

/** Create, edit or delete an authored Scenario (ADR 0058). */
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
  const [dragging, setDragging] = useState(false);
  // Tied by htmlFor: a <label> around the zone would hand its clicks to the textarea.
  const factsId = useId();
  const [error, setError] = useState<string | null>(null);
  const [confirmingClose, setConfirmingClose] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  // So a click outside only prompts when there is something to lose.
  const pristine = useRef<ScenarioDraft>(EMPTY_DRAFT);
  const isDirty = (Object.keys(draft) as (keyof ScenarioDraft)[]).some(
    (key) => draft[key] !== pristine.current[key],
  );

  // Escape or backdrop: blocked mid-save, and confirmed in-panel once touched.
  const dismiss = () => {
    if (confirmingClose) {
      setConfirmingClose(false);
    } else if (confirmingDelete) {
      setConfirmingDelete(false);
    } else if (!saving) {
      if (isDirty) setConfirmingClose(true);
      else onClose();
    }
  };

  // A missed drop would make the browser open the file and lose the draft.
  useEffect(() => {
    const swallow = (e: DragEvent) => e.preventDefault();
    window.addEventListener("dragover", swallow);
    window.addEventListener("drop", swallow);
    return () => {
      window.removeEventListener("dragover", swallow);
      window.removeEventListener("drop", swallow);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    // The API's own limits (ADR 0063); on failure the fallback stands.
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
        const draft = toDraft(detail);
        setDraft(draft);
        pristine.current = draft;
        setVisibility(detail.visibility === "public" ? "private" : detail.visibility);
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
      // Created private; apply "share" once it has an id.
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

  const handlePdfs = async (chosen: File[]) => {
    const files = chosen.filter(isPdf);
    if (files.length === 0) {
      setError("Bitte PDF-Dateien auswählen oder ablegen.");
      return;
    }
    // Refused at once; the server's answer is authoritative and worded the same.
    const named = (file: File, message: string) =>
      files.length > 1 ? `${file.name}: ${message}` : message;
    const tooBig = files.find((file) => file.size > MAX_DOCUMENT_MB * MB);
    if (tooBig) {
      setError(named(tooBig, `Die Datei ist größer als ${MAX_DOCUMENT_MB} MB.`));
      return;
    }
    if (files.reduce((sum, file) => sum + file.size, 0) > MAX_DOCUMENTS_TOTAL_MB * MB) {
      setError(`Die Dokumente sind zusammen größer als ${MAX_DOCUMENTS_TOTAL_MB} MB.`);
      return;
    }

    setPdfBusy(true);
    setPdfNote(null);
    setError(null);
    // No ETA is possible, so count up.
    setPdfElapsed(0);
    const started = Date.now();
    const ticker = window.setInterval(
      () => setPdfElapsed(Math.round((Date.now() - started) / 1000)),
      1000,
    );
    try {
      const doc = await extractPdfs(files);
      const what = files.length > 1 ? "den PDFs" : "dem PDF";
      const read =
        doc.documents.length > 1
          ? `${doc.documents.length} Dokumente, ${doc.pages} Seiten gelesen`
          : `${doc.pages} Seiten gelesen`;
      const replace =
        draft.case_facts.trim().length === 0 ||
        window.confirm(`Das Fakten-Feld mit den Fakten aus ${what} ersetzen?`);
      if (replace) {
        setDraft((d) => ({ ...d, case_facts: doc.text }));
        setPdfNote(
          doc.summarised
            ? `${read} und zusammengefasst. Bitte prüfen Sie den Text.`
            : `${read}. Zusammenfassung nicht möglich, Rohtext übernommen.`,
        );
      }
    } catch (e: unknown) {
      setError(
        e instanceof ApiError && e.detail
          ? e.detail
          : "Die PDFs konnten nicht gelesen werden.",
      );
    } finally {
      window.clearInterval(ticker);
      setPdfBusy(false);
    }
  };

  const handleDelete = async () => {
    if (scenarioId === null) return;
    setConfirmingDelete(false);
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
    <Modal
      labelledBy="editor-title"
      onDismiss={dismiss}
      overlay={
        <>
          {confirmingClose && (
            <ConfirmDialog
              title="Eingaben verwerfen?"
              body="Deine Änderungen an diesem Szenario werden nicht gespeichert."
              cancelLabel="Weiter bearbeiten"
              confirmLabel="Verwerfen"
              destructive
              onCancel={() => setConfirmingClose(false)}
              onConfirm={onClose}
            />
          )}

          {confirmingDelete && (
            <ConfirmDialog
              title="Dieses Szenario wirklich löschen?"
              body="Es verschwindet aus Ihrer Bibliothek. Bereits gespielte Trainings bleiben erhalten."
              cancelLabel="Behalten"
              confirmLabel="Löschen"
              destructive
              onCancel={() => setConfirmingDelete(false)}
              onConfirm={() => void handleDelete()}
            />
          )}
        </>
      }
    >
      <h2 id="editor-title">{isNew ? "Neues Szenario anlegen" : "Szenario bearbeiten"}</h2>

      {loading ? (
        <p>Wird geladen …</p>
      ) : (
        <>
          <div className="editor-fields">
            {FIELDS.map((field) => {
              const value = draft[field.key];
              const limit = limits[field.key];
              const counter = (
                <span
                  className={"editor-field-count" + (value.length >= limit ? " is-full" : "")}
                  aria-hidden="true"
                >
                  {value.length} / {limit}
                </span>
              );
              const caption = (
                <span>
                  {field.label}
                  {field.required && <span aria-hidden="true"> *</span>}
                </span>
              );
              return (
                <Fragment key={field.key}>
                  {field.key === "case_facts" ? (
                    <div className="editor-field">
                      <label className="editor-field-label" htmlFor={factsId}>
                        {caption}
                        {counter}
                      </label>

                      {/* Side by side with an "oder": two ways to fill one field, not two steps. */}
                      <div className="facts-split">
                        <textarea
                          id={factsId}
                          value={value}
                          placeholder={field.placeholder}
                          maxLength={limit}
                          onChange={(e) =>
                            setDraft((d) => ({ ...d, case_facts: e.target.value }))
                          }
                        />

                        <span className="facts-split-or">oder</span>

                        {/* A <label>, so a click opens the picker; the input stays the keyboard's way in. */}
                        <label
                          className={cx(
                            "pdf-dropzone",
                            dragging && "is-dragging",
                            pdfBusy && "is-busy",
                          )}
                          onDragOver={(e) => {
                            e.preventDefault();
                            if (!pdfBusy) setDragging(true);
                          }}
                          onDragLeave={(e) => {
                            // Crossing a child fires this too.
                            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
                              setDragging(false);
                            }
                          }}
                          onDrop={(e) => {
                            e.preventDefault();
                            setDragging(false);
                            if (pdfBusy) return;
                            void handlePdfs(Array.from(e.dataTransfer.files));
                          }}
                        >
                          <svg
                            className="pdf-dropzone-cloud"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden="true"
                          >
                            <path d="M7 18.5a4.5 4.5 0 0 1-.7-8.95 5.5 5.5 0 0 1 10.64-1.1A4.25 4.25 0 0 1 17.6 18.5" />
                            <path d="M12 21v-8.5" />
                            <path d="m8.8 15.7 3.2-3.2 3.2 3.2" />
                          </svg>

                          <span className="pdf-dropzone-title">
                            {pdfBusy
                              ? `PDFs werden ausgewertet … (${formatElapsed(pdfElapsed)})`
                              : "PDFs hierher ziehen"}
                          </span>

                          {!pdfBusy && (
                            <span className="pdf-dropzone-browse">Dateien durchsuchen</span>
                          )}

                          <input
                            type="file"
                            accept="application/pdf,.pdf"
                            multiple
                            disabled={pdfBusy}
                            onChange={(e) => {
                              const files = Array.from(e.target.files ?? []);
                              e.target.value = ""; // allow re-selecting the same files
                              if (files.length > 0) void handlePdfs(files);
                            }}
                          />
                        </label>
                      </div>

                      {pdfNote && <span className="pdf-upload-note">{pdfNote}</span>}
                    </div>
                  ) : (
                    <label className="editor-field">
                      <span className="editor-field-label">
                        {caption}
                        {counter}
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
                  )}

                  {field.key === "short_description" && (
                    <label className="editor-field">
                      <span className="editor-field-label">
                        <span>
                          Kategorie
                          <span aria-hidden="true"> *</span>
                        </span>
                      </span>
                      <select
                        value={draft.category}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            category: e.target.value as CategoryChoice,
                          }))
                        }
                      >
                        {/* Better uncategorised than filed wrongly (ADR 0072). */}
                        <option value="">Ohne Kategorie</option>
                        {CATEGORIES.map((c) => (
                          <option key={c} value={c}>
                            {CATEGORY_LABELS[c]}
                          </option>
                        ))}
                      </select>
                    </label>
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
                onClick={() => setConfirmingDelete(true)}
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
    </Modal>
  );
}
