"""
CadenceWorks Analytics Engine
Layer 3: Predictive Analytics

Trains a No-Show Risk Score model on the available data.
Returns per-appointment risk scores + model metadata.
Falls back to rule-based scoring if insufficient data for ML.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score
from sklearn.metrics import roc_auc_score


MIN_ROWS_FOR_ML = 100   # minimum rows before we use ML vs rules


# ── Feature engineering ───────────────────────────────────────────────────────

def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Convert UDM columns into model-ready numeric features."""
    feat = pd.DataFrame(index=df.index)

    # Lead time (numeric, already clean)
    if "lead_time_days" in df.columns:
        feat["lead_time_days"] = df["lead_time_days"].fillna(df["lead_time_days"].median())
    else:
        feat["lead_time_days"] = 5

    # Channel (categorical → ordinal by observed risk)
    channel_risk = {"WhatsApp": 2, "Online": 1, "Phone": 0}
    if "channel" in df.columns:
        feat["channel_risk"] = df["channel"].map(channel_risk).fillna(1)
    else:
        feat["channel_risk"] = 1

    # Patient type
    if "patient_type" in df.columns:
        feat["is_new_patient"] = (df["patient_type"].str.lower() == "new").astype(int)
    else:
        feat["is_new_patient"] = 0

    # Is prime slot
    if "is_prime_slot" in df.columns:
        feat["is_prime_slot"] = df["is_prime_slot"].astype(int)
    else:
        feat["is_prime_slot"] = 0

    # Day of week risk (Mon/Thu highest based on data)
    day_risk = {"Mon": 2, "Tue": 0, "Wed": 1, "Thu": 3, "Fri": 2, "Sat": 1, "Sun": 1}
    if "day_of_week" in df.columns:
        feat["day_risk"] = df["day_of_week"].map(day_risk).fillna(1)
    else:
        feat["day_risk"] = 1

    # Appointment type
    appt_risk = {"Consult": 1, "Follow-up": 0, "Procedure": 1}
    if "appointment_type" in df.columns:
        feat["appt_type_risk"] = df["appointment_type"].map(appt_risk).fillna(1)
    else:
        feat["appt_type_risk"] = 1

    # Lead time buckets as features
    if "lead_time_days" in df.columns:
        feat["is_far_future"] = (df["lead_time_days"] >= 15).astype(int)
        feat["is_same_week"]  = (df["lead_time_days"] <= 3).astype(int)

    return feat


def _rule_based_score(feat_row: pd.Series) -> float:
    """
    Fallback rule-based risk score (0–100) when insufficient data for ML.
    Weights derived from observed data patterns.
    """
    score = 30.0  # base rate ~10% → start at 30

    # Lead time contribution (biggest driver)
    lead = feat_row.get("lead_time_days", 5)
    if lead >= 15:
        score += 35
    elif lead >= 8:
        score += 15
    elif lead >= 4:
        score += 10
    else:
        score -= 10

    # Channel
    ch = feat_row.get("channel_risk", 1)
    score += ch * 12   # WhatsApp +24, Online +12, Phone +0

    # New patient
    score += feat_row.get("is_new_patient", 0) * 12

    # Prime slot
    score += feat_row.get("is_prime_slot", 0) * 8

    # Day risk
    day = feat_row.get("day_risk", 1)
    score += (day - 1) * 8   # Thu adds 16, Tue subtracts 8

    return round(min(max(score, 0), 100), 1)


# ── Main model ────────────────────────────────────────────────────────────────

def run(df: pd.DataFrame) -> dict:
    """
    Train the no-show risk model and score all appointments.
    Returns dict with: scores, model_info, feature_importance, high_risk_appointments.
    """
    results = {}

    if "status" not in df.columns:
        return {"error": "No status column found — cannot train model."}

    # Target: 1 = No-Show, 0 = everything else
    target = (df["status"] == "No-Show").astype(int)
    features = _build_features(df)

    use_ml = len(df) >= MIN_ROWS_FOR_ML and target.sum() >= 10

    if use_ml:
        # ── ML path ──────────────────────────────────────────────────────────
        model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.1,
            random_state=42,
        )
        model.fit(features, target)

        # Risk scores as probabilities scaled to 0–100
        proba = model.predict_proba(features)[:, 1]
        scores = (proba * 100).round(1)

        # Cross-val AUC
        cv_scores = cross_val_score(model, features, target, cv=5, scoring="roc_auc")
        auc = round(cv_scores.mean(), 3)

        # Feature importance
        importance = dict(zip(features.columns, model.feature_importances_.round(3)))
        importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

        results["model_type"] = "GradientBoostingClassifier"
        results["model_auc"]  = auc
        results["cv_scores"]  = [round(s, 3) for s in cv_scores]
        results["feature_importance"] = importance

    else:
        # ── Rule-based fallback ───────────────────────────────────────────────
        scores = features.apply(_rule_based_score, axis=1).values
        results["model_type"] = "Rule-Based (insufficient data for ML)"
        results["model_auc"]  = None
        results["feature_importance"] = {
            "lead_time_days": 0.35,
            "channel_risk":   0.25,
            "is_new_patient": 0.15,
            "day_risk":       0.12,
            "is_prime_slot":  0.08,
            "appt_type_risk": 0.05,
        }

    # ── Score bands ───────────────────────────────────────────────────────────
    score_series = pd.Series(scores, index=df.index)

    def _band(s):
        if s >= 20:   return "High Risk"
        elif s >= 12: return "Medium Risk"
        else:         return "Low Risk"

    bands = score_series.map(_band)
    results["risk_distribution"] = {
        "High Risk":   int((score_series >= 20).sum()),
        "Medium Risk": int(((score_series >= 12) & (score_series < 20)).sum()),
        "Low Risk":    int((score_series < 12).sum()),
    }

    # ── Scored appointments table ─────────────────────────────────────────────
    scored = df.copy()
    scored["risk_score"] = scores.tolist() if hasattr(scores, "tolist") else list(scores)
    scored["risk_band"]  = bands.values

    # High-risk upcoming-style records (treat all for now)
    high_risk = (
        scored[scored["risk_band"] == "High Risk"]
        [[c for c in ["appointment_id","provider","patient_type","channel",
                      "day_of_week","lead_time_days","appointment_type",
                      "risk_score","status"] if c in scored.columns]]
        .sort_values("risk_score", ascending=False)
        .head(20)
    )
    results["high_risk_appointments"] = high_risk.to_dict(orient="records")

    # Score statistics
    results["score_stats"] = {
        "mean":   round(float(score_series.mean()), 1),
        "median": round(float(score_series.median()), 1),
        "p75":    round(float(np.percentile(scores, 75)), 1),
        "p90":    round(float(np.percentile(scores, 90)), 1),
    }

    # Actual vs predicted check (for completed data)
    actual_noshow = target.sum()
    predicted_high = (score_series >= 20).sum()
    results["validation"] = {
        "actual_no_shows":    int(actual_noshow),
        "predicted_high_risk": int(predicted_high),
        "actual_rate_pct":    round(float(actual_noshow / len(df) * 100), 1),
    }

    return results
