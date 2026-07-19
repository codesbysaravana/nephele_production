"""
ML API Router — Mounts under /api/predict, /api/model/metrics, /api/forecast.
Fully decoupled from the voice WebSocket pipeline.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ml.predict import predict, get_metrics

router = APIRouter(tags=["ML Pipeline"])

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class PredictionRequest(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    hour: int = Field(..., ge=0, le=23)
    week_number: int = Field(..., ge=0)
    historical_rate: float = Field(..., ge=0.0, le=1.0)


class PredictionResponse(BaseModel):
    will_attend: int
    confidence: float
    input: dict


@router.post("/api/predict", response_model=PredictionResponse)
async def make_prediction(req: PredictionRequest):
    """Predict attendance for a student given session features."""
    try:
        result = predict(
            day_of_week=req.day_of_week,
            hour=req.hour,
            week_number=req.week_number,
            historical_rate=req.historical_rate,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/api/model/metrics")
async def model_metrics():
    """Return training metrics for the current deployed model."""
    return get_metrics()


@router.get("/api/forecast")
async def attendance_forecast():
    """
    Predict attendance probability for each day of the upcoming week.
    Uses an average historical_rate of 0.75 (adjustable) and 10am sessions.
    Returns data ready for Chart.js rendering on the dashboard.
    """
    today = datetime.now()
    current_week = today.isocalendar()[1] % 52

    labels = []
    values = []

    for offset in range(7):
        target_date = today + timedelta(days=offset)
        day_of_week = target_date.weekday()

        try:
            result = predict(
                day_of_week=day_of_week,
                hour=10,
                week_number=current_week,
                historical_rate=0.75,
            )
            confidence = result["confidence"]
        except FileNotFoundError:
            confidence = 0.0

        labels.append(f"{DAY_NAMES[day_of_week]} {target_date.strftime('%d/%m')}")
        values.append(round(confidence * 100, 1))

    return {
        "labels": labels,
        "values": values,
        "unit": "percent",
        "description": "Predicted attendance probability for next 7 days",
    }
