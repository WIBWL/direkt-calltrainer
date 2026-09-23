/** Converts browser microphone errors into stable German user-facing messages.
 * Browser-provided error text is intentionally not exposed because it differs
 * between browsers and may not match the application's language.
 *
 * One function for both places the microphone is opened — the microphone check
 * and the call itself — so the same refusal reads the same on both screens.
 * `fallback` covers what is not a microphone error at all: during the call the
 * voice detection's model can fail to load, which says nothing about the
 * device and must not be reported as though it did. */
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
