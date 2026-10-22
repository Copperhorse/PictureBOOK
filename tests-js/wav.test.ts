// Run with: node --test tests-js/
import assert from "node:assert/strict";
import { test } from "node:test";
import { encodeWav, floatToInt16, formatDuration, totalSamples } from "../src/lib/wav.ts";

test("the header describes mono 16-bit PCM at the given rate and the right byte counts", () => {
  const w = encodeWav([Int16Array.from([1, -2, 3]), Int16Array.from([4])], 16000);
  const v = new DataView(w.buffer);
  const text = (o: number, n: number) => String.fromCharCode(...w.slice(o, o + n));
  assert.equal(w.length, 44 + 4 * 2);
  assert.deepEqual([text(0, 4), text(8, 4), text(12, 4), text(36, 4)], ["RIFF", "WAVE", "fmt ", "data"]);
  assert.equal(v.getUint32(4, true), 36 + 8);
  assert.deepEqual([v.getUint16(20, true), v.getUint16(22, true), v.getUint32(24, true), v.getUint32(28, true), v.getUint16(32, true), v.getUint16(34, true)], [1, 1, 16000, 32000, 2, 16]);
  assert.equal(v.getUint32(40, true), 8);
  assert.deepEqual([...new Int16Array(w.buffer, 44, 4)], [1, -2, 3, 4]);
});

test("an empty recording is a valid empty WAV", () => {
  const w = encodeWav([]);
  assert.equal(w.length, 44);
  assert.equal(new DataView(w.buffer).getUint32(40, true), 0);
  assert.equal(totalSamples([]), 0);
});

test("samples are clipped, never wrapped", () => {
  assert.deepEqual([...floatToInt16(Float32Array.from([0, 1, -1, 2, -3, 0.5, -0.5]))], [0, 32767, -32768, 32767, -32768, 16384, -16384]);
});

test("a long recording encodes with the exact size (15 minutes at 16 kHz)", () => {
  const n = 16000 * 900, chunk = new Int16Array(16000);
  const chunks = Array.from({ length: 900 }, () => chunk);
  assert.equal(totalSamples(chunks), n);
  assert.equal(encodeWav(chunks).length, 44 + n * 2);
});

test("durations read as minutes and seconds", () => {
  assert.deepEqual([0, 5, 59, 60, 61, 725, -3].map(formatDuration), ["0:00", "0:05", "0:59", "1:00", "1:01", "12:05", "0:00"]);
});
