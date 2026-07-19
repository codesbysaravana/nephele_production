"""
ML Training Script — Attendance Trend Predictor
Trains on REAL attendance scan data from SQLite, augmented with synthetic data
to ensure model quality even with sparse real records.

Features: day_of_week, hour, week_number, historical_attendance_rate
Target: will_attend (0 or 1)

Run standalone: python -m ml.train
Outputs: backend/ml/artifacts/model.json + metrics.json
"""

import json
import os
import sqlite3
import numpy as np
from pathlib import Path
from datetime import datetime

ARTIFACT_DIR = Path(__file__).parent / "artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)

SEED = 42
N_STUDENTS = 120
N_SESSIONS = 60

ATTENDANCE_DB_PATH = Path(__file__).parent.parent / "attendance.db"


def load_real_attendance_data() -> list[dict]:
    """
    Pulls real scan records from SQLite and engineers ML features.
    Each scan is a positive attendance event (will_attend=1).
    Absence is inferred from gaps in expected sessions.
    """
    if not ATTENDANCE_DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(ATTENDANCE_DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT student_id, scan_time FROM scans ORDER BY scan_time")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return []

    # Build per-student scan history
    student_scans: dict[str, list[datetime]] = {}
    for student_id, scan_time in rows:
        dt = datetime.fromisoformat(scan_time)
        student_scans.setdefault(student_id, []).append(dt)

    # Compute historical rate per student
    total_sessions_estimate = max(len(scans) for scans in student_scans.values())
    if total_sessions_estimate == 0:
        return []

    real_data = []
    for student_id, scans in student_scans.items():
        historical_rate = len(scans) / max(total_sessions_estimate, 1)
        historical_rate = min(historical_rate, 1.0)

        for scan_dt in scans:
            week_number = scan_dt.isocalendar()[1] % 52
            real_data.append({
                "student_id": student_id,
                "session_id": 0,
                "day_of_week": scan_dt.weekday(),
                "hour": scan_dt.hour,
                "week_number": week_number,
                "historical_rate": round(historical_rate, 4),
                "will_attend": 1,
            })

        # Generate synthetic absences for this student (days they didn't show up)
        attended_days = {s.weekday() for s in scans}
        absent_days = [d for d in range(7) if d not in attended_days]
        for day in absent_days:
            real_data.append({
                "student_id": student_id,
                "session_id": 0,
                "day_of_week": day,
                "hour": 10,
                "week_number": week_number,
                "historical_rate": round(historical_rate, 4),
                "will_attend": 0,
            })

    return real_data


def generate_mock_data(n_students: int = N_STUDENTS, n_sessions: int = N_SESSIONS):
    """
    Generates synthetic attendance records as baseline training data.
    Real data from SQLite is merged in during training.
    """
    rng = np.random.default_rng(SEED)

    student_base_rates = rng.beta(a=5, b=2, size=n_students)

    rows = []
    for sid in range(n_students):
        base_rate = student_base_rates[sid]
        for sess in range(n_sessions):
            day_of_week = sess % 7
            hour = rng.choice([9, 10, 11, 14, 15, 16])
            week_number = sess // 7

            day_penalty = 0.15 if day_of_week >= 4 else 0.0
            hour_penalty = 0.10 if hour >= 15 else 0.0

            prob = np.clip(base_rate - day_penalty - hour_penalty, 0.05, 0.98)
            attended = int(rng.random() < prob)

            rows.append({
                "student_id": sid,
                "session_id": sess,
                "day_of_week": day_of_week,
                "hour": hour,
                "week_number": week_number,
                "historical_rate": round(float(base_rate), 4),
                "will_attend": attended,
            })

    return rows


def train_model(data: list[dict]) -> dict:
    """Trains an XGBoost classifier and returns metrics."""
    from xgboost import XGBClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

    features = np.array([
        [r["day_of_week"], r["hour"], r["week_number"], r["historical_rate"]]
        for r in data
    ])
    labels = np.array([r["will_attend"] for r in data])

    X_train, X_test, y_train, y_test = train_test_split(
        features, labels, test_size=0.2, random_state=SEED, stratify=labels
    )

    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=SEED,
        verbosity=0,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "f1_score": round(f1_score(y_test, y_pred), 4),
        "roc_auc": round(roc_auc_score(y_test, y_proba), 4),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "features": ["day_of_week", "hour", "week_number", "historical_rate"],
    }

    model_path = str(ARTIFACT_DIR / "model.json")
    model.save_model(model_path)

    metrics_path = str(ARTIFACT_DIR / "metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics


if __name__ == "__main__":
    print("[*] Loading real attendance data from SQLite...")
    real_data = load_real_attendance_data()
    print(f"    {len(real_data)} real records from attendance.db")

    print("[*] Generating synthetic baseline data...")
    synthetic_data = generate_mock_data()
    print(f"    {len(synthetic_data)} synthetic records")

    data = real_data + synthetic_data
    print(f"    {len(data)} total training records (real + synthetic)")

    print("[*] Training XGBoost classifier...")
    metrics = train_model(data)

    print("[+] Training complete! Metrics:")
    for k, v in metrics.items():
        print(f"    {k}: {v}")
    print(f"\n[+] Artifacts saved to: {ARTIFACT_DIR}")
