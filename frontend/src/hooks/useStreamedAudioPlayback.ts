import { useCallback, useEffect, useRef, useState } from "react";

import { useAudioLevelMeter } from "./useAudioLevelMeter";

/** Speech RMS is small; this scales it into a range the call wave can show. */
const METER_GAIN = 5;

/** One scheduled chunk, with what it takes to tell how much of it was heard. */
interface ScheduledChunk {
  startAt: number;
  duration: number;
}

/**
 * Plays back incoming TTS audio chunks back-to-back, gapless, as they arrive.
 * Each chunk is a small, complete WAV file (not a continuously-appended
 * stream), so scheduled AudioBufferSourceNodes are enough — no need for
 * MediaSource Extensions (see ADR 0033).
 *
 * Starts "held": chunks arriving before `activate()` is called are buffered,
 * not played — the opening Turn is generated in the background while the
 * user is still on the mic-check screen (see CallFlow), and should only
 * start playing once the call screen actually appears. `activate()` flushes
 * whatever's buffered and switches to playing chunks live from then on.
 *
 * `audioLevel` is the amplitude of what is coming out of the speakers right
 * now, so the call wave can follow real speech instead of animating blindly.
 */
export function useStreamedAudioPlayback() {
  const [isPlaying, setIsPlaying] = useState(false);
  const { level: audioLevel, start: startMeter, stop: stopMeter } = useAudioLevelMeter(METER_GAIN);

  // Created on demand, and together: every chunk is routed through the
  // analyser on its way to the speakers, which leaves the audio unchanged
  // while exposing its waveform to the meter.
  const audioRef = useRef<{
    ctx: AudioContext;
    analyser: AnalyserNode;
    // A master gain the whole graph passes through, so a barge-in can cut all
    // output in one move regardless of what each individual source does — see
    // stopActiveSources: `AudioBufferSourceNode.stop()` does not reliably
    // cancel a source scheduled to start in the future (Firefox throws, and
    // the server streams whole sentences ahead), which left the rest of the
    // interrupted reply playing out loud.
    gain: GainNode;
  } | null>(null);
  const nextStartTimeRef = useRef(0);
  const pendingCountRef = useRef(0);
  const scheduleChainRef = useRef<Promise<void>>(Promise.resolve());
  const heldRef = useRef(true);
  const heldChunksRef = useRef<ArrayBuffer[]>([]);
  // Tracked so reset()/interrupt() can silence whatever's still playing —
  // without this, audio already scheduled (e.g. the Persona's closing line, or
  // sentences streamed ahead of a barge-in) would keep playing out through the
  // speakers. Each source carries its own scheduled start and length so a
  // barge-in can tell how much of the current chunk was actually heard.
  const activeSourcesRef = useRef<Map<AudioBufferSourceNode, ScheduledChunk>>(new Map());
  // Bumped by every stopActiveSources() (interrupt/reset). A chunk carries the
  // epoch it was queued under into the async decode chain; a decode that
  // resolves after the epoch moved on belongs to a reply the user already cut
  // off, and must not be scheduled — reassigning scheduleChainRef alone does
  // not unhook the .then() callbacks already chained behind an in-flight decode
  // (they would otherwise start() straight away, playing the rest of the
  // interrupted reply out loud).
  const epochRef = useRef(0);
  // Milliseconds of the *current* persona reply that have actually played.
  // Reset when a fresh reply's first chunk arrives (below) and read by
  // interrupt() so the server only commits what the user heard (ADR 0035).
  const playedMsRef = useRef(0);

  const getAudio = useCallback(() => {
    if (!audioRef.current) {
      const ctx = new AudioContext();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.75;
      const gain = ctx.createGain();
      // source(s) -> analyser -> gain -> speakers
      analyser.connect(gain);
      gain.connect(ctx.destination);
      audioRef.current = { ctx, analyser, gain };
    }

    return audioRef.current;
  }, []);

  /** Cut / restore all output at the master gain. Used around a barge-in so
   * nothing the server streamed ahead keeps playing even if its source node
   * ignores stop(). */
  const setMasterMuted = useCallback((muted: boolean) => {
    const audio = audioRef.current;
    if (!audio) return;
    const t = audio.ctx.currentTime;
    audio.gain.gain.cancelScheduledValues(t);
    audio.gain.gain.setValueAtTime(muted ? 0 : 1, t);
  }, []);

  const finishPending = useCallback(() => {
    pendingCountRef.current -= 1;

    if (pendingCountRef.current === 0) {
      setIsPlaying(false);
      stopMeter();
    }
  }, [stopMeter]);

  const scheduleChunk = useCallback(
    (data: ArrayBuffer) => {
      const epoch = epochRef.current;
      // Nothing pending or playing means this is the first chunk of a new
      // persona reply — start its played-time tally from zero. (A long enough
      // mid-reply TTS stall could also land here; the tally then under-counts,
      // which only makes the server commit *less* on a barge-in — the safe way
      // to be wrong.)
      if (pendingCountRef.current === 0 && activeSourcesRef.current.size === 0) {
        playedMsRef.current = 0;
      }
      pendingCountRef.current += 1;
      setIsPlaying(true);
      // Chained so chunks are decoded+scheduled in arrival order even though
      // decodeAudioData is async and could otherwise resolve out of order.
      scheduleChainRef.current = scheduleChainRef.current.then(async () => {
        // Interrupted or reset while this chunk sat in the chain — drop it.
        if (epoch !== epochRef.current) return;
        const { ctx, analyser } = getAudio();
        try {
          const audioBuffer = await ctx.decodeAudioData(data.slice(0));
          if (epoch !== epochRef.current) return; // ... or during its decode
          const source = ctx.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(analyser);
          startMeter(analyser);
          // This chunk belongs to the live reply — lift the barge-in mute.
          setMasterMuted(false);

          const startAt = Math.max(ctx.currentTime, nextStartTimeRef.current);
          source.start(startAt);
          nextStartTimeRef.current = startAt + audioBuffer.duration;
          activeSourcesRef.current.set(source, { startAt, duration: audioBuffer.duration });
          source.onended = () => {
            // Played to its end: the whole chunk counts as heard.
            activeSourcesRef.current.delete(source);
            playedMsRef.current += audioBuffer.duration * 1000;
            finishPending();
          };
        } catch (e) {
          if (epoch !== epochRef.current) return; // dropped, not a real failure
          console.error("Failed to decode/play an audio chunk", e);
          finishPending();
        }
      });
    },
    [getAudio, finishPending, startMeter, setMasterMuted],
  );

  const enqueue = useCallback(
    (data: ArrayBuffer) => {
      if (heldRef.current) {
        heldChunksRef.current.push(data);
        return;
      }
      scheduleChunk(data);
    },
    [scheduleChunk],
  );

  const activate = useCallback(() => {
    if (!heldRef.current) return;
    heldRef.current = false;
    const held = heldChunksRef.current;
    heldChunksRef.current = [];
    for (const data of held) scheduleChunk(data);
  }, [scheduleChunk]);

  const stopActiveSources = useCallback(() => {
    epochRef.current += 1; // in-flight decodes from before this point are stale
    // Master mute first: whatever the per-source stop()s below do or don't do,
    // nothing reaches the speakers from this instant.
    setMasterMuted(true);
    const now = audioRef.current?.ctx.currentTime ?? 0;
    for (const [source, { startAt, duration }] of activeSourcesRef.current) {
      source.onended = null; // avoid a double pendingCount decrement below
      // Count only the part of this chunk that had actually played by now;
      // a chunk still scheduled in the future (startAt > now) contributes 0.
      playedMsRef.current += Math.min(duration, Math.max(0, now - startAt)) * 1000;
      // disconnect() is the reliable one — stop() on a not-yet-started source
      // throws on Firefox and is ignored by some engines, which is what let a
      // streamed-ahead reply keep playing after a barge-in.
      try {
        source.disconnect();
      } catch {
        /* already disconnected */
      }
      try {
        source.stop();
      } catch {
        /* not started / already stopped */
      }
    }
    activeSourcesRef.current.clear();
    scheduleChainRef.current = Promise.resolve();
    nextStartTimeRef.current = 0;
    pendingCountRef.current = 0;
    setIsPlaying(false);
    stopMeter();
  }, [stopMeter, setMasterMuted]);

  const reset = useCallback(() => {
    stopActiveSources();
    playedMsRef.current = 0;
    heldRef.current = true;
    heldChunksRef.current = [];
  }, [stopActiveSources]);

  /** Like reset(), but for a mid-call barge-in: stays live (not held) so
   * the next Turn's chunks play immediately instead of buffering forever.
   * Returns how many ms of the interrupted reply actually played, for the
   * server to bound what it commits to history (ADR 0035). */
  const interrupt = useCallback((): number => {
    stopActiveSources();
    heldChunksRef.current = [];
    const played = Math.round(playedMsRef.current);
    playedMsRef.current = 0;
    return played;
  }, [stopActiveSources]);

  // The meter stops itself on unmount; the context it was reading has to be
  // closed here or it outlives the call.
  useEffect(() => () => void audioRef.current?.ctx.close(), []);

  return { enqueue, activate, reset, interrupt, isPlaying, audioLevel };
}
