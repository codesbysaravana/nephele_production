const landing = () => {
    return `
    <div onclick="window.location.hash='#/voice'" style="cursor: pointer; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; overflow: hidden; z-index: 1000; display: flex; flex-direction: column; align-items: center; justify-content: center;">

        <!-- The Robot Eyes Video Background -->
        <video autoplay loop muted playsinline style="position: absolute; top: 50%; left: 50%; min-width: 100%; min-height: 100%; width: auto; height: auto; transform: translate(-50%, -50%); object-fit: cover; z-index: -1; filter: brightness(0.85) contrast(1.1);">
            <source src="./assets/nepheletrimmed.mp4" type="video/mp4">
        </video>

        <!-- Gradient Overlay -->
        <div style="position: absolute; inset: 0; background: linear-gradient(180deg, rgba(5,5,8,0.3) 0%, rgba(5,5,8,0.0) 40%, rgba(5,5,8,0.0) 60%, rgba(5,5,8,0.7) 100%); z-index: 0;"></div>

        <!-- Bottom CTA -->
        <div style="position: absolute; bottom: 60px; z-index: 1; text-align: center; animation: floatUp 1.2s ease-out both;">
            <p style="font-size: 0.85rem; font-weight: 500; color: rgba(76, 201, 240, 0.7); letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 8px;">Voice AI Agent</p>
            <h1 style="font-size: 2.8rem; margin-bottom: 12px; background: linear-gradient(135deg, #4cc9f0, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -0.03em; font-weight: 800;">Nephele</h1>
            <p style="font-size: 0.9rem; color: rgba(255,255,255,0.45); font-weight: 400;">Tap anywhere to begin</p>
        </div>
    </div>
    `;
}

export default landing;
