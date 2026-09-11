import { useEffect } from "react";

/**
 * The ringtone on the incoming-call screen (F-63).
 *
 * Synthesised rather than played from a file: a recorded ringtone is someone
 * else's, and the one this needs is two soft notes — cheaper to make than to
 * license, and it can be kept genuinely quiet, which a normalised sample
 * cannot.
 *
 * It is deliberately not a telephone bell. A real ring is an alarm; it is
 * built to be heard through a wall and it makes people tense before a call
 * they are already nervous about. This is a bell-like two-note motif — a
 * rising fourth, sine tones with one quiet harmonic, a fast attack and a long
 * decay — at a level you could talk over.
 *
 * The phone on screen shakes and pulses on the same cycle, which it takes
 * from `RINGTONE_CYCLE_MS` below: the two bursts of vibration are the two bars
 * of the figure, and the still half is its silence. A phone buzzing out of
 * time with its own ringtone is worse than one that does not buzz at all.
 */

/** One note: when it is struck inside the cycle, and at what pitch. */
interface Strike {
  at: number;
  freq: number;
}

interface Ringtone {
  /** Seconds from one repeat to the next, the silence at the end included. */
  cycle: number;
  /** How long a struck note takes to fade to nothing. */
  decay: number;
  /** The peak of a single note — not of their sum. Quiet on purpose. */
  peak: number;
  /** Harmonics as [multiple of the fundamental, share of the peak]. What a
   * timbre is made of: an octave gives body, a fourth and a tenth are what
   * make a struck bar sound wooden rather than electronic. */
  partials: readonly (readonly [number, number])[];
  strikes: readonly Strike[];
}

/** The pattern in use. Swapping the ringtone is this constant and nothing
 * else — the scheduling below does not care how long it is or how many notes
 * it has.
 *
 * A marimba figure: two bars of six, a fourth of the cycle sounding and the
 * rest silence. The partials are what make it wooden rather than electronic —
 * a struck bar is tuned so that its fourth and tenth harmonics ring with the
 * fundamental, which is why this reads as a mallet and a bell does not. */
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

/** How long one turn of it takes, in milliseconds. Exported because the phone
 * on screen shakes and its rings expand on the same beat: two places that must
 * agree, kept as one number. */
export const RINGTONE_CYCLE_MS = RINGTONE.cycle * 1000;

/** One struck note under a bell envelope. Nothing is left connected — each
 * note builds its own nodes and stops them, so a screen left open overnight
 * accumulates nothing. */
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

/**
 * Rings for as long as `enabled` stays true, and stops the moment it does not.
 *
 * Silence is the safe failure: a browser that refuses the AudioContext, or one
 * that never resumes it, leaves the screen working and quiet rather than
 * throwing on the way into a call.
 */
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
    // Reaching this screen took a click, so the context is normally allowed to
    // start — but a refusal is not an error worth surfacing.
    void ctx.resume().catch(() => undefined);

    // Each cycle is scheduled a beat ahead and against the audio clock, so the
    // notes of one ring stay together even when the main thread does not.
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
