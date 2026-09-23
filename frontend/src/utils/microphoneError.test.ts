import { describe, expect, it } from "vitest";

import { microphoneErrorMessage } from "./microphoneError";

describe("microphoneErrorMessage", () => {
  it("names a refused permission as blocked, however the browser phrased it", () => {
    const refused = new DOMException("Permission denied by system", "NotAllowedError");
    expect(microphoneErrorMessage(refused)).toBe("Der Mikrofonzugriff wurde blockiert.");
  });

  it("never passes the browser's own text through", () => {
    const odd = new DOMException("Some English browser text", "UnknownError");
    expect(microphoneErrorMessage(odd)).toBe("Das Mikrofon konnte nicht geöffnet werden.");
  });

  it("uses the caller's fallback for what is not a microphone error", () => {
    const modelLoad = new Error("failed to fetch silero_vad.onnx");
    expect(microphoneErrorMessage(modelLoad, "Anders.")).toBe("Anders.");
  });

  it("still names a device error when a fallback is given", () => {
    const gone = new DOMException("", "NotFoundError");
    expect(microphoneErrorMessage(gone, "Anders.")).toBe(
      "Es wurde kein verfügbares Mikrofon gefunden.",
    );
  });
});
