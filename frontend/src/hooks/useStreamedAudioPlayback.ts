import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Plays back incoming TTS audio chunks back-to-back, gapless, as they arrive.
 * Each chunk is a small, complete WAV file (not a continuously-appended
 * stream), so scheduled AudioBufferSourceNodes are enough — no need for
 * MediaSource Extensions (see ADR 0026).
 *
 * Starts "held": chunks arriving before `activate()` is called are buffered,
 * not played — the opening Turn is generated in the background while the
 * user is still on the mic-check screen (see CallFlow), and should only
 * start playing once the call screen actually appears. `activate()` flushes
 * whatever's buffered and switches to playing chunks live from then on.
 */
export function useStreamedAudioPlayback() {
  const [isPlaying, setIsPlaying] = useState(false);
  const audioContextRef = useRef<AudioContext | null>(null);
  const nextStartTimeRef = useRef(0);
  const pendingCountRef = useRef(0);
  const scheduleChainRef = useRef<Promise<void>>(Promise.resolve());
  const heldRef = useRef(true);
  const heldChunksRef = useRef<ArrayBuffer[]>([]);
  const activeSourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  // Bumped by stopAll() to invalidate chunks already sitting in
  // scheduleChainRef's promise chain (decodeAudioData is async, so a chunk
  // enqueued just before an interrupt can still resolve afterwards — a plain
  // reassignment of scheduleChainRef.current wouldn't stop an already-chained
  // .then() callback from running). Each scheduled chunk captures the epoch
  // it was enqueued under and checks it's still current before playing.
  const epochRef = useRef(0);

  const getContext = useCallback(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext();
    }
    return audioContextRef.current;
  }, []);

  const finishPending = useCallback(() => {
    pendingCountRef.current -= 1;
    if (pendingCountRef.current === 0) setIsPlaying(false);
  }, []);

  const scheduleChunk = useCallback(
    (data: ArrayBuffer) => {
      const epoch = epochRef.current;
      pendingCountRef.current += 1;
      setIsPlaying(true);
      // Chained so chunks are decoded+scheduled in arrival order even though
      // decodeAudioData is async and could otherwise resolve out of order.
      scheduleChainRef.current = scheduleChainRef.current.then(async () => {
        if (epoch !== epochRef.current) {
          finishPending();
          return;
        }
        const ctx = getContext();
        try {
          const audioBuffer = await ctx.decodeAudioData(data.slice(0));
          if (epoch !== epochRef.current) {
            finishPending();
            return;
          }
          const source = ctx.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(ctx.destination);
          const startAt = Math.max(ctx.currentTime, nextStartTimeRef.current);
          source.start(startAt);
          nextStartTimeRef.current = startAt + audioBuffer.duration;
          activeSourcesRef.current.add(source);
          source.onended = () => {
            activeSourcesRef.current.delete(source);
            finishPending();
          };
        } catch (e) {
          console.error("Failed to decode/play an audio chunk", e);
          finishPending();
        }
      });
    },
    [getContext, finishPending],
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

  /** Immediately silences whatever's currently playing or queued — used both
   * for barge-in (user starts talking over the Persona) and to make sure
   * nothing keeps playing after the call has ended. */
  const stopAll = useCallback(() => {
    epochRef.current += 1;
    for (const source of activeSourcesRef.current) {
      source.onended = null; // avoid a double pendingCount decrement below
      try {
        source.stop();
      } catch {
        // already stopped/ended — nothing to do
      }
    }
    activeSourcesRef.current.clear();
    scheduleChainRef.current = Promise.resolve();
    nextStartTimeRef.current = 0;
    pendingCountRef.current = 0;
    heldChunksRef.current = [];
    setIsPlaying(false);
  }, []);

  const reset = useCallback(() => {
    stopAll();
    heldRef.current = true;
  }, [stopAll]);

  useEffect(() => {
    return () => {
      audioContextRef.current?.close();
    };
  }, []);

  return { enqueue, activate, reset, stopAll, isPlaying };
}
