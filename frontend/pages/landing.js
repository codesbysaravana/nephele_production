const landing = () => {
    return `
    <div onclick="window.location.hash='#/voice'" style="cursor: pointer; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; overflow: hidden; z-index: 1000; display: flex; flex-direction: column; align-items: center; justify-content: center;">
        
        <!-- The Robot Eyes Video Background -->
        <video autoplay loop muted playsinline style="position: absolute; top: 50%; left: 50%; min-width: 100%; min-height: 100%; width: auto; height: auto; transform: translate(-50%, -50%); object-fit: cover; z-index: -1;">
            <source src="./assets/nepheletrimmed.mp4" type="video/mp4">
        </video>
    </div>
    `;
}

export default landing;