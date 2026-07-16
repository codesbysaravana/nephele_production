import landing from './pages/landing.js';
import voice from './pages/voice.js';

const route = {
    "": landing,
    "#": landing,
    "#/landing": landing,
    "#/voice": voice
};

export default route;