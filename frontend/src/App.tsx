import { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "";

interface ProcessResult {
  transcript: string;
  translation: string;
  audio_base64: string;
}

type Status = { kind: "idle" | "loading" | "success" | "error"; message: string };

export default function App() {
  const [fileName, setFileName] = useState("🎙️ Audiodatei auswählen");
  const [status, setStatus] = useState<Status>({ kind: "idle", message: "" });
  const [result, setResult] = useState<ProcessResult | null>(null);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    setResult(null);
    setStatus({ kind: "loading", message: "Verarbeite Audiodatei …" });

    const formData = new FormData();
    formData.append("file", file);

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

  return (
    <>
      <div className="eyebrow">Calltrainer</div>
      <h1>Audiodatei hochladen</h1>

      <label className="upload" htmlFor="file">
        <span>{fileName}</span>
        <input type="file" id="file" accept="audio/*" onChange={handleFileChange} />
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
            <h2>Übersetzung (Englisch)</h2>
            <p>{result.translation}</p>
          </div>
          <div className="card">
            <h2>Sprachausgabe</h2>
            <audio controls src={`data:audio/mpeg;base64,${result.audio_base64}`} />
          </div>
        </>
      )}
    </>
  );
}
