import { encodeWav, MAX_SECONDS, SAMPLE_RATE, totalSamples } from "./wav";

/** Plain-words explanation of why the microphone could not be opened. */
export function micErrorMessage(e: unknown): string {
  const name = (e as { name?: string })?.name ?? "";
  if (name === "NotAllowedError" || name === "SecurityError") return "The app is not allowed to use the microphone. Check the privacy settings of your system.";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "No microphone was found. Plug one in and try again.";
  if (name === "NotReadableError" || name === "AbortError") return "The microphone is busy. Another program may be using it.";
  return `The microphone could not be opened (${(e as Error)?.message || name || "unknown problem"}).`;
}

export interface RecorderEvents {
  level: (peak: number) => void;       // 0..1, about every 46 ms
  tick: (seconds: number) => void;     // recorded speech so far
  limit: () => void;                   // 15 minutes reached: the recording was stopped
}

/** Records the microphone as 16 kHz mono 16-bit samples in memory (nothing is written to disk until the parent uses the recording). */
export class Recorder {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: AudioWorkletNode | null = null;
  private chunks: Int16Array[] = [];
  private samples = 0;
  private stopped = false;
  private limited = false;
  constructor(private ev: RecorderEvents) {}

  get seconds() { return this.samples / SAMPLE_RATE; }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: false, noiseSuppression: true, autoGainControl: true } });
    try {
      this.ctx = new AudioContext();
      await this.ctx.audioWorklet.addModule("/recorder-worklet.js");
      await this.ctx.resume();                                     // an AudioContext starts suspended until a user gesture
      this.node = new AudioWorkletNode(this.ctx, "downsampler", { numberOfInputs: 1, numberOfOutputs: 0, channelCount: 1, channelCountMode: "explicit" });
      this.node.port.onmessage = (e: MessageEvent) => {
        if (this.stopped) return;
        if (e.data.pcm) {
          this.chunks.push(e.data.pcm); this.samples += e.data.pcm.length; this.ev.tick(this.seconds);
          if (this.seconds >= MAX_SECONDS && !this.limited) { this.limited = true; this.ev.limit(); }   // once only
        } else if ("level" in e.data) this.ev.level(e.data.level);
      };
      this.ctx.createMediaStreamSource(this.stream).connect(this.node);
    } catch (e) { this.release(); throw e; }
  }
  pause() { this.node?.port.postMessage("pause"); }
  resume() { this.node?.port.postMessage("resume"); }

  /** Stops, releases the microphone and returns the recording as WAV bytes (null when nothing was recorded). */
  async finish(): Promise<{ wav: Uint8Array; seconds: number } | null> {
    this.node?.port.postMessage("flush");
    await new Promise((r) => setTimeout(r, 120));                  // let the last chunk arrive
    this.stopped = true;
    this.release();
    if (totalSamples(this.chunks) === 0) return null;
    return { wav: encodeWav(this.chunks), seconds: this.seconds };
  }
  discard() { this.stopped = true; this.release(); this.chunks = []; this.samples = 0; }
  private release() {
    this.stream?.getTracks().forEach((t) => t.stop());              // the microphone light goes off
    this.node?.disconnect();
    void this.ctx?.close();
    this.stream = null; this.node = null; this.ctx = null;
  }
}
