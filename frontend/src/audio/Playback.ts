/** Decodes little-endian PCM across arbitrary HTTP/WebSocket chunk boundaries. */
export class Playback {
  private tail: number | null = null;
  private nextTime = 0;
  private sources = new Set<AudioBufferSourceNode>();
  private context: AudioContext;
  private onDrain: () => void;
  constructor(context: AudioContext, onDrain: () => void = () => {}) {
    this.context = context;
    this.onDrain = onDrain;
  }

  get isPlaying() {
    return this.sources.size > 0;
  }

  push(bytes: ArrayBuffer) {
    const incoming = new Uint8Array(bytes);
    const joined = new Uint8Array(
      incoming.length + (this.tail === null ? 0 : 1),
    );
    if (this.tail !== null) joined[0] = this.tail;
    joined.set(incoming, this.tail === null ? 0 : 1);
    this.tail = joined.length % 2 ? joined[joined.length - 1] : null;
    const count = Math.floor(joined.length / 2);
    if (!count) return;
    const buffer = this.context.createBuffer(1, count, 24000);
    const data = buffer.getChannelData(0);
    const view = new DataView(joined.buffer);
    for (let i = 0; i < count; i++)
      data[i] = view.getInt16(i * 2, true) / 32768;
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.context.destination);
    this.sources.add(source);
    source.onended = () => {
      this.sources.delete(source);
      source.disconnect();
      if (!this.sources.size) this.onDrain();
    };
    this.nextTime = Math.max(this.nextTime, this.context.currentTime + 0.02);
    source.start(this.nextTime);
    this.nextTime += buffer.duration;
  }

  stop() {
    for (const source of this.sources) {
      source.onended = null;
      try {
        source.stop();
      } catch {
        /* Already ended. */
      }
      source.disconnect();
    }
    this.sources.clear();
    this.tail = null;
    this.nextTime = 0;
  }
}
