// Run from frontend/: PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs node tests/browser.mjs
// No external providers: browser microphone uses Chrome's fake device and WS messages are mocked.
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import assert from "node:assert/strict";
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || "playwright"
);
const server = spawn("npm", ["run", "dev", "--", "--host", "127.0.0.1"], {
  stdio: "ignore",
  detached: true,
});
let browser;
try {
  for (let i = 0; i < 60; i++) {
    try {
      if ((await fetch("http://127.0.0.1:5173")).ok) break;
    } catch {
      /* Wait for the dev server. */
    }
    await delay(100);
  }
  browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome",
    headless: true,
    args: [
      "--no-sandbox",
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
    ],
  });
  const context = await browser.newContext({
    permissions: ["microphone"],
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.__testStreams = [];
    const original = navigator.mediaDevices.getUserMedia.bind(
      navigator.mediaDevices,
    );
    navigator.mediaDevices.getUserMedia = async (...args) => {
      const stream = await original(...args);
      window.__testStreams.push(stream);
      return stream;
    };
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let currentSocket;
  await page.routeWebSocket("**/ws/voice", (ws) => {
    currentSocket = ws;
    ws.send(JSON.stringify({ type: "ready" }));
  });
  await page.goto("http://127.0.0.1:5173");
  await page.getByRole("heading", { name: /A little clarity/ }).waitFor();
  await page.locator(".companion-art").evaluate((img) => img.decode());
  await page.screenshot({
    path: "/tmp/nephele-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  assert.equal(
    await page.evaluate(
      () => navigator.mediaDevices.getUserMedia === undefined,
    ),
    false,
  );
  await page.getByRole("button", { name: "Start a conversation" }).click();
  await page
    .getByRole("status")
    .filter({ hasText: "Listening to you" })
    .waitFor();
  currentSocket.send(
    JSON.stringify({
      type: "user_text",
      content: "How do I prepare for an interview?",
    }),
  );
  currentSocket.send(
    JSON.stringify({ type: "text", content: "Start with your introduction. " }),
  );
  currentSocket.send(Buffer.from(new Int16Array(2400).buffer));
  currentSocket.send(JSON.stringify({ type: "audio_complete" }));
  await page.getByText("Start with your introduction.").waitFor();
  await page.getByRole("button", { name: "End conversation" }).click();
  await page
    .getByRole("status")
    .filter({ hasText: "Ready when you are" })
    .waitFor();
  assert.equal(
    await page.evaluate(() =>
      window.__testStreams.every((stream) =>
        stream.getTracks().every((track) => track.readyState === "ended"),
      ),
    ),
    true,
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.mouse.move(0, 0);
  await page.waitForFunction(
    () =>
      getComputedStyle(document.querySelector(".call-button"))
        .backgroundColor === "rgb(197, 213, 171)",
  );
  await page.screenshot({
    path: "/tmp/nephele-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
  await page.getByRole("button", { name: "Start a conversation" }).click();
  await page
    .getByRole("status")
    .filter({ hasText: "Listening to you" })
    .waitFor();
  currentSocket.send(
    JSON.stringify({
      type: "error",
      message:
        "Voice service is not configured. Please contact the site owner.",
    }),
  );
  await page.getByRole("alert").waitFor();
  await page.screenshot({
    path: "/tmp/nephele-error.png",
    fullPage: true,
    animations: "disabled",
  });
  assert.equal(
    await page.getByRole("button", { name: "Try again" }).count(),
    1,
  );
  assert.equal(
    await page.evaluate(() =>
      window.__testStreams.every((stream) =>
        stream.getTracks().every((track) => track.readyState === "ended"),
      ),
    ),
    true,
  );
  for (const width of [320, 768]) {
    await page.setViewportSize({ width, height: 900 });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      true,
    );
    await page.screenshot({
      path: `/tmp/nephele-${width}.png`,
      fullPage: true,
      animations: "disabled",
    });
  }
  assert.deepEqual(errors, []);
  console.log(
    "PASS: desktop + mobile layout, mocked microphone/WS call, transcript, PCM playback, end, reconnect, server error; no page errors or horizontal overflow.",
  );
  await context.close();
  const denied = await browser.newContext();
  const deniedPage = await denied.newPage();
  await deniedPage.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => {
      throw new DOMException("denied", "NotAllowedError");
    };
  });
  await deniedPage.goto("http://127.0.0.1:5173");
  await deniedPage
    .getByRole("button", { name: "Start a conversation" })
    .click();
  await deniedPage
    .getByRole("alert")
    .filter({ hasText: "Microphone access was denied" })
    .waitFor();
  console.log("PASS: microphone denied state, retry remains available.");
  await denied.close();
} finally {
  await browser?.close();
  try {
    process.kill(-server.pid, "SIGTERM");
  } catch {
    /* Server already stopped. */
  }
}
