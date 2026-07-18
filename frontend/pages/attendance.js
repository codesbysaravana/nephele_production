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
            statusEl.innerText = "❌ Failed to load scanner library.";
            return;
        }

        const html5QrCode = new Html5Qrcode("reader");
        const config = { fps: 10, qrbox: { width: 250, height: 250 } };
        
        html5QrCode.start({ facingMode: "environment" }, config, async (decodedText) => {
            // Success! A QR code was found
            statusEl.innerText = "✅ Scanned: " + decodedText;
            
            // Stop scanning immediately
            html5QrCode.stop().then(() => {
                document.getElementById("reader").style.display = "none";
            }).catch(err => console.error(err));
            
            // Send the scanned data to the FastAPI backend
            try {
                statusEl.innerText = "Saving attendance...";
                
                // Assuming backend is on localhost:8000 for local testing
                // If deploying to Render, this should be the Render URL
                const apiUrl = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" 
                                ? "http://localhost:8000/api/attendance" 
                                : "https://nephele-dsoa.onrender.com/api/attendance";
                                
                await fetch(apiUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ student_id: decodedText, timestamp: new Date().toISOString() })
                });
                
                statusEl.innerText = "✅ Attendance Logged! Returning to Nephele...";
                statusEl.style.color = "#4ade80";
                
                // Autonomously route back to the Voice AI page
                setTimeout(() => {
                    window.location.hash = "#/voice";
                }, 2500);
                
            } catch (e) {
                console.error(e);
                statusEl.innerText = "❌ Network error saving attendance.";
                statusEl.style.color = "#ef4444";
            }
        }, (errorMessage) => {
            // parse error, ignore it (happens every frame it doesn't see a QR)
        }).catch(err => {
            console.error(err);
            statusEl.innerText = "❌ Error starting webcam. Please grant permissions.";
        });
    }

    return `
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; width: 100vw; background: #0a0a0a; color: #fff;">
        <h1 style="margin-bottom: 10px; font-size: 2rem;">Nephele Vision</h1>
        <p style="margin-bottom: 40px; color: #888;">Please scan a student QR code to log attendance.</p>
        
        <!-- The div where the webcam stream will render -->
        <div id="reader" style="width: 300px; height: 300px; border: 2px solid #4cc9f0; border-radius: 20px; overflow: hidden; background: #111; box-shadow: 0 0 30px rgba(76, 201, 240, 0.2);"></div>
        
        <p id="qr-status" style="margin-top: 30px; font-size: 1.1rem; font-weight: 600; color: #4cc9f0; text-align: center; max-width: 80%;"></p>
        
        <a href="#/voice" style="margin-top: 40px; padding: 10px 20px; background: #222; border-radius: 10px; color: #aaa; text-decoration: none; transition: all 0.2s;" onmouseover="this.style.color='#fff'; this.style.background='#333';" onmouseout="this.style.color='#aaa'; this.style.background='#222';">Cancel</a>
    </div>
    `;
};

export default attendance;
