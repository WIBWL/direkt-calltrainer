import { useEffect, useState } from "react";

import { apiFetch, authorizedFetch } from "../api";
import type { DataOverviewPayload, RetentionState } from "../protocol";
import { formatDate } from "../utils/time";
import RetentionSettings from "./RetentionSettings";

/** Counts, not content, and a copy to take away (ADR 0066). */
export default function DataOverview() {
  const [data, setData] = useState<DataOverviewPayload | null>(null);
  const [failed, setFailed] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadFailed, setDownloadFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const payload = await apiFetch<DataOverviewPayload>("/api/me/data");
        if (!cancelled) setData(payload);
      } catch (e) {
        if (cancelled) return;
        console.debug("[data overview] load failed", e);
        setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) {
    return <p className="muted">Die Übersicht konnte nicht geladen werden.</p>;
  }

  if (!data) {
    return <p className="muted">Wird geladen …</p>;
  }

  return (
    <>
      <dl className="profile-facts">
        <dt>Gespeicherte Trainings</dt>
        <dd>{data.sessions}</dd>
        <dt>Gesprächsbeiträge</dt>
        <dd>{data.utterances}</dd>
        <dt>Messwerte</dt>
        <dd>{data.measurements}</dd>
        <dt>Auswertungen</dt>
        <dd>{data.feedbacks}</dd>
        {data.first_session_at && (
          <>
            <dt>Zeitraum</dt>
            <dd>
              {formatDate(data.first_session_at)} bis {formatDate(data.last_session_at) ?? "heute"}
            </dd>
          </>
        )}
      </dl>

      <RetentionSettings
        retention={data.retention}
        onChange={(retention: RetentionState) => setData({ ...data, retention })}
      >
        {data.sessions > 0 && (
          <button
            type="button"
            className="consent-button consent-button-secondary"
            onClick={() => void download(setDownloading, setDownloadFailed)}
            disabled={downloading}
          >
            {downloading ? "Wird vorbereitet …" : "Alle Daten als JSON herunterladen"}
          </button>
        )}
      </RetentionSettings>

      {downloadFailed && (
        <p className="consent-error">
          Der Export konnte nicht erstellt werden. Bitte versuchen Sie es erneut.
        </p>
      )}
    </>
  );
}

/** A blob download: an `<a href>` sends no bearer token. */
async function download(
  setDownloading: (value: boolean) => void,
  setFailed: (value: boolean) => void,
): Promise<void> {
  setDownloading(true);
  setFailed(false);
  let url: string | null = null;
  try {
    const response = await authorizedFetch("/api/me/export");
    const blob = await response.blob();
    url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filenameFrom(response) ?? "calltrainer-export.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
  } catch (e) {
    console.debug("[export] failed", e);
    setFailed(true);
  } finally {
    // It holds a copy of everything the user said.
    if (url) URL.revokeObjectURL(url);
    setDownloading(false);
  }
}

function filenameFrom(response: Response): string | null {
  const disposition = response.headers.get("content-disposition");
  const match = disposition?.match(/filename="([^"]+)"/);
  return match?.[1] ?? null;
}
