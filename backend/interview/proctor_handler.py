"""
Handles proctor event text frames from the client.
Action: "proctor_event" with an event_type field.
"""

import json
import asyncio  # AUDIT-FIX-1: for to_thread wrapping
import logging
from fastapi import WebSocket

from interview.proctor_db import ProctorDB

logger = logging.getLogger(__name__)
_db = ProctorDB()


async def handle_proctor_command(raw_text: str, ws: WebSocket,
                                 user_id: str, session_id: str) -> bool:
    """
    Parse and log a proctor event. Returns True if handled.
    """
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return False

    if data.get("action") != "proctor_event":
        return False

    event_type = data.get("event_type", "")
    valid = await asyncio.to_thread(_db.log_event, user_id, session_id, event_type)  # AUDIT-FIX-1

    if not valid:
        await ws.send_text(json.dumps({
            "type": "proctor_error",
            "message": f"Unknown event_type: {event_type}",
            "valid_types": list(ProctorDB.VALID_EVENTS),
        }))
        logger.warning(f"[PROCTOR] Invalid event_type={event_type} user={user_id}")
    else:
        logger.info(f"[PROCTOR] {event_type} user={user_id} session={session_id}")

    return True
