import { useCallback, useEffect, useState } from "react";

export interface MicDevice {
  deviceId: string;
  /** Empty until microphone permission has been granted at least once
   * (browser privacy behavior) — callers show a generic placeholder for those. */
  label: string;
}

/** Chrome/Edge append the USB vendor:product id to some device labels (e.g.
 * "Mikrofon (0d8c:0014)") — the raw hardware id means nothing to someone
 * picking a device by name, so it is dropped, leaving what Windows itself
 * calls the device. */
function stripHardwareId(label: string): string {
  return label.replace(/\s*\([0-9a-f]{4}:[0-9a-f]{4}\)\s*$/i, "");
}

/**
 * The list of available microphones, kept in sync with plug/unplug events.
 * `enumerateDevices()` lists every device (with ids) even before permission is
 * granted; only the labels are withheld until then.
 */
export function useMicrophoneDevices() {
  const [devices, setDevices] = useState<MicDevice[]>([]);

  const refresh = useCallback(async () => {
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      setDevices(
        all
          .filter((d) => d.kind === "audioinput")
          .map((d) => ({ deviceId: d.deviceId, label: stripHardwareId(d.label) })),
      );
    } catch {
      // Unsupported or blocked -- the picker just falls back to "Standardmikrofon".
    }
  }, []);

  useEffect(() => {
    void refresh();
    navigator.mediaDevices.addEventListener("devicechange", refresh);
    return () => navigator.mediaDevices.removeEventListener("devicechange", refresh);
  }, [refresh]);

  return { devices, refresh };
}
