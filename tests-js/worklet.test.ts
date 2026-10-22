// Run with: node --test tests-js/   (loads static/recorder-worklet.js with stubs for the audio-thread globals)
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

function load(rate: number) {
  let Ctor: any;
  const sent: any[] = [];
  class Base { port: any = { postMessage: (m: any) => sent.push(m), onmessage: null }; }
  vm.runInNewContext(readFileSync(new URL("../static/recorder-worklet.js", import.meta.url), "utf8"), { sampleRate: rate, AudioWorkletProcessor: Base, registerProcessor: (_: string, c: any) => (Ctor = c), Math, Int16Array });
  const p = new Ctor();
  const feed = (samples: Float32Array) => { for (let i = 0; i < samples.length; i += 128) p.process([[samples.subarray(i, i + 128)]]); };
  const pcm = () => sent.filter((m) => m.pcm).flatMap((m) => [...m.pcm as Int16Array]);
  return { p, feed, sent, pcm };
}
const sine = (rate: number, hz: number, secs: number, amp = 0.5) => Float32Array.from({ length: Math.round(rate * secs) }, (_, i) => amp * Math.sin((2 * Math.PI * hz * i) / rate));

for (const rate of [48000, 44100, 32000, 16000, 22050]) {
  test(`one second at ${rate} Hz becomes 16000 samples at 16 kHz`, () => {
    const { p, feed, pcm } = load(rate);
    feed(sine(rate, 440, 1)); p.port.onmessage({ data: "flush" });
    assert.ok(Math.abs(pcm().length - 16000) <= 2, `${pcm().length}`);
  });
}

test("a constant level stays the same level and a 1 kHz tone keeps its loudness", () => {
  const dc = load(44100);
  dc.feed(new Float32Array(44100).fill(0.5)); dc.p.port.onmessage({ data: "flush" });
  const v = dc.pcm().slice(10, -10);
  assert.ok(v.every((x) => Math.abs(x - 16383.5) < 2), "DC passes unchanged (up to rounding)");
  const t = load(48000);
  t.feed(sine(48000, 1000, 1)); t.p.port.onmessage({ data: "flush" });
  const peak = Math.max(...t.pcm().map(Math.abs));
  assert.ok(peak > 0.45 * 32767 && peak < 0.52 * 32767, `peak ${peak}`);
});

test("loud input is clipped, not wrapped", () => {
  const { p, feed, pcm } = load(16000);
  feed(new Float32Array(1280).fill(3)); p.port.onmessage({ data: "flush" });
  assert.ok(pcm().every((x) => x === 32767));
  const n = load(16000); n.feed(new Float32Array(1280).fill(-3)); n.p.port.onmessage({ data: "flush" });
  assert.ok(n.pcm().every((x) => x === -32768));
});

test("pause drops samples but still reports the level; resume continues", () => {
  const { p, feed, sent, pcm } = load(16000);
  p.port.onmessage({ data: "pause" });
  feed(sine(16000, 440, 0.5)); p.port.onmessage({ data: "flush" });
  assert.equal(pcm().length, 0);
  assert.ok(sent.some((m) => m.level > 0.4), "the level meter keeps moving while paused");
  p.port.onmessage({ data: "resume" });
  feed(sine(16000, 440, 0.5)); p.port.onmessage({ data: "flush" });
  assert.ok(Math.abs(pcm().length - 8000) <= 2);
});

test("chunks arrive about every quarter second and the level about every 46 ms", () => {
  const { feed, sent } = load(48000);
  feed(sine(48000, 440, 2));
  const chunks = sent.filter((m) => m.pcm), levels = sent.filter((m) => "level" in m);
  assert.ok(chunks.length >= 7 && chunks.every((c) => c.pcm.length === 4000), `${chunks.length} chunks`);
  assert.ok(levels.length > 35 && levels.length < 50, `${levels.length} levels`);
});

test("a block without input is ignored", () => {
  const { p } = load(48000);
  assert.equal(p.process([[]]), true);
  assert.equal(p.process([]), true);
});
