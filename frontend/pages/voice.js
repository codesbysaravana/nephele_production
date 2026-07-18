const voice = () => {
    return `
    <div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; overflow: hidden; z-index: 1000; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; padding-bottom: 60px;">
        
        <!-- The Robot Eyes Video Background -->
        <video autoplay loop muted playsinline style="position: absolute; top: 50%; left: 50%; min-width: 100%; min-height: 100%; width: auto; height: auto; transform: translate(-50%, -50%); object-fit: cover; z-index: -1;">
            <source src="./assets/nepheletrimmed.mp4" type="video/mp4">
        </video>
        
        <!-- Animated Dark Overlay -->
        <div id="speakingOverlay" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.2); z-index: 0; transition: all 0.5s ease;"></div>

        <!-- The Controls Overlaid at the Bottom -->
        <div style="z-index: 1; text-align: center; display: flex; flex-direction: column; align-items: center; width: 100%;">
            
            <p id="status" style="margin-bottom: 15px; font-size: 0.9rem; font-weight: 600; color: #ccc; padding: 8px 20px; background: rgba(0, 0, 0, 0.5); border-radius: 30px; border: 1px solid #333; backdrop-filter: blur(8px); transition: all 0.3s ease;">Status: Disconnected</p>

            <div id="container" style="display: flex; gap: 15px; background: rgba(20, 20, 20, 0.6); padding: 15px 25px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8); backdrop-filter: blur(15px); border: 1px solid rgba(255, 255, 255, 0.1);">
                <button id="startBtn" style="font-size: 0.95rem; padding: 8px 20px;">Connect Audio</button>
                <button id="stopBtn" disabled style="font-size: 0.95rem; padding: 8px 20px;">Hang Up</button>
            </div>
            
            <a href="#/landing" style="margin-top: 25px; color: #888; text-decoration: none; font-size: 0.9rem; transition: color 0.2s;" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='#888'">&#8592; Back to Home</a>
        </div>
    </div>
    `;
}

export default voice;