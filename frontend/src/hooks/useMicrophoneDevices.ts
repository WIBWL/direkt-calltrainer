import { useCallback, useEffect, useState } from "react";

export interface MicDevice {
  deviceId: string;
  /** Empty until permission was granted once. */
  label: string;
}

/** Drops Chrome's "(0d8c:0014)" vendor:product suffix. */
function stripHardwareId(label: string): string {
  return label.replace(/\s*\([0-9a-f]{4}:[0-9a-f]{4}\)\s*$/i, "");
}

/** Kept in sync with plug/unplug events; labels are withheld until permission. */
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
      // Unsupported or blocked -- the picker falls back to the default-device
      // label.
    }
  }, []);

  useEffect(() => {
    void refresh();
    navigator.mediaDevices.addEventListener("devicechange", refresh);
    return () => navigator.mediaDevices.removeEventListener("devicechange", refresh);
  }, [refresh]);

  return { devices, refresh };
}
