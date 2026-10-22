/** Mono 16-bit PCM WAV, the format the speech stage reads. Pure functions with no browser or Svelte imports, so `node --test` can check them. */
export const SAMPLE_RATE = 16000;
export const MAX_SECONDS = 15 * 60;

export function totalSamples(chunks: Int16Array[]): number {
  let n = 0;
  for (const c of chunks) n += c.length;
  return n;
}

/** The RIFF/WAVE bytes for the given chunks of 16-bit mono samples. */
export function encodeWav(chunks: Int16Array[], sampleRate = SAMPLE_RATE): Uint8Array {
  const n = totalSamples(chunks);
  const out = new Uint8Array(44 + n * 2);
  const v = new DataView(out.buffer);
  const tag = (o: number, s: string) => { for (let i = 0; i < s.length; i++) out[o + i] = s.charCodeAt(i); };
  tag(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); tag(8, "WAVE");
  tag(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, sampleRate, true); v.setUint32(28, sampleRate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  tag(36, "data"); v.setUint32(40, n * 2, true);
  let o = 44;
  for (const c of chunks) for (let i = 0; i < c.length; i++, o += 2) v.setInt16(o, c[i], true);
  return out;
}

/** Float samples in -1..1 to 16-bit, clipping instead of wrapping around. */
export function floatToInt16(x: Float32Array): Int16Array {
  const y = new Int16Array(x.length);
  for (let i = 0; i < x.length; i++) {
    const s = Math.max(-1, Math.min(1, x[i]));
    y[i] = s < 0 ? Math.round(s * 32768) : Math.round(s * 32767);
  }
  return y;
}

export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
