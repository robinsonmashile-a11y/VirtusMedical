"""
CadenceWorks — Client Ingestor
Format: Two-file CSV export (BookingTypeReport + BookingStatusReport)

This ingestor handles the specific export format from this client's
booking system, which separates appointment types and statuses into
two separate CSV files that join on date.

USAGE:
    from engine.client_ingestor import ingest_two_file

    udm, meta = ingest_two_file(
        type_file="BookingTypeReport.csv",
        status_file="BookingStatusReport.csv"
    )

The output UDM is identical to the standard ingestor output and is
fully compatible with the descriptive, predictive and prescriptive
analytics engine layers.

KEY DECISIONS:
  - "Done" + "Treated"  → Completed
  - "Booked" on a past date → No-Show (ghost booking — never cancelled, never attended)
  - "Booked" on today or future date → kept as Booked (genuine future appointment)
  - "Ready" + "Arrived" → Completed (patient reached the practice)
  - "Out of office" appointment type → excluded from patient analytics
  - "Meeting" appointment type → excluded from patient analytics
  - Fee is estimated from appointment type (no fee column in source data)
  - Channel defaults to "Unknown" (not in source data — can be enriched later)
  - Provider defaults to "Practice" (not in source data — single-provider assumption)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date, datetime


# ── Fee estimates by appointment type ─────────────────────────────────────────
# Adjust these to match the practice's actual fee schedule
FEE_MAP = {
    "Consultation":  900,
    "Follow-up":     650,
    "New Patient":  1100,
    "Meeting":         0,   # Internal — excluded
    "Out of office":   0,   # Internal — excluded
}
DEFAULT_FEE = 900

# ── Appointment types that are internal (not patient-facing) ──────────────────
INTERNAL_TYPES = {"Out of office", "Meeting"}

# ── Status mapping from source system → UDM ──────────────────────────────────
STATUS_MAP = {
    "Done":     "Completed",
    "Treated":  "Completed",
    "Arrived":  "Completed",
    "Ready":    "Completed",
    "Booked":   "__INFER__",   # Past date → No-Show, future → Booked
}


def _load_csv(filepath: str) -> pd.DataFrame:
    """Load CSV, handle double carriage returns from Windows exports."""
    fp = Path(filepath)
    with open(fp, "r", encoding="utf-8-sig") as f:
        content = f.read().replace("\r\r\n", "\n").replace("\r\n", "\n")
    import io
    return pd.read_csv(io.StringIO(content))


def _normalise_type_file(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise the BookingTypeReport columns."""
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns={
        "date":    "appointment_date",
        "name":    "appointment_type",
        "count":   "type_count",
        "type_id": "type_id",
    })
    df["appointment_date"] = pd.to_datetime(df["appointment_date"], errors="coerce")
    return df


def _normalise_status_file(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise the BookingStatusReport columns."""
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    # Handle both column orderings seen in this client's export
    col_map = {}
    for col in df.columns:
        if col in ("name", "status"):
            col_map[col] = "status"
        elif col == "count":
            col_map[col] = "status_count"
        elif col == "date":
            col_map[col] = "appointment_date"
        elif col in ("status_id",):
            col_map[col] = "status_id"
    df = df.rename(columns=col_map)
    df["appointment_date"] = pd.to_datetime(df["appointment_date"], errors="coerce")
    return df


def _infer_status(row, today: date) -> str:
    """
    For 'Booked' entries: if the appointment date is in the past,
    it's a ghost booking — the patient never showed and was never
    cancelled. We classify this as No-Show.
    """
    if row["raw_status"] == "__INFER__":
        if pd.isna(row["appointment_date"]):
            return "Unknown"
        appt_date = row["appointment_date"].date() if hasattr(row["appointment_date"], "date") else row["appointment_date"]
        if appt_date < today:
            return "No-Show"
        else:
            return "Booked"
    return row["raw_status"]


def _expand_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Source data is aggregated (count per day per type/status).
    Expand each row into individual appointment records so the
    engine can score them individually.
    """
    rows = []
    appt_counter = 1

    for _, row in df.iterrows():
        n = int(row.get("count", 1))
        for i in range(n):
            rows.append({
                "appointment_id":   f"CL{appt_counter:06d}",
                "appointment_date": row["appointment_date"],
                "appointment_type": row["appointment_type"],
                "status":           row["status"],
                "fee":              row["fee"],
                "provider":         row.get("provider", "Practice"),
                "patient_type":     row["patient_type"],
                "channel":          "Unknown",
                "lead_time_days":   1,      # GP default — same/next day booking
                "is_prime_slot":    False,  # Cannot derive from aggregated data
                "day_of_week":      row["appointment_date"].strftime("%a") if pd.notna(row["appointment_date"]) else "Unknown",
                "time_block":       "Unknown",
                "booked_at":        pd.NaT,
                "patient_id":       f"P{appt_counter:06d}",
            })
            appt_counter += 1

    return pd.DataFrame(rows)


def ingest_two_file(
    type_file: str,
    status_file: str,
    fee_map: dict = None,
    provider_name: str = "Practice",
) -> tuple:
    """
    Main entry point for the two-file ingestor.

    Args:
        type_file:     Path to BookingTypeReport.csv
        status_file:   Path to BookingStatusReport.csv
        fee_map:       Optional override for fee estimates per appointment type
        provider_name: Practice or doctor name to use in the provider column

    Returns:
        (udm_df, meta) — standard CadenceWorks UDM format
    """
    today = date.today()
    fees  = fee_map or FEE_MAP

    # ── Load and normalise ────────────────────────────────────────────────────
    type_raw   = _load_csv(type_file)
    status_raw = _load_csv(status_file)

    type_df   = _normalise_type_file(type_raw)
    status_df = _normalise_status_file(status_raw)

    # ── Aggregate both to date level ─────────────────────────────────────────
    # Type file: total per date per appointment type
    type_agg = (
        type_df
        .groupby(["appointment_date", "appointment_type"], as_index=False)["type_count"]
        .sum()
    )

    # Status file: total per date per status
    status_agg = (
        status_df
        .groupby(["appointment_date", "status"], as_index=False)["status_count"]
        .sum()
    )

    # ── Cross-join on date to create type × status combinations ──────────────
    # We distribute status counts proportionally across appointment types
    # on the same day. This is the best we can do without row-level linking.

    type_day   = type_agg.groupby("appointment_date")["type_count"].sum().reset_index(name="day_type_total")
    status_day = status_agg.groupby("appointment_date")["status_count"].sum().reset_index(name="day_status_total")

    # Build the merged record: for each date, for each type, assign the
    # proportional share of each status
    records = []
    all_dates = sorted(set(type_agg["appointment_date"].dropna().unique()))

    for appt_date in all_dates:
        day_types   = type_agg[type_agg["appointment_date"] == appt_date]
        day_statuses = status_agg[status_agg["appointment_date"] == appt_date]

        day_type_total   = day_types["type_count"].sum()
        day_status_total = day_statuses["status_count"].sum()

        if day_type_total == 0 or day_status_total == 0:
            continue

        for _, t_row in day_types.iterrows():
            appt_type  = t_row["appointment_type"]

            # Skip internal types
            if appt_type in INTERNAL_TYPES:
                continue

            type_share = t_row["type_count"] / day_type_total  # proportion of this type

            for _, s_row in day_statuses.iterrows():
                raw_status = s_row["status"]
                mapped     = STATUS_MAP.get(raw_status, "Unknown")

                # Infer no-show for past bookings
                if mapped == "__INFER__":
                    appt_date_plain = appt_date.date() if hasattr(appt_date, "date") else appt_date
                    mapped = "No-Show" if appt_date_plain < today else "Booked"

                # Proportional count for this type × status combination
                proportional_count = round(s_row["status_count"] * type_share)
                if proportional_count == 0:
                    continue

                # Patient type inference
                if appt_type == "New Patient":
                    patient_type = "New"
                elif appt_type == "Follow-up":
                    patient_type = "Returning"
                else:
                    patient_type = "Returning"  # Consultation — assume returning (conservative)

                records.append({
                    "appointment_date": appt_date,
                    "appointment_type": appt_type,
                    "status":           mapped,
                    "raw_status":       raw_status,
                    "count":            proportional_count,
                    "fee":              fees.get(appt_type, DEFAULT_FEE),
                    "provider":         provider_name,
                    "patient_type":     patient_type,
                })

    combined_df = pd.DataFrame(records)

    if combined_df.empty:
        raise ValueError("No patient-facing appointments found after filtering internal types.")

    # ── Expand aggregated rows → individual appointment records ───────────────
    udm = _expand_rows(combined_df)

    # ── Final type coercions ──────────────────────────────────────────────────
    udm["appointment_date"] = pd.to_datetime(udm["appointment_date"], errors="coerce")
    udm["fee"]              = pd.to_numeric(udm["fee"], errors="coerce").fillna(0)
    udm["lead_time_days"]   = udm["lead_time_days"].fillna(1).astype(int)

    # ── Exclude future bookings from historical analysis ──────────────────────
    historical = udm[udm["appointment_date"].dt.date < today].copy()
    future     = udm[udm["appointment_date"].dt.date >= today].copy()

    # ── Build metadata ────────────────────────────────────────────────────────
    ns_count   = (historical["status"] == "No-Show").sum()
    comp_count = (historical["status"] == "Completed").sum()
    total_hist = len(historical)

    meta = {
        "source_files":       [Path(type_file).name, Path(status_file).name],
        "ingestor":           "client_ingestor_two_file",
        "raw_type_rows":      len(type_raw),
        "raw_status_rows":    len(status_raw),
        "total_appointments": total_hist,
        "future_bookings":    len(future),
        "date_range":         (
            str(historical["appointment_date"].min().date()),
            str(historical["appointment_date"].max().date()),
        ) if not historical.empty else None,
        "providers":          historical["provider"].unique().tolist(),
        "status_breakdown":   historical["status"].value_counts().to_dict(),
        "type_breakdown":     historical["appointment_type"].value_counts().to_dict(),
        "completion_rate":    round(comp_count / total_hist * 100, 1) if total_hist > 0 else 0,
        "noshow_rate":        round(ns_count / total_hist * 100, 1) if total_hist > 0 else 0,
        "ghost_bookings":     int((historical["status"] == "No-Show").sum()),
        "revenue_lost":       float(historical[historical["status"] == "No-Show"]["fee"].sum()),
        "udm_columns":        list(historical.columns),
        "missing_udm":        [
            k for k in ["channel", "booked_at", "lead_time_days", "is_prime_slot", "time_block"]
            if k not in historical.columns
        ],
        "enrichment_needed":  [
            "channel — not in source data. Add booking channel column to export.",
            "provider — defaulted to 'Practice'. Add doctor/staff name to export.",
            "lead_time_days — defaulted to 1 day (GP same-day norm). Enrich if booking timestamps available.",
            "time_block — not in source data. Add appointment time to export for slot analysis.",
        ],
        "notes": [
            "Ghost no-shows: past 'Booked' entries that never resolved to Done/Treated.",
            "Fee is estimated from appointment type — confirm actual fee schedule with practice.",
            "Status distribution is proportionally allocated across appointment types per day.",
            "Internal types (Out of office, Meeting) excluded from all analytics.",
        ]
    }

    return historical, future, meta


def ingest_two_file_for_engine(type_file: str, status_file: str, **kwargs) -> tuple:
    """
    Convenience wrapper that returns (udm, meta) matching the standard
    ingestor interface expected by the Streamlit app and analytics layers.
    Only returns historical data for analytics.
    """
    historical, future, meta = ingest_two_file(type_file, status_file, **kwargs)
    return historical, meta


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 3:
        print("Usage: python -m engine.client_ingestor <type_file> <status_file>")
        sys.exit(1)

    type_f   = sys.argv[1]
    status_f = sys.argv[2]

    print(f"\nIngesting:\n  Type file:   {type_f}\n  Status file: {status_f}\n")

    hist, future, meta = ingest_two_file(type_f, status_f)

    print("=" * 55)
    print("  INGEST SUMMARY")
    print("=" * 55)
    print(f"  Date range:        {meta['date_range']}")
    print(f"  Total historical:  {meta['total_appointments']:,}")
    print(f"  Future bookings:   {meta['future_bookings']:,}")
    print(f"  Completion rate:   {meta['completion_rate']}%")
    print(f"  No-show rate:      {meta['noshow_rate']}%")
    print(f"  Ghost no-shows:    {meta['ghost_bookings']:,}")
    print(f"  Revenue lost:      R{meta['revenue_lost']:,.0f}")
    print()
    print("  Status breakdown:")
    for s, n in meta["status_breakdown"].items():
        print(f"    {s}: {n:,}")
    print()
    print("  Type breakdown:")
    for t, n in meta["type_breakdown"].items():
        print(f"    {t}: {n:,}")
    print()
    print("  Enrichment needed:")
    for e in meta["enrichment_needed"]:
        print(f"    → {e}")
    print()
    print("  Sample UDM output (first 5 rows):")
    print(hist.head().to_string())
    print("=" * 55)
