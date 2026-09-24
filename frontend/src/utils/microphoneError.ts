/** Converts browser microphone errors into stable German messages (browser text
 * differs per browser and language), for the mic check and the call alike.
 * `fallback` is for non-microphone failures, e.g. the VAD model failing to load,
 * which must not be reported as a device problem. */
export function microphoneErrorMessage(
  error: unknown,
  fallback = "Das Mikrofon konnte nicht geöffnet werden.",
): string {
  if (!(error instanceof DOMException)) return fallback;

  switch (error.name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Der Mikrofonzugriff wurde blockiert.";

    case "NotFoundError":
      return "Es wurde kein verfügbares Mikrofon gefunden.";

    case "NotReadableError":
      return "Das Mikrofon kann derzeit nicht verwendet werden. Möglicherweise wird es von einer anderen Anwendung verwendet.";

    case "OverconstrainedError":
      return "Das ausgewählte Mikrofon ist nicht mehr verfügbar.";

    case "AbortError":
      return "Der Mikrofonzugriff wurde unterbrochen. Bitte versuchen Sie es erneut.";

    default:
      return fallback;
  }
}
