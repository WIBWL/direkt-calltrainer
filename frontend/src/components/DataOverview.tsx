import { useEffect, useState } from "react";

import { apiFetch } from "../api";
import { currentAccessToken } from "../auth";
import type { DataOverviewPayload, RetentionState } from "../protocol";
import { formatDate } from "../utils/time";
import RetentionSettings from "./RetentionSettings";

/**
 * How much is stored about the caller, and a copy of it to take away
 * (ADR 0066).
 *
 * Counts rather than content: the point is to make the *extent* of what is
 * held visible at a glance, which the history below already fails to do — a
 * list of twenty rows does not tell you it holds four hundred utterances.
 */
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

/**
 * Fetch the export and hand it to the browser as a file.
 *
 * Not a plain link: the route needs the bearer token, and an `<a href>` sends
 * no Authorization header. So it is fetched, turned into a blob and clicked
 * programmatically — which also keeps a page of transcripts out of a browser
 * tab that the next person at the machine could page back to.
 */
async function download(
  setDownloading: (value: boolean) => void,
  setFailed: (value: boolean) => void,
): Promise<void> {
  setDownloading(true);
  setFailed(false);
  let url: string | null = null;
  try {
    const token = await currentAccessToken();
    if (!token) throw new Error("no active session");

    const response = await fetch("/api/me/export", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error(`export failed: ${response.status}`);

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
    // Revoked either way: an object URL holds the whole document in memory
    // until it is released, and this one is a copy of everything the user ever
    // said.
    if (url) URL.revokeObjectURL(url);
    setDownloading(false);
  }
}

/** The server's suggested filename, if it sent one. */
function filenameFrom(response: Response): string | null {
  const disposition = response.headers.get("content-disposition");
  const match = disposition?.match(/filename="([^"]+)"/);
  return match?.[1] ?? null;
}
