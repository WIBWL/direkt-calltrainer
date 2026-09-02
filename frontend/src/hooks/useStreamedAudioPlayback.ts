import { useCallback, useEffect, useRef, useState } from "react";

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
 */
export function useStreamedAudioPlayback() {
  const [isPlaying, setIsPlaying] = useState(false);
  const audioContextRef = useRef<AudioContext | null>(null);
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
  const activeSourcesRef = useRef<Map<AudioBufferSourceNode, { startAt: number; duration: number }>>(
    new Map(),
  );
  // Milliseconds of the *current* persona reply that have actually played.
  // Reset when a fresh reply's first chunk arrives (below) and read by
  // interrupt() so the server only commits what the user heard (ADR 0035).
  const playedMsRef = useRef(0);

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
        const ctx = getContext();
        try {
          const audioBuffer = await ctx.decodeAudioData(data.slice(0));
          const source = ctx.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(ctx.destination);
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
    const now = audioContextRef.current?.currentTime ?? 0;
    for (const [source, { startAt, duration }] of activeSourcesRef.current) {
      source.onended = null; // avoid a double pendingCount decrement below
      // Count only the part of this chunk that had actually played by now;
      // a chunk still scheduled in the future (startAt > now) contributes 0.
      playedMsRef.current += Math.min(duration, Math.max(0, now - startAt)) * 1000;
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

  useEffect(() => {
    return () => {
      audioContextRef.current?.close();
    };
  }, []);

  return { enqueue, activate, reset, interrupt, isPlaying };
}
