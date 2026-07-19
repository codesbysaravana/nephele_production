const attendance = () => {
    // Wait for the DOM to render the #reader div before starting the scanner
    setTimeout(() => {
        if (!document.getElementById("qr-script")) {
            const script = document.createElement("script");
            script.id = "qr-script";
            script.src = "https://unpkg.com/html5-qrcode";
            script.onload = startScanner;
            document.head.appendChild(script);
        } else {
            startScanner();
        }
    }, 100);

    function startScanner() {
        const statusEl = document.getElementById("qr-status");
        statusEl.innerText = "Initializing Webcam...";

        // Ensure Html5Qrcode is loaded
        if (typeof Html5Qrcode === 'undefined') {
            statusEl.innerText = "Failed to load scanner library.";
            return;
        }

        const html5QrCode = new Html5Qrcode("reader");
        const config = { fps: 10, qrbox: { width: 250, height: 250 } };

        html5QrCode.start({ facingMode: "environment" }, config, async (decodedText) => {
            // Success! A QR code was found
            statusEl.innerText = "Scanned: " + decodedText;

            // Stop scanning immediately
            html5QrCode.stop().then(() => {
                document.getElementById("reader").style.display = "none";
            }).catch(err => console.error(err));

            // Send the scanned data to the FastAPI backend
            try {
                statusEl.innerText = "Saving attendance...";

                const apiUrl = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
                    ? "http://localhost:8000/api/attendance"
                    : "https://nephele-dsoa.onrender.com/api/attendance";

                await fetch(apiUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ student_id: decodedText, timestamp: new Date().toISOString() })
                });

                statusEl.innerText = "Attendance Logged! Returning to Nephele...";
                statusEl.style.color = "#4cc9f0";

                // Parse the QR code payload to extract the name
                let userName = "Agent";
                try {
                    const parsedQR = JSON.parse(decodedText);
                    if (parsedQR.name) {
                        userName = parsedQR.name;
                    }
                } catch (e) {
                    console.log("QR is not JSON, using default name.");
                }

                // Play the welcome audio instantly using Web Speech API
                const utterance = new SpeechSynthesisUtterance(`Welcome ${userName}, your presence has been initialized`);
                utterance.rate = 1.0;
                utterance.pitch = 1.0;
                window.speechSynthesis.speak(utterance);

                // Autonomously route back to the Voice AI page
                setTimeout(() => {
                    window.location.hash = "#/voice";
                }, 3500);

            } catch (e) {
                console.error(e);
                statusEl.innerText = "Network error saving attendance.";
                statusEl.style.color = "#ef4444";
            }
        }, (errorMessage) => {
            // parse error, ignore it (happens every frame it doesn't see a QR)
        }).catch(err => {
            console.error(err);
            statusEl.innerText = "Error starting webcam. Please grant permissions.";
        });
    }

    return `
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; width: 100vw; background: var(--bg-obsidian, #050508); color: #fff; animation: fadeIn 0.5s ease-out both;">

        <!-- Subtle gradient backdrop -->
        <div style="position: fixed; inset: 0; background: radial-gradient(ellipse at top, rgba(76,201,240,0.03) 0%, transparent 60%); pointer-events: none;"></div>

        <div style="position: relative; z-index: 1; display: flex; flex-direction: column; align-items: center;">
            <p style="font-size: 0.75rem; font-weight: 500; color: rgba(76, 201, 240, 0.6); letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 8px;">QR Scanner</p>
            <h1 style="margin-bottom: 8px; font-size: 2.2rem;">Nephele Vision</h1>
            <p style="margin-bottom: 40px; color: rgba(255,255,255,0.4); font-size: 0.9rem; font-weight: 400;">Scan a student QR code to log attendance</p>

            <!-- The div where the webcam stream will render -->
            <div id="reader" style="width: 300px; height: 300px; border: 2px solid rgba(76, 201, 240, 0.3); border-radius: 20px; overflow: hidden; background: rgba(14, 14, 20, 0.8); box-shadow: 0 0 40px rgba(76, 201, 240, 0.08), inset 0 0 30px rgba(0,0,0,0.3); animation: borderGlow 3s ease-in-out infinite;"></div>

            <p id="qr-status" style="margin-top: 30px; font-size: 1rem; font-weight: 600; color: var(--accent, #4cc9f0); text-align: center; max-width: 80%; min-height: 1.5em;"></p>

            <a href="#/voice" class="neph-link" style="margin-top: 35px;">Cancel</a>
        </div>
    </div>
    `;
};

export default attendance;
