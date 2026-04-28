"""
CadenceWorks Analytics Engine
Layer 2: Descriptive Analytics

Computes all KPIs, breakdowns and summaries from the UDM DataFrame.
Returns pure Python dicts/lists — no UI concerns here.
"""

import pandas as pd
import numpy as np


def _pct(count, total):
    return round(count / total * 100, 1) if total > 0 else 0.0


def run(df: pd.DataFrame) -> dict:
    """
    Run full descriptive analytics on a standardised UDM DataFrame.
    Returns a nested dict of all metrics.
    """
    total = len(df)
    results = {}

    # ── 1. Top-line KPIs ─────────────────────────────────────────────────────
    status_counts = df["status"].value_counts() if "status" in df.columns else pd.Series()

    completed   = int(status_counts.get("Completed",   0))
    no_shows    = int(status_counts.get("No-Show",     0))
    cancelled   = int(status_counts.get("Cancelled",   0))
    late_cancel = int(status_counts.get("Late Cancel", 0))

    revenue_scheduled = float(df["fee"].sum()) if "fee" in df.columns else 0
    revenue_lost      = float(df.loc[df["status"] == "No-Show", "fee"].sum()) if "fee" in df.columns else 0
    avg_fee           = float(df["fee"].mean()) if "fee" in df.columns else 0
    avg_lead          = float(df["lead_time_days"].mean()) if "lead_time_days" in df.columns else 0

    results["kpis"] = {
        "total_appointments":   total,
        "completed":            completed,
        "no_shows":             no_shows,
        "cancelled":            cancelled,
        "late_cancels":         late_cancel,
        "completion_rate":      _pct(completed, total),
        "no_show_rate":         _pct(no_shows, total),
        "cancellation_rate":    _pct(cancelled, total),
        "late_cancel_rate":     _pct(late_cancel, total),
        "revenue_scheduled":    revenue_scheduled,
        "revenue_lost":         revenue_lost,
        "revenue_recovered":    revenue_scheduled - revenue_lost,
        "avg_fee":              round(avg_fee, 2),
        "avg_lead_time_days":   round(avg_lead, 1),
    }

    # ── 2. No-show rate by dimension ─────────────────────────────────────────

    def _noshow_rate_by(col):
        if col not in df.columns:
            return {}
        grp = df.groupby(col)["status"].apply(
            lambda s: _pct((s == "No-Show").sum(), len(s))
        )
        return grp.sort_values(ascending=False).to_dict()

    results["noshow_by_channel"]      = _noshow_rate_by("channel")
    results["noshow_by_patient_type"] = _noshow_rate_by("patient_type")
    results["noshow_by_day"]          = _noshow_rate_by("day_of_week")
    results["noshow_by_appt_type"]    = _noshow_rate_by("appointment_type")
    results["noshow_by_provider"]     = _noshow_rate_by("provider")

    # Prime vs non-prime
    if "is_prime_slot" in df.columns:
        prime_df     = df[df["is_prime_slot"] == True]
        nonprime_df  = df[df["is_prime_slot"] == False]
        results["noshow_by_slot_type"] = {
            "Prime Slot":     _pct((prime_df["status"] == "No-Show").sum(),    len(prime_df)),
            "Non-Prime Slot": _pct((nonprime_df["status"] == "No-Show").sum(), len(nonprime_df)),
        }

    # Lead time buckets
    if "lead_time_days" in df.columns:
        bins   = [0, 3, 7, 14, 999]
        labels = ["0–3 days", "4–7 days", "8–14 days", "15+ days"]
        df["_lead_bucket"] = pd.cut(df["lead_time_days"], bins=bins, labels=labels, right=True)
        results["noshow_by_lead_time"] = _noshow_rate_by("_lead_bucket")
        df.drop(columns=["_lead_bucket"], inplace=True)

    # ── 3. Volume breakdowns ─────────────────────────────────────────────────

    def _volume_by(col):
        if col not in df.columns:
            return {}
        return df[col].value_counts().to_dict()

    results["volume_by_status"]       = status_counts.to_dict()
    results["volume_by_provider"]     = _volume_by("provider")
    results["volume_by_channel"]      = _volume_by("channel")
    results["volume_by_appt_type"]    = _volume_by("appointment_type")
    results["volume_by_patient_type"] = _volume_by("patient_type")
    results["volume_by_day"]          = _volume_by("day_of_week")

    # Pillar-level breakdown (Virtus Health specific — gracefully skipped if column absent)
    if "pillar" in df.columns or "Pillar" in df.columns:
        pillar_col = "pillar" if "pillar" in df.columns else "Pillar"
        results["volume_by_pillar"]   = _volume_by(pillar_col)
        results["noshow_by_pillar"]   = _noshow_rate_by(pillar_col)
        if "fee" in df.columns:
            results["revenue_by_pillar"] = df.groupby(pillar_col)["fee"].sum().to_dict()
            results["lost_revenue_by_pillar"] = (
                df[df["status"] == "No-Show"]
                .groupby(pillar_col)["fee"].sum().to_dict()
            )

    # ── 4. Revenue breakdowns ────────────────────────────────────────────────
    if "fee" in df.columns and "provider" in df.columns:
        results["revenue_by_provider"] = df.groupby("provider")["fee"].sum().to_dict()
    if "fee" in df.columns and "appointment_type" in df.columns:
        results["revenue_by_appt_type"] = df.groupby("appointment_type")["fee"].sum().to_dict()

    # ── 5. Daily trend ───────────────────────────────────────────────────────
    if "appointment_date" in df.columns:
        daily = df.groupby(df["appointment_date"].dt.date).agg(
            total=("status", "count"),
            no_shows=("status", lambda s: (s == "No-Show").sum()),
            revenue=("fee", "sum") if "fee" in df.columns else ("status", "count"),
        ).reset_index()
        daily["date"] = daily["appointment_date"].astype(str)
        results["daily_trend"] = daily[["date","total","no_shows"]].to_dict(orient="records")

    # ── 6. Provider comparison ───────────────────────────────────────────────
    if "provider" in df.columns:
        prov_stats = []
        for prov, grp in df.groupby("provider"):
            prov_stats.append({
                "provider":      prov,
                "total":         len(grp),
                "completed":     int((grp["status"] == "Completed").sum()),
                "no_show_rate":  _pct((grp["status"] == "No-Show").sum(), len(grp)),
                "revenue":       float(grp["fee"].sum()) if "fee" in grp.columns else 0,
                "avg_lead":      round(float(grp["lead_time_days"].mean()), 1) if "lead_time_days" in grp.columns else 0,
            })
        results["provider_comparison"] = prov_stats

    return results
