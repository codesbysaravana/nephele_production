/**
 * Interview page logic — handles resume upload, WebSocket voice session.
 * Called after interview.js DOM renders.
 */

const API_BASE = "https://nephele-dsoa.onrender.com";
const WS_BASE = "wss://nephele-dsoa.onrender.com";

let ws = null;
let mediaStream = null;
let mediaRecorder = null;
let selectedFile = null;
const USER_ID = "user_" + Math.random().toString(36).slice(2, 10);

export function initInterviewPage() {
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("fileInput");
    const uploadBtn = document.getElementById("uploadBtn");
    const startBtn = document.getElementById("startInterviewBtn");
    const endBtn = document.getElementById("endBtn");

    // --- Drag & Drop ---
    dropZone.addEventListener("click", () => fileInput.click());
    dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("dragover"); });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
    dropZone.addEventListener("drop", (e) => {
        e.preventDefault(); dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length) _handleFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener("change", () => { if (fileInput.files[0]) _handleFile(fileInput.files[0]); });

    // --- Upload ---
    uploadBtn.addEventListener("click", _uploadResume);

    // --- Start Interview ---
    startBtn.addEventListener("click", _startVoiceInterview);
    endBtn.addEventListener("click", _endInterview);
}

function _handleFile(file) {
    const valid = ["application/pdf", "text/plain", "text/markdown"];
    if (!valid.includes(file.type) && !file.name.endsWith(".txt") && !file.name.endsWith(".pdf")) {
        alert("Please upload a PDF or text file."); return;
    }
    selectedFile = file;
    document.getElementById("fileName").textContent = `Selected: ${file.name}`;
    document.getElementById("fileName").style.display = "block";
    document.getElementById("uploadBtn").disabled = false;
}

async function _uploadResume() {
    if (!selectedFile) return;
    _showCard("loadingCard");

    const form = new FormData();
    form.append("file", selectedFile);
    form.append("user_id", USER_ID);

    try {
        const res = await fetch(`${API_BASE}/api/resume/upload`, { method: "POST", body: form });
        const text = await res.text();
        let json;
        try { json = JSON.parse(text); } catch { throw new Error(`Server error (${res.status}): ${text.slice(0, 200)}`); }
        if (!res.ok) throw new Error(json.detail || `Upload failed (${res.status})`);
        _showParsedResult(json.data);
    } catch (e) {
        alert("Error: " + e.message);
        _showCard("uploadCard");
    }
}

function _showParsedResult(data) {
    const skills = data.skills || [];
    const projects = data.projects || [];
    document.getElementById("skillsList").innerHTML =
        `<p style="color:var(--text-secondary);font-size:0.8rem;margin-bottom:8px;">Skills (${skills.length}):</p>` +
        `<div style="display:flex;flex-wrap:wrap;gap:6px;">${skills.map(s => `<span style="padding:4px 10px;border-radius:20px;background:var(--accent-dim);color:var(--accent);font-size:0.75rem;border:1px solid var(--border-accent);">${s}</span>`).join("")}</div>`;
    document.getElementById("projectsList").innerHTML =
        `<p style="color:var(--text-secondary);font-size:0.8rem;">Projects: ${projects.length} found</p>`;
    _showCard("parsedCard");
}

async function _startVoiceInterview() {
    _showCard("interviewActive");
    ws = new WebSocket(`${WS_BASE}/ws/interview`);
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
        ws.send(JSON.stringify({ user_id: USER_ID, name: "Candidate" }));
        _startMic();
        if (window.Proctor) window.Proctor.initProctor(ws, null);
    };
    ws.onmessage = (e) => {
        if (e.data instanceof ArrayBuffer) { _playAudio(e.data); }
        else { try { const d = JSON.parse(e.data); console.log("[WS]", d); } catch {} }
    };
    ws.onclose = () => { _stopMic(); };
}

async function _startMic() {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(mediaStream, { mimeType: "audio/webm;codecs=opus" });
    mediaRecorder.ondataavailable = (e) => { if (ws && ws.readyState === 1 && e.data.size) ws.send(e.data); };
    mediaRecorder.start(250);
}

function _stopMic() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
    if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
}

function _playAudio(buffer) {
    const blob = new Blob([buffer], { type: "audio/opus" });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play().catch(() => {});
    audio.onended = () => URL.revokeObjectURL(url);
}

function _endInterview() {
    if (ws) ws.close();
    _stopMic();
    if (window.Proctor) window.Proctor.destroyProctor();
    _showCard("uploadCard");
}

function _showCard(id) {
    ["uploadCard", "loadingCard", "parsedCard", "interviewActive"].forEach(c => {
        const el = document.getElementById(c);
        if (el) el.style.display = c === id ? "block" : "none";
    });
}
