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
  // Tracked so reset() can actually silence whatever's still playing when a
  // call ends — without this, audio already scheduled (e.g. the Persona's
  // closing line) would keep playing out through the speakers even after
  // the app has moved on to the transcript screen.
  const activeSourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());

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
      pendingCountRef.current += 1;
      setIsPlaying(true);
      // Chained so chunks are decoded+scheduled in arrival order even though
      // decodeAudioData is async and could otherwise resolve out of order.
      scheduleChainRef.current = scheduleChainRef.current.then(async () => {
        const ctx = getContext();
        try {
          const audioBuffer = await ctx.decodeAudioData(data.slice(0));
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

  const stopActiveSources = useCallback(() => {
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
    setIsPlaying(false);
  }, []);

  const reset = useCallback(() => {
    stopActiveSources();
    heldRef.current = true;
    heldChunksRef.current = [];
  }, [stopActiveSources]);

  /** Like reset(), but for a mid-call barge-in: stays live (not held) so
   * the next Turn's chunks play immediately instead of buffering forever. */
  const interrupt = useCallback(() => {
    stopActiveSources();
    heldChunksRef.current = [];
  }, [stopActiveSources]);

  useEffect(() => {
    return () => {
      audioContextRef.current?.close();
    };
  }, []);

  return { enqueue, activate, reset, interrupt, isPlaying };
}
