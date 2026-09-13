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
  // Situation first, then the briefing: the case exists before the trainee's
  // side of it does, and the two are read that way round in the info panel too.
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
  // Goal and bar in one field: a goal without the mark that settles it is half
  // a case, and the caller weighs both the same way — silently, against what
  // has actually been said.
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

/** Seconds as m:ss, for the document-upload progress counter. */
const formatElapsed = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

const MB = 1024 * 1024;

/** A dropped file carries no type often enough that the extension has to count
 * too — the file picker filters by `accept`, a drag does not. */
const isPdf = (file: File) =>
  file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

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
  const [dragging, setDragging] = useState(false);
  // The facts field's own id: its label sits outside it now, above the row it
  // shares with the drop zone, so the two are tied by htmlFor rather than by
  // nesting — a <label> around both would hand a click on the zone to the
  // textarea.
  const factsId = useId();
  const [error, setError] = useState<string | null>(null);
  const [confirmingClose, setConfirmingClose] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  // What the draft looked like when the editor opened (empty for a new
  // Scenario, the loaded row for an edit) — so a click outside only prompts
  // when there is really something to lose.
  const pristine = useRef<ScenarioDraft>(EMPTY_DRAFT);
  const isDirty = (Object.keys(draft) as (keyof ScenarioDraft)[]).some(
    (key) => draft[key] !== pristine.current[key],
  );

  // Escape or a click on the backdrop. An open question over the panel is
  // closed first; otherwise the panel closes — blocked mid-save, and once a
  // field has been touched only after confirming through the in-panel dialog
  // (a native window.confirm would break out of the app's look).
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

  // A file dropped anywhere but the zone below would otherwise be *opened* by
  // the browser, which navigates away from the editor and takes the unsaved
  // draft with it. While this panel is up, a missed drop does nothing instead.
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
        const draft = toDraft(detail);
        setDraft(draft);
        pristine.current = draft;
        // Never "public" here: the editor only opens on an editable row.
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

  const handlePdfs = async (chosen: File[]) => {
    const files = chosen.filter(isPdf);
    if (files.length === 0) {
      setError("Bitte PDF-Dateien auswählen oder ablegen.");
      return;
    }
    // Checked here as well as on the server so an oversized drop is refused at
    // once rather than after the upload. The server's answer is authoritative;
    // these messages deliberately read the same, and name the file only when
    // there is more than one, exactly as the server does.
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
    // No real ETA is possible (thinking-mode length varies), so just count up
    // so the user can see it is still working, not frozen.
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

                      {/* Typing them and dropping the documents in fill the
                          same field, so they sit side by side at the same
                          size with an "oder" between — not one under the
                          other, which would read as a second step. */}
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

                        {/* A <label>, so a click anywhere in the zone opens
                            the picker and the hidden input stays the
                            keyboard's way in. */}
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
                            // Only when the pointer really left the zone —
                            // crossing a child fires this too.
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
                        {/* Marked like the other answers that have to be
                            given, and "Ohne Kategorie" is one of them —
                            which is why it is not in `canSave`: the field
                            cannot be left unanswered, because it starts on
                            a valid answer. A Scenario that fits none of the
                            four is better uncategorised than filed wrongly
                            (ADR 0072); it then shows under "Alle" and under
                            no category. */}
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
