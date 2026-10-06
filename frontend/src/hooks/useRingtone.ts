import { useEffect } from "react";

/** The incoming-call ringtone (F-63), synthesised and quiet. The phone animation
 * shares `RINGTONE_CYCLE_MS`. */

interface Strike {
  at: number;
  freq: number;
}

interface Ringtone {
  /** Seconds, the closing silence included. */
  cycle: number;
  decay: number;
  /** Per note, not their sum. */
  peak: number;
  /** [multiple of the fundamental, share of the peak]. */
  partials: readonly (readonly [number, number])[];
  strikes: readonly Strike[];
}

/** A marimba figure; the 4th and 10th partials make it wooden. */
const RINGTONE: Ringtone = {
  cycle: 4.4,
  decay: 0.55,
  peak: 0.05,
  partials: [
    [1, 1],
    [4, 0.45],
    [10, 0.12],
  ],
  strikes: [
    { at: 0, freq: 523.25 },
    { at: 0.16, freq: 783.99 },
    { at: 0.32, freq: 659.25 },
    { at: 0.48, freq: 1046.5 },
    { at: 0.64, freq: 783.99 },
    { at: 0.8, freq: 659.25 },
    { at: 1.1, freq: 587.33 },
    { at: 1.26, freq: 880 },
    { at: 1.42, freq: 698.46 },
    { at: 1.58, freq: 1174.66 },
    { at: 1.74, freq: 880 },
    { at: 1.9, freq: 698.46 },
  ],
};

export const RINGTONE_CYCLE_MS = RINGTONE.cycle * 1000;

/** Each note builds and stops its own nodes, so nothing accumulates. */
function strike(ctx: AudioContext, at: number, freq: number) {
  const { peak, decay, partials } = RINGTONE;
  const envelope = ctx.createGain();
  envelope.gain.setValueAtTime(0.0001, at);
  envelope.gain.exponentialRampToValueAtTime(peak, at + 0.012);
  envelope.gain.exponentialRampToValueAtTime(0.0001, at + decay);
  envelope.connect(ctx.destination);

  for (const [multiple, share] of partials) {
    const osc = ctx.createOscillator();
    osc.type = "sine";
    osc.frequency.value = freq * multiple;
    const level = ctx.createGain();
    level.gain.value = share;
    osc.connect(level).connect(envelope);
    osc.start(at);
    osc.stop(at + decay + 0.05);
  }
}

/** Silence is the safe failure. */
export function useRingtone(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return undefined;

    const Ctor = window.AudioContext ?? (window as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
    if (!Ctor) return undefined;

    let ctx: AudioContext;
    try {
      ctx = new Ctor();
    } catch {
      return undefined; // no audio on this machine; the screen still works
    }
    void ctx.resume().catch(() => undefined);

    // Scheduled a beat ahead on the audio clock, so a busy main thread cannot split a ring.
    const playCycle = () => {
      const at = ctx.currentTime + 0.06;
      for (const note of RINGTONE.strikes) strike(ctx, at + note.at, note.freq);
    };
    playCycle();
    const timer = window.setInterval(playCycle, RINGTONE.cycle * 1000);

    return () => {
      window.clearInterval(timer);
      void ctx.close().catch(() => undefined);
    };
  }, [enabled]);
}
