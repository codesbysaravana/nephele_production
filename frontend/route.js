import landing from './pages/landing.js';
import voice from './pages/voice.js';
import attendance from './pages/attendance.js';

const route = {
    "": landing,
    "#": landing,
    "#/landing": landing,
    "#/voice": voice,
    "#/attendance": attendance
};

export default route;