/** Web Audio and WebSocket fakes jsdom lacks, with manual decode and delivery controls for the barge-in races. */

// config.ts refuses to load without it.
window.__APP_CONFIG__ = { oidcIssuer: "http://localhost:18081/realms/direkt" };

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

/** Resolves decodes until the scheduling chain is idle. */
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

/** Started and not stopped: what the user would have heard. */
export function audibleSources(): FakeAudioBufferSourceNode[] {
  return FakeAudioContext.createdSources.filter(
    (s) => s.startedAt !== null && !s.stopped && !s.disconnected,
  );
}

export function masterMuted(): boolean {
  return FakeAudioContext.gains.some((g) => g.gain.value === 0);
}

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
  // Not `.at(-1)`, which would widen `lib` for the build too.
  const socket = FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  if (!socket) throw new Error("no FakeWebSocket was constructed");
  return socket;
}

import { afterEach, beforeEach, vi } from "vitest";

vi.stubGlobal("AudioContext", FakeAudioContext);
vi.stubGlobal("WebSocket", FakeWebSocket);
// Deterministic audio specs, no act() warnings.
vi.stubGlobal("requestAnimationFrame", () => 0);
vi.stubGlobal("cancelAnimationFrame", () => {});

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
