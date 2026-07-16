import route from './route.js';

// 1. The SPA Router Logic
const app = document.getElementById("app");

const renderSPA = () => {
    const hash = window.location.hash;
    const template = route[hash] || route[""];
    app.innerHTML = template();

    if (hash === "#/voice") {
        setupVoicePage();
    }
};

window.addEventListener("hashchange", renderSPA);
renderSPA();


function setupVoicePage() {
    const startBtn = document.getElementById("startBtn");
    const stopBtn = document.getElementById("stopBtn");
    const wsStatus = document.getElementById("status");

    let ws;
    let mediaRecorder;
    let audioQueue = [];
    let isPlaying = false;

    function playNextAudio() {
        if (audioQueue.length === 0) {
            isPlaying = false;
            const overlay = document.getElementById("speakingOverlay");
            if (overlay) overlay.classList.remove("nephele-speaking");
            return;
        }

        isPlaying = true;
        const overlay = document.getElementById("speakingOverlay");
        if (overlay) overlay.classList.add("nephele-speaking");
        const audioBlob = audioQueue.shift();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);

        audio.onended = () => {
            playNextAudio(); // Play the next sentence when this one finishes!
        };

        audio.play();
    }

    function connectionSocket() {
        return new Promise((resolve, reject) => {
            ws = new WebSocket("wss://nephele-dsoa.onrender.com/ws/audio");
            //ws = new WebSocket("ws://localhost:8000/ws/audio");
            ws.onopen = () => {
                wsStatus.innerHTML = 'Status: Connected to Server';
                startBtn.disabled = true;
                stopBtn.disabled = false;
                resolve();
            };

            ws.onmessage = (event) => {
                console.log("🔊 Received audio sentence from server!");
                const audioBlob = new Blob([event.data], { type: 'audio/ogg; codecs=opus' });
                audioQueue.push(audioBlob);

                if (!isPlaying) {
                    playNextAudio();
                    wsStatus.classList.remove('processing');
                    wsStatus.innerHTML = 'Status: Speaking...';
                }
            };

            ws.onclose = () => {
                wsStatus.innerHTML = 'Status: Disconnected';
                startBtn.disabled = false;
                stopBtn.disabled = true;
            };

            ws.onerror = (err) => {
                console.error("WebSocket error:", err);
                reject(err);
            };
        });
    }

    startBtn.onclick = async () => {
        try {
            // Ask for microphone permission FIRST!
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // NOW open the websocket to the server and WAIT for it to connect!
            await connectionSocket();

            mediaRecorder = new MediaRecorder(stream);

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 && ws.readyState === WebSocket.OPEN) {
                    ws.send(event.data);
                }
            };

            // Start recording and send chunks every 250ms for ultra-low latency!
            mediaRecorder.start(250);

        } catch (err) {
            console.error("Microphone error:", err);
            wsStatus.innerHTML = 'Status: Microphone Access Denied';
        }
    };

    stopBtn.onclick = () => {
        if (mediaRecorder) mediaRecorder.stop();
        if (ws) {
            ws.close();
        }
    };
}