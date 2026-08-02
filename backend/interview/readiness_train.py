"""
Train the readiness model on synthetic + real data.
Run: python -m interview.readiness_train (or python interview/readiness_train.py)
Produces: backend/interview/artifacts/readiness_model.json + metrics.json
"""

import json
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from xgboost import XGBRegressor

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

# DECISION: Regression (0-100 readiness score) rather than classification.
# Gives more granular signal than pass/fail binary.
FEATURE_NAMES = [
    "mcq_accuracy", "mcq_total", "mcq_avg_time_ms",
    "tech_avg_score", "tech_total", "tech_high_count",
    "tab_blurs", "no_face_events", "multi_face_events",
]


def generate_synthetic_data(n_samples: int = 500) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic training data until enough real data accumulates.
    Simulates realistic distributions for each feature.
    """
    rng = np.random.default_rng(42)

    X = np.zeros((n_samples, len(FEATURE_NAMES)))
    y = np.zeros(n_samples)

    for i in range(n_samples):
        # DECISION: Readiness score is a weighted combination with noise.
        # Weights reflect interviewer intuition about what matters most.
        mcq_acc = rng.beta(5, 3)  # skewed toward decent performance
        mcq_total = rng.integers(5, 30)
        mcq_time = rng.normal(8000, 3000)
        mcq_time = max(2000, min(30000, mcq_time))

        tech_avg = rng.uniform(1, 5)
        tech_total = rng.integers(0, 15)
        tech_high = int(tech_total * rng.beta(2, 3))

        tab_blurs = rng.poisson(3)
        no_face = rng.poisson(1)
        multi_face = rng.poisson(0.5)

        X[i] = [mcq_acc, mcq_total, mcq_time, tech_avg,
                tech_total, tech_high, tab_blurs, no_face, multi_face]

        # Readiness formula (ground truth for synthetic)
        score = (
            mcq_acc * 35
            + (tech_avg / 5) * 40
            + min(tech_total / 10, 1) * 10
            - tab_blurs * 1.5
            - no_face * 2
            - multi_face * 1
            + rng.normal(0, 5)
        )
        y[i] = max(0, min(100, score))

    return X, y


def train():
    """Train and save the readiness model."""
    X, y = generate_synthetic_data(500)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = XGBRegressor(
        n_estimators=100, max_depth=4, learning_rate=0.1,
        random_state=42, verbosity=0,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2 = float(r2_score(y_test, y_pred))

    # Save model
    model_path = ARTIFACTS_DIR / "readiness_model.json"
    model.save_model(str(model_path))

    # Save metrics
    metrics = {"rmse": round(rmse, 2), "r2": round(r2, 4), "n_train": len(X_train)}
    metrics_path = ARTIFACTS_DIR / "readiness_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))

    print(f"Model saved: {model_path}")
    print(f"Metrics: RMSE={rmse:.2f}, R2={r2:.4f}, Train samples={len(X_train)}")
    return model


if __name__ == "__main__":
    train()
