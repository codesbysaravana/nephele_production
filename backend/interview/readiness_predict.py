"""
Readiness inference — lazy-loads trained model and predicts from user features.
"""

import numpy as np
from pathlib import Path
from xgboost import XGBRegressor

from interview.readiness_features import extract_features
from interview.readiness_train import FEATURE_NAMES

_MODEL_PATH = Path(__file__).parent / "artifacts" / "readiness_model.json"
_model: XGBRegressor | None = None


def _load_model() -> XGBRegressor:
    """Lazy singleton loader — only loads from disk once."""
    global _model
    if _model is None:
        if not _MODEL_PATH.exists():
            raise FileNotFoundError(
                "Readiness model not trained yet. Run: python interview/readiness_train.py"
            )
        _model = XGBRegressor()
        _model.load_model(str(_MODEL_PATH))
    return _model


def predict_readiness(user_id: str) -> dict | None:
    """
    Predict readiness score for a user. Returns:
    {"score": 0-100, "weakest_topics": [...], "features": {...}}
    or None if no data available.
    """
    features = extract_features(user_id)
    if not features:
        return None

    model = _load_model()

    # Build feature vector in correct order
    x = np.array([[
        features["mcq_accuracy"],
        features["mcq_total"],
        features["mcq_avg_time_ms"],
        features["tech_avg_score"],
        features["tech_total"],
        features["tech_high_count"],
        features["tab_blurs"],
        features["no_face_events"],
        features["multi_face_events"],
    ]])

    raw_score = float(model.predict(x)[0])
    score = max(0, min(100, round(raw_score, 1)))

    # DECISION: Surface weakest topics by accuracy. Simple and interpretable.
    weakest = _find_weakest_topics(features.get("topic_scores", {}))

    return {
        "readiness_score": score,
        "weakest_topics": weakest,
        "features": {k: v for k, v in features.items() if k != "topic_scores"},
    }


def _find_weakest_topics(topic_scores: dict, threshold: float = 0.6) -> list[dict]:
    """Return topics where accuracy is below threshold, sorted weakest first."""
    weak = []
    for topic, data in topic_scores.items():
        if data["total"] == 0:
            continue
        acc = data["correct"] / data["total"]
        if acc < threshold:
            weak.append({"topic": topic, "accuracy": round(acc, 2), "attempts": data["total"]})
    weak.sort(key=lambda x: x["accuracy"])
    return weak
