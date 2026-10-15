import { Playback } from "./Playback";
import { voiceUrl } from "../config";

export type CallState =
  "idle" | "connecting" | "listening" | "thinking" | "speaking" | "error";
export type VoiceEvent = { type: string; content?: string; message?: string };

export class VoiceSession {
  private active = true;
  private stream?: MediaStream;
  private context?: AudioContext;
  private capture?: MediaStreamAudioSourceNode;
  private worklet?: AudioWorkletNode;
  private socket?: WebSocket;
  private playback?: Playback;
  private timeout?: ReturnType<typeof setTimeout>;
  private ready = false;

  private onState: (state: CallState, error?: string) => void;
  private onEvent: (event: VoiceEvent) => void;
  private closeWhenDrained = false;
  constructor(
    onState: (state: CallState, error?: string) => void,
    onEvent: (event: VoiceEvent) => void,
  ) {
    this.onState = onState;
    this.onEvent = onEvent;
  }

  async start() {
    this.onState("connecting");
    try {
      const url = voiceUrl(import.meta.env.VITE_WS_URL, window.location);
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        throw new Error(
          "Microphone access needs HTTPS and a supported browser.",
        );
      }
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (!this.active) {
        this.stop();
        return;
      }
      this.context = new AudioContext();
      await this.context.resume();
      if (!this.active) return;
      this.playback = new Playback(this.context, () => {
        if (!this.active) return;
        if (this.closeWhenDrained) {
          this.stop();
          this.onState("idle");
        } else this.onState("listening");
      });
      await this.context.audioWorklet.addModule(
        `${import.meta.env.BASE_URL}pcm-processor.js`,
      );
      if (!this.active) return;
      this.capture = this.context.createMediaStreamSource(this.stream);
      this.worklet = new AudioWorkletNode(this.context, "pcm-processor");
      this.capture.connect(this.worklet);
      this.worklet.connect(this.context.destination);
      const ws = new WebSocket(url);
      this.socket = ws;
      ws.binaryType = "arraybuffer";
      this.timeout = setTimeout(
        () =>
          this.fail(
            "The voice service took too long to connect. Please try again.",
          ),
        20000,
      );
      this.worklet.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
        if (
          this.active &&
          this.ready &&
          ws.readyState === WebSocket.OPEN &&
          ws.bufferedAmount < 65536
        )
          ws.send(event.data);
      };
      ws.onmessage = (event: MessageEvent) => {
        if (!this.active) return;
        if (typeof event.data !== "string") {
          this.playback?.push(event.data as ArrayBuffer);
          this.onState("speaking");
          return;
        }
        try {
          const message: VoiceEvent = JSON.parse(event.data);
          if (message.type === "ready") {
            clearTimeout(this.timeout);
            this.ready = true;
            this.onState("listening");
          } else if (message.type === "error") {
            this.fail(
              message.message ||
                "The voice service had a problem. Please try again.",
            );
          } else if (message.type === "close") {
            if (this.playback?.isPlaying) this.closeWhenDrained = true;
            else {
              this.stop();
              this.onState("idle");
            }
          } else {
            if (
              message.type === "user_text" ||
              message.type === "interrupted"
            ) {
              this.playback?.stop();
              this.onState(
                message.type === "user_text" ? "thinking" : "listening",
              );
            }
            if (message.type === "audio_complete" && !this.playback?.isPlaying)
              this.onState("listening");
            this.onEvent(message);
          }
        } catch {
          this.fail("The voice service returned an invalid response.");
        }
      };
      ws.onerror = () =>
        this.fail(
          "Could not reach the voice service. Check your connection and try again.",
        );
      ws.onclose = () => {
        if (this.active)
          this.fail("The call disconnected. You can start a new call.");
      };
    } catch (error) {
      if (!this.active) return;
      const message =
        error instanceof DOMException && error.name === "NotAllowedError"
          ? "Microphone access was denied. Allow it in your browser settings, then try again."
          : error instanceof DOMException && error.name === "NotFoundError"
            ? "No microphone was found. Connect one and try again."
            : error instanceof Error
              ? error.message
              : "Could not start the call.";
      this.fail(message);
    }
  }

  private fail(message: string) {
    if (!this.active) return;
    this.stop();
    this.onState("error", message);
  }

  stop() {
    this.active = false;
    this.ready = false;
    clearTimeout(this.timeout);
    this.stream?.getTracks().forEach((track) => track.stop());
    this.playback?.stop();
    this.capture?.disconnect();
    if (this.worklet) {
      this.worklet.port.onmessage = null;
      this.worklet.disconnect();
    }
    if (this.socket) {
      this.socket.onmessage = this.socket.onerror = this.socket.onclose = null;
      this.socket.close();
    }
    if (this.context && this.context.state !== "closed")
      void this.context.close();
  }
}
