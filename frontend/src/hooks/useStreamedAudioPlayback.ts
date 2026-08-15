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

  const getContext = useCallback(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext();
    }
    return audioContextRef.current;
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
          source.onended = () => {
            pendingCountRef.current -= 1;
            if (pendingCountRef.current === 0) setIsPlaying(false);
          };
        } catch (e) {
          console.error("Failed to decode/play an audio chunk", e);
          pendingCountRef.current -= 1;
          if (pendingCountRef.current === 0) setIsPlaying(false);
        }
      });
    },
    [getContext],
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

  const reset = useCallback(() => {
    scheduleChainRef.current = Promise.resolve();
    nextStartTimeRef.current = 0;
    pendingCountRef.current = 0;
    heldRef.current = true;
    heldChunksRef.current = [];
    setIsPlaying(false);
  }, []);

  useEffect(() => {
    return () => {
      audioContextRef.current?.close();
    };
  }, []);

  return { enqueue, activate, reset, isPlaying };
}
