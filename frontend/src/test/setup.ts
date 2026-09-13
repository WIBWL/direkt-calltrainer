/**
 * Test-only fakes for the two browser APIs the live-call audio path is built
 * on: Web Audio (useStreamedAudioPlayback) and WebSocket (useSessionSocket).
 * jsdom ships neither, and the real ones can't be driven frame-by-frame — the
 * barge-in races only show up when decode timing and socket delivery are under
 * the test's control.
 *
 * Both fakes expose a small manual-control surface (resolve this decode now,
 * deliver this frame now) on top of the shape the hooks actually use.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

// --- Web Audio -------------------------------------------------------------

/** A decode call waiting for the test to hand it a buffer, the way the model
 * gateway hands back synthesized audio. */
interface PendingDecode {
  resolve: (buffer: FakeAudioBuffer) => void;
  reject: (err: unknown) => void;
}

export interface FakeAudioBuffer {
  duration: number;
}

class FakeAudioBufferSourceNode {
  buffer: FakeAudioBuffer | null = null;
  onended: (() => void) | null = null;
  startedAt: number | null = null;
  stopped = false;
  disconnected = false;

  connect(): void {}

  disconnect(): void {
    this.disconnected = true;
  }

  start(when = 0): void {
    this.startedAt = when;
  }

  stop(): void {
    this.stopped = true;
  }
}

class FakeGainParam {
  value = 1;
  cancelScheduledValues(): void {}
  setValueAtTime(value: number): void {
    this.value = value;
  }
  setTargetAtTime(value: number): void {
    this.value = value;
  }
}

class FakeGainNode {
  gain = new FakeGainParam();
  connect(): void {}
  disconnect(): void {}
}

class FakeAnalyserNode {
  fftSize = 2048;
  smoothingTimeConstant = 0;
  frequencyBinCount = 1024;
  connect(): void {}
  getByteTimeDomainData(array: Uint8Array): void {
    array.fill(128);
  }
}

export class FakeAudioContext {
  static pendingDecodes: PendingDecode[] = [];
  static createdSources: FakeAudioBufferSourceNode[] = [];
  static gains: FakeGainNode[] = [];

  currentTime = 0;
  destination = {};
  state: "running" | "closed" = "running";

  createAnalyser(): FakeAnalyserNode {
    return new FakeAnalyserNode();
  }

  createGain(): FakeGainNode {
    const gain = new FakeGainNode();
    FakeAudioContext.gains.push(gain);
    return gain;
  }

  createBufferSource(): FakeAudioBufferSourceNode {
    const source = new FakeAudioBufferSourceNode();
    FakeAudioContext.createdSources.push(source);
    return source;
  }

  decodeAudioData(_data: ArrayBuffer): Promise<FakeAudioBuffer> {
    return new Promise<FakeAudioBuffer>((resolve, reject) => {
      FakeAudioContext.pendingDecodes.push({ resolve, reject });
    });
  }

  close(): Promise<void> {
    this.state = "closed";
    return Promise.resolve();
  }
}

/** Resolve decodes as the scheduling chain produces them — each resolved decode
 * lets the chain advance one link and queue the next — and return once the
 * chain has been idle for a few microtask rounds. */
export async function flushDecodes(duration = 1): Promise<void> {
  let idleRounds = 0;
  while (idleRounds < 5) {
    if (FakeAudioContext.pendingDecodes.length > 0) {
      idleRounds = 0;
      FakeAudioContext.pendingDecodes.shift()?.resolve({ duration });
    } else {
      idleRounds += 1;
    }
    await Promise.resolve();
  }
}

/** The playback sources that actually got start()ed and weren't stopped or
 * disconnected again — i.e. audio the user would have heard. */
export function audibleSources(): FakeAudioBufferSourceNode[] {
  return FakeAudioContext.createdSources.filter(
    (s) => s.startedAt !== null && !s.stopped && !s.disconnected,
  );
}

/** True when the master gain is currently cutting all output (barge-in mute). */
export function masterMuted(): boolean {
  return FakeAudioContext.gains.some((g) => g.gain.value === 0);
}

// --- WebSocket -----------------------------------------------------------

type Listener = ((event: any) => void) | null;

export class FakeWebSocket {
  static CONNECTING = 0 as const;
  static OPEN = 1 as const;
  static CLOSING = 2 as const;
  static CLOSED = 3 as const;
  static instances: FakeWebSocket[] = [];

  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSING = 2;
  readonly CLOSED = 3;

  readyState = 0;
  binaryType = "blob";
  onopen: Listener = null;
  onmessage: Listener = null;
  onerror: Listener = null;
  onclose: Listener = null;
  sent: Array<string | ArrayBuffer> = [];

  constructor(readonly url: string) {
    FakeWebSocket.instances.push(this);
  }

  send(data: string | ArrayBuffer): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code: 1000, reason: "", wasClean: true });
  }

  // --- test controls ---

  /** The parsed JSON control messages the client has sent. */
  sentJson(): Array<Record<string, unknown>> {
    return this.sent
      .filter((d): d is string => typeof d === "string")
      .map((d) => JSON.parse(d) as Record<string, unknown>);
  }

  simulateOpen(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.({});
  }

  serverJson(message: Record<string, unknown>): void {
    this.onmessage?.({ data: JSON.stringify(message) });
  }

  serverBinary(buffer: ArrayBuffer = new ArrayBuffer(8)): void {
    this.onmessage?.({ data: buffer });
  }
}

export function latestSocket(): FakeWebSocket {
  // Indexed rather than `.at(-1)`, which is ES2022 and would mean widening
  // `lib` for the production build as well.
  const socket = FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  if (!socket) throw new Error("no FakeWebSocket was constructed");
  return socket;
}

// --- Wiring + per-test reset --------------------------------------------

import { afterEach, beforeEach, vi } from "vitest";

vi.stubGlobal("AudioContext", FakeAudioContext);
vi.stubGlobal("WebSocket", FakeWebSocket);
// The level meter re-arms itself every animation frame; pinned to a no-op so
// the audio specs stay deterministic and don't leak act() warnings.
vi.stubGlobal("requestAnimationFrame", () => 0);
vi.stubGlobal("cancelAnimationFrame", () => {});

// The hooks trace every socket message on console.debug; keep it out of the
// test reporter's output. Real warnings and errors still come through.
vi.spyOn(console, "debug").mockImplementation(() => {});

beforeEach(() => {
  FakeAudioContext.pendingDecodes = [];
  FakeAudioContext.createdSources = [];
  FakeAudioContext.gains = [];
  FakeWebSocket.instances = [];
});

afterEach(() => {
  vi.clearAllMocks();
});
