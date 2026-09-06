/**
 * pcm-processor.js — AudioWorklet for capturing 16kHz mono PCM from the microphone.
 *
 * The AudioContext is created at 24kHz (for TTS playback), but the MediaStream
 * constraint requests 16kHz. The browser may or may not honour the constraint.
 * To be safe, this worklet downsamples from whatever the context rate is to 16kHz
 * using a simple decimation approach before converting float32 → int16 and posting
 * the buffer to the main thread.
 */

const TARGET_SAMPLE_RATE = 16000;
const CHUNK_SIZE = 2048; // samples at target rate per message (~128ms @ 16kHz)

class PcmProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this._buffer = [];
        this._ratio = 1; // will be set on first process() call
        this._accumulated = 0;
    }

    process(inputs) {
        const input = inputs[0];
        if (!input || !input[0]) return true;

        const channelData = input[0]; // Float32Array, length = 128 samples per render quantum

        // Compute decimation ratio on first call (currentTime is 0 before first call)
        if (this._ratio === 1 && sampleRate !== TARGET_SAMPLE_RATE) {
            this._ratio = sampleRate / TARGET_SAMPLE_RATE;
        }

        // Simple decimation: pick every N-th sample
        const step = this._ratio;
        for (let i = 0; i < channelData.length; i += step) {
            this._buffer.push(channelData[Math.floor(i)]);

            if (this._buffer.length >= CHUNK_SIZE) {
                const int16 = new Int16Array(CHUNK_SIZE);
                for (let j = 0; j < CHUNK_SIZE; j++) {
                    // Clamp and convert float32 [-1, 1] → int16 [-32768, 32767]
                    const s = Math.max(-1, Math.min(1, this._buffer[j]));
                    int16[j] = s < 0 ? s * 32768 : s * 32767;
                }
                // Transfer ownership for zero-copy
                this.port.postMessage(int16.buffer, [int16.buffer]);
                this._buffer = [];
            }
        }

        return true; // Keep processor alive
    }
}

registerProcessor('pcm-processor', PcmProcessor);
