const voice = () => {
    return `
    <div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; overflow: hidden; z-index: 1000; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; padding-bottom: 60px;">

        <!-- The Robot Eyes Video Background -->
        <video autoplay loop muted playsinline style="position: absolute; top: 50%; left: 50%; min-width: 100%; min-height: 100%; width: auto; height: auto; transform: translate(-50%, -50%); object-fit: cover; z-index: -1; filter: brightness(0.8) contrast(1.1);">
            <source src="./assets/nepheletrimmed.mp4" type="video/mp4">
        </video>

        <!-- Animated Dark Overlay -->
        <div id="speakingOverlay" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(5, 5, 8, 0.25); z-index: 0; transition: all 0.6s ease;"></div>

        <!-- Gradient Vignette -->
        <div style="position: absolute; inset: 0; background: radial-gradient(ellipse at center, transparent 30%, rgba(5,5,8,0.6) 100%); z-index: 0; pointer-events: none;"></div>

        <!-- The Controls Overlaid at the Bottom -->
        <div style="z-index: 1; text-align: center; display: flex; flex-direction: column; align-items: center; width: 100%; animation: floatUp 0.8s ease-out both;">

            <p id="status" style="margin-bottom: 18px; font-size: 0.85rem; font-weight: 500; color: rgba(255,255,255,0.5); padding: 8px 22px; background: rgba(14, 14, 20, 0.7); border-radius: 30px; border: 1px solid rgba(255,255,255,0.06); backdrop-filter: blur(20px) saturate(1.6); transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);">Status: Disconnected</p>

            <div id="container" style="display: flex; gap: 12px; background: rgba(14, 14, 20, 0.7); padding: 14px 24px; border-radius: 16px; box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255,255,255,0.04); backdrop-filter: blur(24px) saturate(1.8); border: 1px solid rgba(255, 255, 255, 0.06);">
                <button id="startBtn" style="font-size: 0.9rem; padding: 10px 24px; border-radius: 10px;">Connect Audio</button>
                <button id="stopBtn" disabled style="font-size: 0.9rem; padding: 10px 24px; border-radius: 10px;">Hang Up</button>
            </div>

            <div style="margin-top: 24px; display: flex; gap: 12px;">
                <a href="#/dashboard" class="neph-link" style="font-size: 0.8rem; padding: 8px 16px;">Analytics</a>
                <a href="#/landing" class="neph-link" style="font-size: 0.8rem; padding: 8px 16px;">Home</a>
            </div>
        </div>
    </div>
    `;
}

export default voice;
