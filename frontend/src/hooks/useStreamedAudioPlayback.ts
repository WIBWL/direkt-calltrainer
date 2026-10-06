import { useCallback, useEffect, useRef, useState } from "react";

import { useAudioLevelMeter } from "./useAudioLevelMeter";

const METER_GAIN = 5;

interface ScheduledChunk {
  startAt: number;
  duration: number;
}

/** Plays TTS chunks gapless as they arrive (ADR 0033). Starts held: chunks
 * before `activate()` are buffered. */
export function useStreamedAudioPlayback() {
  const [isPlaying, setIsPlaying] = useState(false);
  const { level: audioLevel, start: startMeter, stop: stopMeter } = useAudioLevelMeter(METER_GAIN);

  const audioRef = useRef<{
    ctx: AudioContext;
    analyser: AnalyserNode;
    // Mutes all output at once on a barge-in: `stop()` on a future source is unreliable.
    gain: GainNode;
  } | null>(null);
  const nextStartTimeRef = useRef(0);
  const pendingCountRef = useRef(0);
  const scheduleChainRef = useRef<Promise<void>>(Promise.resolve());
  const heldRef = useRef(true);
  const heldChunksRef = useRef<ArrayBuffer[]>([]);
  // So reset()/interrupt() can silence what is still scheduled, and tell how
  // much of the current chunk was heard.
  const activeSourcesRef = useRef<Map<AudioBufferSourceNode, ScheduledChunk>>(new Map());
  // A decode resolving under an older epoch belongs to a cut-off reply:
  // already-chained .then() callbacks are not unhooked.
  const epochRef = useRef(0);
  // Of the current reply; read by interrupt() (ADR 0035).
  const playedMsRef = useRef(0);

  const getAudio = useCallback(() => {
    if (!audioRef.current) {
      const ctx = new AudioContext();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.75;
      const gain = ctx.createGain();
      analyser.connect(gain);
      gain.connect(ctx.destination);
      audioRef.current = { ctx, analyser, gain };
    }

    return audioRef.current;
  }, []);

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
      // A new reply: start the tally from zero. A long TTS stall can land here
      // too; the under-count only makes the server commit less.
      if (pendingCountRef.current === 0 && activeSourcesRef.current.size === 0) {
        playedMsRef.current = 0;
      }
      pendingCountRef.current += 1;
      setIsPlaying(true);
      // Chained, so decoding keeps arrival order.
      scheduleChainRef.current = scheduleChainRef.current.then(async () => {
        if (epoch !== epochRef.current) return;
        const { ctx, analyser } = getAudio();
        try {
          const audioBuffer = await ctx.decodeAudioData(data.slice(0));
          if (epoch !== epochRef.current) return; // ... or during its decode
          const source = ctx.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(analyser);
          startMeter(analyser);
          setMasterMuted(false);

          const startAt = Math.max(ctx.currentTime, nextStartTimeRef.current);
          source.start(startAt);
          nextStartTimeRef.current = startAt + audioBuffer.duration;
          activeSourcesRef.current.set(source, { startAt, duration: audioBuffer.duration });
          source.onended = () => {
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
    setMasterMuted(true);
    const now = audioRef.current?.ctx.currentTime ?? 0;
    for (const [source, { startAt, duration }] of activeSourcesRef.current) {
      source.onended = null; // avoid a double pendingCount decrement below
      // Only the part that has played; a future chunk counts 0.
      playedMsRef.current += Math.min(duration, Math.max(0, now - startAt)) * 1000;
      // disconnect() is the reliable one: stop() on an unstarted source throws on Firefox.
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

  /** Like reset(), but stays live for the next Turn. Returns the ms played (ADR 0035). */
  const interrupt = useCallback((): number => {
    stopActiveSources();
    heldChunksRef.current = [];
    const played = Math.round(playedMsRef.current);
    playedMsRef.current = 0;
    return played;
  }, [stopActiveSources]);

  useEffect(() => () => void audioRef.current?.ctx.close(), []);

  return { enqueue, activate, reset, interrupt, isPlaying, audioLevel };
}
