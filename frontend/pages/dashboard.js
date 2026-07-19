const dashboard = () => {
    setTimeout(() => {
        if (!document.getElementById("chartjs-script")) {
            const script = document.createElement("script");
            script.id = "chartjs-script";
            script.src = "https://cdn.jsdelivr.net/npm/chart.js";
            script.onload = () => { initDashboard(); initDashboardVoice(); };
            document.head.appendChild(script);
        } else {
            initDashboard();
            initDashboardVoice();
        }
    }, 100);

    function getApiBase() {
        if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
            return "http://localhost:8000";
        }
        return "https://nephele-dsoa.onrender.com";
    }

    async function fetchData(endpoint) {
        const resp = await fetch(getApiBase() + endpoint);
        return resp.json();
    }

    async function initDashboard() {
        const statusEl = document.getElementById("dash-status");
        statusEl.innerText = "Loading analytics...";

        try {
            const [revenue, customers, distribution, running, forecast] = await Promise.all([
                fetchData("/api/analytics/revenue-by-day"),
                fetchData("/api/analytics/top-customers"),
                fetchData("/api/analytics/spending-distribution"),
                fetchData("/api/analytics/running-revenue"),
                fetchData("/api/forecast"),
            ]);

            statusEl.innerText = "";

            Chart.defaults.font.family = "'Inter', sans-serif";
            Chart.defaults.color = "#8b8b9a";

            // Revenue Line Chart
            new Chart(document.getElementById("revenueChart"), {
                type: "line",
                data: {
                    labels: revenue.labels,
                    datasets: [{
                        label: "Daily Revenue ($)",
                        data: revenue.values,
                        borderColor: "#4cc9f0",
                        backgroundColor: "rgba(76, 201, 240, 0.06)",
                        fill: true,
                        tension: 0.4,
                        borderWidth: 2,
                        pointBackgroundColor: "#4cc9f0",
                        pointBorderColor: "transparent",
                        pointRadius: 4,
                        pointHoverRadius: 7,
                    }]
                },
                options: chartOpts("Revenue by Day"),
            });

            // Top Customers Bar Chart
            new Chart(document.getElementById("customersChart"), {
                type: "bar",
                data: {
                    labels: customers.labels,
                    datasets: [{
                        label: "Total Spent ($)",
                        data: customers.values,
                        backgroundColor: "rgba(114, 9, 183, 0.6)",
                        hoverBackgroundColor: "rgba(114, 9, 183, 0.85)",
                        borderRadius: 8,
                        borderSkipped: false,
                    }]
                },
                options: {
                    ...chartOpts("Top Customers by Spend"),
                    indexAxis: "y",
                },
            });

            // Spending Distribution Doughnut
            new Chart(document.getElementById("distributionChart"), {
                type: "doughnut",
                data: {
                    labels: distribution.labels,
                    datasets: [{
                        data: distribution.values,
                        backgroundColor: [
                            "rgba(239, 68, 68, 0.7)",
                            "rgba(245, 158, 11, 0.7)",
                            "rgba(16, 185, 129, 0.7)",
                            "rgba(99, 102, 241, 0.7)"
                        ],
                        borderWidth: 0,
                        hoverOffset: 8,
                    }]
                },
                options: {
                    responsive: true,
                    cutout: "65%",
                    plugins: {
                        title: { display: true, text: "Spending Distribution", color: "#eaeaf0", font: { size: 14, weight: 600 } },
                        legend: { position: "bottom", labels: { color: "#8b8b9a", padding: 16, usePointStyle: true, pointStyle: "circle" } },
                    },
                },
            });

            // Running Revenue Area Chart
            new Chart(document.getElementById("runningChart"), {
                type: "line",
                data: {
                    labels: running.labels,
                    datasets: [{
                        label: "Cumulative Revenue ($)",
                        data: running.values,
                        borderColor: "#10b981",
                        backgroundColor: "rgba(16, 185, 129, 0.06)",
                        fill: true,
                        tension: 0.4,
                        borderWidth: 2,
                        pointBackgroundColor: "#10b981",
                        pointBorderColor: "transparent",
                        pointRadius: 4,
                        pointHoverRadius: 7,
                    }]
                },
                options: chartOpts("Cumulative Revenue (Window Function)"),
            });

            // ML Predicted Attendance Chart
            new Chart(document.getElementById("forecastChart"), {
                type: "bar",
                data: {
                    labels: forecast.labels,
                    datasets: [{
                        label: "Predicted Attendance (%)",
                        data: forecast.values,
                        backgroundColor: forecast.values.map(v =>
                            v >= 70 ? "rgba(16, 185, 129, 0.65)" :
                            v >= 50 ? "rgba(245, 158, 11, 0.65)" :
                            "rgba(239, 68, 68, 0.55)"
                        ),
                        hoverBackgroundColor: forecast.values.map(v =>
                            v >= 70 ? "rgba(16, 185, 129, 0.9)" :
                            v >= 50 ? "rgba(245, 158, 11, 0.9)" :
                            "rgba(239, 68, 68, 0.8)"
                        ),
                        borderRadius: 8,
                        borderSkipped: false,
                    }]
                },
                options: {
                    ...chartOpts("ML Attendance Forecast (XGBoost)"),
                    scales: {
                        x: { ticks: { color: "#8b8b9a" }, grid: { color: "rgba(255,255,255,0.03)" } },
                        y: { ticks: { color: "#8b8b9a" }, grid: { color: "rgba(255,255,255,0.03)" }, min: 0, max: 100 },
                    },
                },
            });

        } catch (e) {
            console.error(e);
            statusEl.innerText = "Failed to load analytics. Is the backend running?";
            statusEl.style.color = "#ef4444";
        }
    }

    function chartOpts(title) {
        return {
            responsive: true,
            interaction: { mode: "index", intersect: false },
            plugins: {
                title: { display: true, text: title, color: "#eaeaf0", font: { size: 14, weight: 600 }, padding: { bottom: 16 } },
                legend: { labels: { color: "#8b8b9a", usePointStyle: true, pointStyle: "circle" } },
                tooltip: {
                    backgroundColor: "rgba(14, 14, 20, 0.9)",
                    titleColor: "#eaeaf0",
                    bodyColor: "#8b8b9a",
                    borderColor: "rgba(76, 201, 240, 0.2)",
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 12,
                },
            },
            scales: {
                x: { ticks: { color: "#8b8b9a" }, grid: { color: "rgba(255,255,255,0.03)", drawBorder: false } },
                y: { ticks: { color: "#8b8b9a" }, grid: { color: "rgba(255,255,255,0.03)", drawBorder: false } },
            },
        };
    }

    function initDashboardVoice() {
        const micBtn = document.getElementById("dashMicBtn");
        const micStatus = document.getElementById("dashMicStatus");
        let ws = null;
        let mediaRecorder = null;
        let audioQueue = [];
        let isPlaying = false;
        let isConnected = false;

        function playNext() {
            if (audioQueue.length === 0) {
                isPlaying = false;
                micStatus.innerText = "Listening...";
                return;
            }
            isPlaying = true;
            micStatus.innerText = "Speaking...";
            const blob = audioQueue.shift();
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.onended = playNext;
            audio.play();
        }

        micBtn.onclick = async () => {
            if (isConnected) {
                if (mediaRecorder) mediaRecorder.stop();
                if (ws) ws.close();
                micBtn.innerText = "Ask About Data";
                micBtn.style.background = "";
                micBtn.style.boxShadow = "";
                micStatus.innerText = "";
                isConnected = false;
                return;
            }

            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

                const wsUrl = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
                    ? "ws://localhost:8000/ws/dashboard-voice"
                    : "wss://nephele-dsoa.onrender.com/ws/dashboard-voice";

                ws = new WebSocket(wsUrl);

                ws.onopen = () => {
                    isConnected = true;
                    micBtn.innerText = "Stop Listening";
                    micBtn.style.background = "linear-gradient(135deg, #7209b7, #4cc9f0)";
                    micBtn.style.boxShadow = "0 0 20px rgba(114, 9, 183, 0.4)";
                    micStatus.innerText = "Listening...";

                    mediaRecorder = new MediaRecorder(stream);
                    mediaRecorder.ondataavailable = (e) => {
                        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
                            ws.send(e.data);
                        }
                    };
                    mediaRecorder.start(250);
                };

                ws.onmessage = (event) => {
                    if (typeof event.data === "string") return;
                    const blob = new Blob([event.data], { type: "audio/ogg; codecs=opus" });
                    audioQueue.push(blob);
                    if (!isPlaying) playNext();
                };

                ws.onclose = () => {
                    isConnected = false;
                    micBtn.innerText = "Ask About Data";
                    micBtn.style.background = "";
                    micBtn.style.boxShadow = "";
                    micStatus.innerText = "";
                };

            } catch (err) {
                micStatus.innerText = "Mic access denied";
                micStatus.style.color = "#ef4444";
            }
        };
    }

    return `
    <div style="min-height: 100vh; width: 100vw; background: var(--bg-obsidian, #050508); color: var(--text-primary, #eaeaf0); padding: 50px 24px 40px; box-sizing: border-box; overflow-y: auto; animation: fadeIn 0.5s ease-out both;">

        <!-- Ambient glow -->
        <div style="position: fixed; top: -200px; left: 50%; transform: translateX(-50%); width: 600px; height: 400px; background: radial-gradient(ellipse, rgba(76,201,240,0.04) 0%, transparent 70%); pointer-events: none; z-index: 0;"></div>

        <div style="max-width: 1260px; margin: 0 auto; position: relative; z-index: 1;">

            <!-- Header -->
            <div style="text-align: center; margin-bottom: 40px; animation: fadeInScale 0.6s ease-out both;">
                <p style="font-size: 0.75rem; font-weight: 500; color: rgba(76, 201, 240, 0.6); letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 6px;">Live Data Warehouse</p>
                <h1 style="font-size: 2.4rem; margin-bottom: 8px;">Nephele Analytics</h1>
                <p style="color: var(--text-muted, #55556a); font-size: 0.9rem; font-weight: 400;">Real-time metrics from your Star Schema</p>
                <p id="dash-status" style="margin-top: 12px; color: var(--accent, #4cc9f0); font-weight: 600; font-size: 0.9rem; min-height: 1.3em;"></p>
            </div>

            <!-- Chart Grid -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(480px, 1fr)); gap: 24px;">

                <div style="background: rgba(14,14,20,0.7); border: 1px solid rgba(255,255,255,0.06); border-radius: 20px; padding: 24px; backdrop-filter: blur(20px) saturate(1.6); transition: all 0.3s cubic-bezier(0.4,0,0.2,1); box-shadow: 0 4px 24px rgba(0,0,0,0.3);" onmouseover="this.style.borderColor='rgba(76,201,240,0.2)'; this.style.boxShadow='0 8px 40px rgba(0,0,0,0.4), 0 0 30px rgba(76,201,240,0.05)'; this.style.transform='translateY(-2px)'" onmouseout="this.style.borderColor='rgba(255,255,255,0.06)'; this.style.boxShadow='0 4px 24px rgba(0,0,0,0.3)'; this.style.transform='translateY(0)'">
                    <canvas id="revenueChart"></canvas>
                </div>

                <div style="background: rgba(14,14,20,0.7); border: 1px solid rgba(255,255,255,0.06); border-radius: 20px; padding: 24px; backdrop-filter: blur(20px) saturate(1.6); transition: all 0.3s cubic-bezier(0.4,0,0.2,1); box-shadow: 0 4px 24px rgba(0,0,0,0.3);" onmouseover="this.style.borderColor='rgba(114,9,183,0.3)'; this.style.boxShadow='0 8px 40px rgba(0,0,0,0.4), 0 0 30px rgba(114,9,183,0.08)'; this.style.transform='translateY(-2px)'" onmouseout="this.style.borderColor='rgba(255,255,255,0.06)'; this.style.boxShadow='0 4px 24px rgba(0,0,0,0.3)'; this.style.transform='translateY(0)'">
                    <canvas id="customersChart"></canvas>
                </div>

                <div style="background: rgba(14,14,20,0.7); border: 1px solid rgba(255,255,255,0.06); border-radius: 20px; padding: 24px; backdrop-filter: blur(20px) saturate(1.6); transition: all 0.3s cubic-bezier(0.4,0,0.2,1); box-shadow: 0 4px 24px rgba(0,0,0,0.3);" onmouseover="this.style.borderColor='rgba(76,201,240,0.2)'; this.style.boxShadow='0 8px 40px rgba(0,0,0,0.4), 0 0 30px rgba(76,201,240,0.05)'; this.style.transform='translateY(-2px)'" onmouseout="this.style.borderColor='rgba(255,255,255,0.06)'; this.style.boxShadow='0 4px 24px rgba(0,0,0,0.3)'; this.style.transform='translateY(0)'">
                    <canvas id="distributionChart"></canvas>
                </div>

                <div style="background: rgba(14,14,20,0.7); border: 1px solid rgba(255,255,255,0.06); border-radius: 20px; padding: 24px; backdrop-filter: blur(20px) saturate(1.6); transition: all 0.3s cubic-bezier(0.4,0,0.2,1); box-shadow: 0 4px 24px rgba(0,0,0,0.3);" onmouseover="this.style.borderColor='rgba(16,185,129,0.25)'; this.style.boxShadow='0 8px 40px rgba(0,0,0,0.4), 0 0 30px rgba(16,185,129,0.06)'; this.style.transform='translateY(-2px)'" onmouseout="this.style.borderColor='rgba(255,255,255,0.06)'; this.style.boxShadow='0 4px 24px rgba(0,0,0,0.3)'; this.style.transform='translateY(0)'">
                    <canvas id="runningChart"></canvas>
                </div>

                <!-- ML Forecast Card — special accent border -->
                <div style="background: rgba(14,14,20,0.7); border: 1px solid rgba(114,9,183,0.25); border-radius: 20px; padding: 24px; backdrop-filter: blur(20px) saturate(1.6); transition: all 0.3s cubic-bezier(0.4,0,0.2,1); box-shadow: 0 4px 24px rgba(0,0,0,0.3), 0 0 20px rgba(114,9,183,0.05); grid-column: 1 / -1;" onmouseover="this.style.borderColor='rgba(114,9,183,0.5)'; this.style.boxShadow='0 8px 40px rgba(0,0,0,0.4), 0 0 40px rgba(114,9,183,0.1)'; this.style.transform='translateY(-2px)'" onmouseout="this.style.borderColor='rgba(114,9,183,0.25)'; this.style.boxShadow='0 4px 24px rgba(0,0,0,0.3), 0 0 20px rgba(114,9,183,0.05)'; this.style.transform='translateY(0)'">
                    <canvas id="forecastChart"></canvas>
                    <p style="text-align: center; color: var(--text-muted, #55556a); font-size: 0.75rem; margin-top: 12px; font-weight: 400;">Trained on real QR attendance scans + synthetic augmentation</p>
                </div>

            </div>

            <!-- Dashboard Voice Widget -->
            <div style="margin-top: 36px; text-align: center; padding: 28px; background: rgba(14,14,20,0.7); border: 1px solid rgba(255,255,255,0.06); border-radius: 20px; backdrop-filter: blur(20px) saturate(1.6); transition: all 0.3s cubic-bezier(0.4,0,0.2,1);">
                <p style="color: var(--text-secondary, #8b8b9a); font-size: 0.85rem; margin-bottom: 14px; font-weight: 400;">Ask Nephele about this data</p>
                <button id="dashMicBtn" style="padding: 12px 32px; background: linear-gradient(135deg, rgba(14,14,20,0.9), rgba(20,20,30,0.9)); border: 1px solid rgba(114,9,183,0.3); border-radius: 12px; color: #fff; font-weight: 600; font-size: 0.9rem; cursor: pointer; transition: all 0.3s cubic-bezier(0.4,0,0.2,1);" onmouseover="if(!this.style.boxShadow.includes('20px')){this.style.borderColor='rgba(76,201,240,0.4)'; this.style.transform='translateY(-1px)'}" onmouseout="if(!this.style.boxShadow.includes('20px')){this.style.borderColor='rgba(114,9,183,0.3)'; this.style.transform='translateY(0)'}">Ask About Data</button>
                <p id="dashMicStatus" style="margin-top: 12px; font-size: 0.85rem; color: var(--accent, #4cc9f0); min-height: 1.2em; font-weight: 500;"></p>
            </div>

            <!-- Navigation -->
            <div style="text-align: center; margin-top: 24px; padding-bottom: 20px;">
                <a href="#/voice" class="neph-link">Back to Voice</a>
            </div>
        </div>
    </div>
    `;
};

export default dashboard;
