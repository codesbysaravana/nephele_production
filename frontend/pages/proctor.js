/**
 * Proctor module — Page Visibility + face-api.js face-presence detection.
 * Sends events over an existing WebSocket connection.
 * DECISION: This is a utility module, not a page. Import and call initProctor(ws).
 */

// ============================================================
// Page Visibility — detect tab/window blur
// ============================================================

let _ws = null;
let _visibilityActive = false;

function _onVisibilityChange() {
  if (!_ws || _ws.readyState !== WebSocket.OPEN) return;

  const eventType = document.hidden ? "tab_blur" : "tab_focus";
  _ws.send(JSON.stringify({ action: "proctor_event", event_type: eventType }));
}

function startVisibilityTracking(ws) {
  _ws = ws;
  if (_visibilityActive) return;
  document.addEventListener("visibilitychange", _onVisibilityChange);
  _visibilityActive = true;
}

function stopVisibilityTracking() {
  document.removeEventListener("visibilitychange", _onVisibilityChange);
  _visibilityActive = false;
}

// ============================================================
// Face Presence — face-api.js (pretrained, client-side only)
// ============================================================

let _faceInterval = null;
let _videoEl = null;
let _lastFaceState = "ok"; // "ok" | "no_face" | "multiple_faces"

// DECISION: face-api.js loaded from CDN. Models loaded from /assets/face-models/.
// Detection runs every 2s — low CPU overhead, sufficient for presence detection.
const FACE_CHECK_INTERVAL_MS = 2000;

async function startFaceDetection(ws, videoElement) {
  _ws = ws;
  _videoEl = videoElement;

  if (typeof faceapi === "undefined") {
    console.warn("[PROCTOR] face-api.js not loaded — skipping face detection");
    return;
  }

  // Load minimal model (TinyFaceDetector is fast and sufficient for presence)
  const MODEL_URL = "/assets/face-models";
  await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL);

  _faceInterval = setInterval(_checkFaces, FACE_CHECK_INTERVAL_MS);
}

async function _checkFaces() {
  if (!_videoEl || !_ws || _ws.readyState !== WebSocket.OPEN) return;
  if (_videoEl.paused || _videoEl.ended) return;

  try {
    const detections = await faceapi.detectAllFaces(
      _videoEl,
      new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.5 })
    );

    let newState = "ok";
    if (detections.length === 0) {
      newState = "no_face";
    } else if (detections.length > 1) {
      newState = "multiple_faces";
    }

    // Only send on state *change* to avoid flooding the server
    if (newState !== _lastFaceState) {
      if (newState === "ok") {
        _sendEvent("face_restored");
      } else {
        _sendEvent(newState);
      }
      _lastFaceState = newState;
    }
  } catch (err) {
    console.error("[PROCTOR] Face detection error:", err);
  }
}

function stopFaceDetection() {
  if (_faceInterval) {
    clearInterval(_faceInterval);
    _faceInterval = null;
  }
}

function _sendEvent(eventType) {
  if (_ws && _ws.readyState === WebSocket.OPEN) {
    _ws.send(JSON.stringify({ action: "proctor_event", event_type: eventType }));
  }
}

// ============================================================
// Public API
// ============================================================

/**
 * Initialize proctoring on an active WebSocket and optional video element.
 * @param {WebSocket} ws - The interview WebSocket connection
 * @param {HTMLVideoElement|null} videoEl - Webcam video element (null skips face detection)
 */
async function initProctor(ws, videoEl = null) {
  startVisibilityTracking(ws);
  if (videoEl) {
    await startFaceDetection(ws, videoEl);
  }
}

function destroyProctor() {
  stopVisibilityTracking();
  stopFaceDetection();
}

// Export for use in other page modules
window.Proctor = { initProctor, destroyProctor };
