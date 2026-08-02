"""
REST endpoint for readiness predictions.
GET /api/readiness/{user_id}
"""

import asyncio  # AUDIT-FIX-1: for to_thread wrapping
from fastapi import APIRouter, HTTPException

from interview.readiness_predict import predict_readiness

router = APIRouter(prefix="/api", tags=["readiness"])


@router.get("/readiness/{user_id}")
async def get_readiness(user_id: str):
    """
    Returns the predicted interview readiness score and weakest topics.
    Requires: model trained (run interview/readiness_train.py) and user has data.
    """
    try:
        result = await asyncio.to_thread(predict_readiness, user_id)  # AUDIT-FIX-1: async SQLite + model inference
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No interview data found for user_id={user_id}",
        )

    return {"status": "success", "data": result}
