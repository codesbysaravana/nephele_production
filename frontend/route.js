import landing from './pages/landing.js';
import voice from './pages/voice.js';
import attendance from './pages/attendance.js';
import dashboard from './pages/dashboard.js';

const route = {
    "": landing,
    "#": landing,
    "#/landing": landing,
    "#/voice": voice,
    "#/attendance": attendance,
    "#/dashboard": dashboard
};

export default route;