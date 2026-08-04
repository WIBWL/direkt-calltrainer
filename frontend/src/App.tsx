import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "";

interface Persona {
  id: string;
  name: string;
  training_goal: string;
}

interface Language {
  id: string;
  name: string;
}

interface ProcessResult {
  transcript: string;
  reply: string;
  audio_base64: string;
}

type Status = { kind: "idle" | "loading" | "success" | "error"; message: string };

export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [languageId, setLanguageId] = useState<string | null>(null);

  const [fileName, setFileName] = useState("🎙️ Audiodatei auswählen");
  const [status, setStatus] = useState<Status>({ kind: "idle", message: "" });
  const [result, setResult] = useState<ProcessResult | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/personas`)
      .then((r) => r.json())
      .then((data: Persona[]) => {
        setPersonas(data);
        if (data.length > 0) setPersonaId(data[0].id);
      })
      .catch((e) =>
        setStatus({ kind: "error", message: `Personas konnten nicht geladen werden: ${e.message}` }),
      );
    fetch(`${API_URL}/api/languages`)
      .then((r) => r.json())
      .then((data: Language[]) => {
        setLanguages(data);
        if (data.length > 0) setLanguageId(data[0].id);
      })
      .catch((e) =>
        setStatus({ kind: "error", message: `Sprachen konnten nicht geladen werden: ${e.message}` }),
      );
  }, []);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !personaId || !languageId) return;

    setFileName(file.name);
    setResult(null);
    setStatus({ kind: "loading", message: "Verarbeite Audiodatei …" });

    const formData = new FormData();
    formData.append("file", file);
    formData.append("persona_id", personaId);
    formData.append("language_id", languageId);

    try {
      const response = await fetch(`${API_URL}/api/process`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || response.statusText);
      }
      const data: ProcessResult = await response.json();
      setResult(data);
      setStatus({ kind: "success", message: "Fertig." });
    } catch (e) {
      setStatus({ kind: "error", message: `Fehler: ${(e as Error).message}` });
    }
  }

  const readyForUpload = personaId !== null && languageId !== null;

  return (
    <>
      <div className="eyebrow">Calltrainer</div>
      <h1>Training starten</h1>

      <h2>Persona</h2>
      <div className="persona-grid">
        {personas.map((p) => (
          <button
            key={p.id}
            className={"persona-card" + (p.id === personaId ? " selected" : "")}
            onClick={() => setPersonaId(p.id)}
            type="button"
          >
            <span className="persona-name">{p.name}</span>
            <span className="persona-goal">{p.training_goal}</span>
          </button>
        ))}
      </div>

      <h2>Sprache</h2>
      <div className="language-row">
        {languages.map((l) => (
          <button
            key={l.id}
            className={"language-pill" + (l.id === languageId ? " selected" : "")}
            onClick={() => setLanguageId(l.id)}
            type="button"
          >
            {l.name}
          </button>
        ))}
      </div>

      <h2>Audiodatei</h2>
      <label className={"upload" + (readyForUpload ? "" : " disabled")} htmlFor="file">
        <span>{fileName}</span>
        <input
          type="file"
          id="file"
          accept="audio/*"
          onChange={handleFileChange}
          disabled={!readyForUpload}
        />
      </label>

      <p id="status" className={status.kind}>
        {status.message}
      </p>

      {result && (
        <>
          <div className="card">
            <h2>Transkript</h2>
            <p>{result.transcript}</p>
          </div>
          <div className="card">
            <h2>Antwort der Persona</h2>
            <p>{result.reply}</p>
          </div>
          <div className="card">
            <h2>Sprachausgabe</h2>
            <audio controls src={`data:audio/wav;base64,${result.audio_base64}`} />
          </div>
        </>
      )}
    </>
  );
}
