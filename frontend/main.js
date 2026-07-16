const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const wsStatus = document.getElementById("status");


let ws;
let mediaRecorder;
let echoedAudioChunks = []; //store voice in array

let audioQueue = [];
let isPlaying = false;

function playNextAudio() {
    if (audioQueue.length === 0) {
        isPlaying = false;
        return;
    }

    isPlaying = true;
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
        ws = new WebSocket("ws://localhost:8000/ws/audio");

        ws.onopen = () => {
            wsStatus.innerHTML = 'Status: Connected to Server';
            startBtn.disabled = true;
            stopBtn.disabled = false;
            resolve();
        };

    ws.onmessage = (event) => {
        // We received a TTS sentence chunk!
        console.log("🔊 Received audio sentence from server!");
        const audioBlob = new Blob([event.data], { type: 'audio/ogg; codecs=opus' });

        // Add to queue
        audioQueue.push(audioBlob);

        if (!isPlaying) {
            playNextAudio();
            wsStatus.classList.remove('processing');
            wsStatus.innerHTML = 'Status: Speaking...';
        }
    }

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
    // 1. Stop recording from the microphone
    if (mediaRecorder) mediaRecorder.stop();
    
    // 2. Hang up the call entirely!
    if (ws) {
        ws.close();
    }
};