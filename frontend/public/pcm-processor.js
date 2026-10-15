/* Linear interpolation with a persistent fractional cursor across render quanta. */
const TARGET_SAMPLE_RATE = 16000;
const CHUNK_SIZE = 1024;
class PcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.pending = [];
    this.position = 0;
    this.chunk = new Int16Array(CHUNK_SIZE);
    this.used = 0;
  }
  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;
    this.pending.push(...input);
    const step = sampleRate / TARGET_SAMPLE_RATE;
    while (this.position + 1 < this.pending.length) {
      const left = Math.floor(this.position);
      const fraction = this.position - left;
      const value = Math.max(
        -1,
        Math.min(
          1,
          this.pending[left] * (1 - fraction) +
            this.pending[left + 1] * fraction,
        ),
      );
      this.chunk[this.used++] = value < 0 ? value * 32768 : value * 32767;
      this.position += step;
      if (this.used === CHUNK_SIZE) {
        this.port.postMessage(this.chunk.buffer, [this.chunk.buffer]);
        this.chunk = new Int16Array(CHUNK_SIZE);
        this.used = 0;
      }
    }
    const consumed = Math.min(
      Math.floor(this.position),
      this.pending.length - 1,
    );
    this.pending.splice(0, consumed);
    this.position -= consumed;
    return true;
  }
}
registerProcessor("pcm-processor", PcmProcessor);
