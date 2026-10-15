import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

async function moduleFrom(file) {
  const source = readFileSync(new URL(file, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2023,
    },
  });
  return import(
    `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
  );
}
const { voiceUrl } = await moduleFrom("../src/config.ts");
const { Playback } = await moduleFrom("../src/audio/Playback.ts");
const page = { hostname: "nephele.example", protocol: "https:" };

test("production requires an explicit secure backend; local defaults work", () => {
  assert.throws(() => voiceUrl(undefined, page), /not configured/);
  assert.throws(() => voiceUrl("http://backend.example", page), /secure/);
  assert.throws(
    () => voiceUrl("https://name:secret@backend.example", page),
    /invalid/,
  );
  assert.equal(
    voiceUrl("https://backend.example/", page),
    "wss://backend.example/ws/voice",
  );
  assert.equal(
    voiceUrl(undefined, { hostname: "localhost", protocol: "http:" }),
    "ws://localhost:8000/ws/voice",
  );
});

for (const rate of [16000, 24000, 44100, 48000]) {
  test(`PCM capture keeps a stable 16kHz rate from ${rate}Hz across render boundaries`, () => {
    let Processor;
    const chunks = [];
    const context = vm.createContext({
      sampleRate: rate,
      AudioWorkletProcessor: class {
        constructor() {
          this.port = {
            postMessage: (data) => chunks.push(new Int16Array(data)),
          };
        }
      },
      registerProcessor: (_name, value) => {
        Processor = value;
      },
    });
    vm.runInContext(
      readFileSync(
        new URL("../public/pcm-processor.js", import.meta.url),
        "utf8",
      ),
      context,
    );
    const processor = new Processor();
    const count = Math.floor(rate / 128);
    for (let n = 0; n < count; n++)
      processor.process([[new Float32Array(128).fill(0.5)]]);
    const produced =
      chunks.reduce((sum, chunk) => sum + chunk.length, 0) + processor.used;
    assert.ok(Math.abs(produced - (count * 128 * 16000) / rate) <= 2);
    assert.ok(chunks.every((chunk) => chunk.every((value) => value === 16383)));
    assert.ok(processor.pending.length <= 2);
  });
}

test("playback preserves odd chunk boundaries and stops all scheduled audio", () => {
  const sources = [];
  const buffers = [];
  const context = {
    currentTime: 2,
    destination: {},
    createBuffer(_channels, count, rate) {
      const data = new Float32Array(count);
      buffers.push(data);
      return { getChannelData: () => data, duration: count / rate };
    },
    createBufferSource() {
      const source = {
        connect() {},
        disconnect() {},
        start(at) {
          this.at = at;
        },
        stop() {
          this.stopped = true;
        },
      };
      sources.push(source);
      return source;
    },
  };
  const playback = new Playback(context);
  playback.push(new Uint8Array([0, 128, 255]).buffer);
  playback.push(new Uint8Array([127, 0, 0]).buffer);
  assert.deepEqual(Array.from(buffers[0]), [-1]);
  assert.deepEqual(Array.from(buffers[1]), [32767 / 32768, 0]);
  assert.ok(sources[1].at > sources[0].at);
  playback.stop();
  assert.ok(sources.every((source) => source.stopped));
  assert.equal(playback.isPlaying, false);
});
