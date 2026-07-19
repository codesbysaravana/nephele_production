"""
ML Prediction Engine — Lazy-loaded singleton.
Loads the trained XGBoost model on first call and caches it.
"""

import json
import numpy as np
from pathlib import Path
from xgboost import XGBClassifier

ARTIFACT_DIR = Path(__file__).parent / "artifacts"

_model: XGBClassifier | None = None


def _load_model() -> XGBClassifier:
    global _model
    if _model is None:
        model_path = ARTIFACT_DIR / "model.json"
        if not model_path.exists():
            raise FileNotFoundError(
                "Model artifact not found. Run `python -m ml.train` first."
            )
        _model = XGBClassifier()
        _model.load_model(str(model_path))
    return _model


def predict(day_of_week: int, hour: int, week_number: int, historical_rate: float) -> dict:
    """
    Predict whether a student will attend.
    Returns dict with prediction (0/1) and confidence (probability).
    """
    model = _load_model()
    features = np.array([[day_of_week, hour, week_number, historical_rate]])
    prediction = int(model.predict(features)[0])
    probability = float(model.predict_proba(features)[0][1])

    return {
        "will_attend": prediction,
        "confidence": round(probability, 4),
        "input": {
            "day_of_week": day_of_week,
            "hour": hour,
            "week_number": week_number,
            "historical_rate": historical_rate,
        },
    }


def get_metrics() -> dict:
    metrics_path = ARTIFACT_DIR / "metrics.json"
    if not metrics_path.exists():
        return {"error": "No metrics found. Train the model first."}
    with open(metrics_path) as f:
        return json.load(f)
