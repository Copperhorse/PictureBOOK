// Runs in the audio thread. Takes the microphone's samples (the device rate, usually 44.1 or 48 kHz), averages them down to 16 kHz mono
// 16-bit (an exact area average, which also acts as the low-pass filter) and posts small chunks plus a loudness value to the page.
// Messages in: "pause", "resume", "flush". Messages out: {pcm: Int16Array} about every 0.25 s of speech, {level: 0..1} about every 46 ms.
const TARGET = 16000;
class Downsampler extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / TARGET;     // input samples per output sample (may be fractional)
    this.acc = 0; this.accW = 0;
    this.out = new Int16Array(4000); this.n = 0;
    this.peak = 0; this.blocks = 0; this.active = true;
    this.port.onmessage = (e) => {
      if (e.data === "pause") this.active = false;
      else if (e.data === "resume") this.active = true;
      else if (e.data === "flush") this.send();
    };
  }
  send() {
    if (this.n === 0) return;
    const pcm = this.out.slice(0, this.n);
    this.n = 0;
    this.port.postMessage({ pcm }, [pcm.buffer]);
  }
  emit(v) {
    const s = v < -1 ? -1 : v > 1 ? 1 : v;
    this.out[this.n++] = s < 0 ? Math.round(s * 32768) : Math.round(s * 32767);
    if (this.n === this.out.length) this.send();
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      const x = ch[i], a = x < 0 ? -x : x;
      if (a > this.peak) this.peak = a;
      if (!this.active) continue;
      const need = this.ratio - this.accW;
      if (need >= 1) { this.acc += x; this.accW += 1; }
      else { this.acc += x * need; this.emit(this.acc / this.ratio); const rest = 1 - need; this.acc = x * rest; this.accW = rest; }
    }
    if (++this.blocks >= 16) { this.port.postMessage({ level: this.peak }); this.peak = 0; this.blocks = 0; }
    return true;
  }
}
registerProcessor("downsampler", Downsampler);
