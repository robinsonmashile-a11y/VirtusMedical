"""
CadenceWorks Analytics Engine
Layer 1: Data Ingestor & Standardiser

Accepts any Excel/CSV booking file and maps it to the
Universal Data Model (UDM) used by the analytics engine.
"""

import pandas as pd
import numpy as np
from pathlib import Path


# ── Universal Data Model schema ──────────────────────────────────────────────
# These are the canonical column names the engine expects downstream.
UDM_COLUMNS = {
    "appointment_id":   str,
    "status":           str,    # Completed | No-Show | Cancelled | Late Cancel
    "provider":         str,
    "patient_id":       str,
    "patient_type":     str,    # New | Returning
    "appointment_date": "datetime",
    "appointment_type": str,    # Consult | Follow-up | Procedure
    "fee":              float,
    "channel":          str,    # Phone | WhatsApp | Online
    "booked_at":        "datetime",
    "lead_time_days":   int,
    "is_prime_slot":    bool,
    "day_of_week":      str,
    "time_block":       str,
}

# ── Known column alias maps (extend as new clients added) ─────────────────────
COLUMN_ALIASES = {
    "appointment_id":   ["Appt_ID", "appointment_id", "appt_id", "id", "booking_id", "appointment id"],
    "status":           ["Status", "status", "outcome", "appt_status"],
    "provider":         ["Provider", "provider", "doctor", "practitioner", "staff"],
    "patient_id":       ["Patient_ID", "patient_id", "client_id", "customer_id"],
    "patient_type":     ["Patient_Type", "patient_type", "client_type", "customer_type", "patient type"],
    "appointment_date": ["Appt_Date", "appointment_date", "appt_date", "date", "visit_date",
                         "appointment date", "Appointment Date"],
    "appointment_type": ["Appt_Type", "appointment_type", "appt_type", "type", "service_type",
                         "appointment type", "Appointment Type"],
    "fee":              ["Fee_Scheduled", "fee", "fee_scheduled", "amount", "price", "revenue",
                         "fee (r)", "Fee (R)", "fee (R)"],
    "channel":          ["Channel", "channel", "booking_channel", "source",
                         "booking channel", "Booking Channel"],
    "booked_at":        ["Booked_At", "booked_at", "booking_date", "created_at",
                         "booking date", "Booking Date"],
    "lead_time_days":   ["Lead_Time_Days", "lead_time_days", "lead_time", "days_advance",
                         "lead time (days)", "Lead Time (days)"],
    "is_prime_slot":    ["Is_Prime_Slot", "is_prime_slot", "prime_slot", "peak_slot"],
    "day_of_week":      ["DayOfWeek", "day_of_week", "day", "weekday", "day of week", "Day of Week"],
    "time_block":       ["TimeBlock", "time_block", "time_slot", "slot",
                         "appointment time", "Appointment Time"],
    "pillar":           ["pillar", "service_pillar", "service pillar", "Service Pillar",
                         "clinic", "department"],
}

STATUS_NORMALISE = {
    "completed":    "Completed",
    "complete":     "Completed",
    "attended":     "Completed",
    "kept":         "Completed",
    "no-show":      "No-Show",
    "noshow":       "No-Show",
    "no show":      "No-Show",
    "dna":          "No-Show",
    "cancelled":    "Cancelled",
    "canceled":     "Cancelled",
    "cancel":       "Cancelled",
    "late cancel":  "Late Cancel",
    "late cancellation": "Late Cancel",
}


def load(filepath) -> pd.DataFrame:
    """Load Excel or CSV file into a raw DataFrame."""
    fp = Path(filepath)
    if fp.suffix in [".xlsx", ".xlsm", ".xls"]:
        return pd.read_excel(fp)
    elif fp.suffix == ".csv":
        return pd.read_csv(fp)
    else:
        raise ValueError(f"Unsupported file type: {fp.suffix}. Use .xlsx or .csv")


def _find_column(df: pd.DataFrame, udm_key: str):
    """Find the actual column name in df that matches a UDM key via aliases.
    Normalises spaces and hyphens to underscores so headers like
    'Appointment Date' match the alias 'appointment_date'.
    """
    aliases = [a.lower() for a in COLUMN_ALIASES.get(udm_key, [])]
    # Also include the udm_key itself as an alias
    if udm_key.lower() not in aliases:
        aliases.append(udm_key.lower())
    for col in df.columns:
        normalised = col.lower().replace(" ", "_").replace("-", "_")
        if col.lower() in aliases or normalised in aliases:
            return col
    return None


def _compute_lead_time(df: pd.DataFrame, date_col: str, booked_col: str) -> pd.Series:
    """Compute lead time in days if not present."""
    try:
        return (pd.to_datetime(df[date_col]) - pd.to_datetime(df[booked_col])).dt.days.clip(lower=0)
    except Exception:
        return pd.Series([np.nan] * len(df))


def _compute_day_of_week(df: pd.DataFrame, date_col: str) -> pd.Series:
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return pd.to_datetime(df[date_col]).dt.dayofweek.map(lambda x: days[x])


def standardise(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Map raw DataFrame columns → Universal Data Model.
    Returns a clean DataFrame ready for the analytics engine.
    """
    udm = pd.DataFrame()
    mapping = {}

    # Build column mapping
    for udm_key in UDM_COLUMNS:
        found = _find_column(raw, udm_key)
        if found:
            mapping[udm_key] = found

    # Populate UDM columns
    for udm_key, raw_col in mapping.items():
        udm[udm_key] = raw[raw_col]

    # ── Derive missing columns where possible ────────────────────────────────

    # lead_time_days: derive if missing
    if "lead_time_days" not in udm.columns:
        if "appointment_date" in mapping and "booked_at" in mapping:
            udm["lead_time_days"] = _compute_lead_time(
                raw, mapping["appointment_date"], mapping["booked_at"]
            )

    # day_of_week: derive if missing
    if "day_of_week" not in udm.columns:
        if "appointment_date" in mapping:
            udm["day_of_week"] = _compute_day_of_week(raw, mapping["appointment_date"])

    # is_prime_slot: derive if missing (morning 08-10 or lunchtime 13-14)
    if "is_prime_slot" not in udm.columns:
        if "time_block" in udm.columns:
            udm["is_prime_slot"] = udm["time_block"].str.contains(
                r"08:|09:|13:|14:", na=False
            )
        else:
            udm["is_prime_slot"] = False

    # ── Type coercions ───────────────────────────────────────────────────────
    if "appointment_date" in udm.columns:
        udm["appointment_date"] = pd.to_datetime(udm["appointment_date"], errors="coerce")
    if "booked_at" in udm.columns:
        udm["booked_at"] = pd.to_datetime(udm["booked_at"], errors="coerce")
    if "fee" in udm.columns:
        udm["fee"] = pd.to_numeric(udm["fee"], errors="coerce").fillna(0)
    if "lead_time_days" in udm.columns:
        udm["lead_time_days"] = pd.to_numeric(udm["lead_time_days"], errors="coerce").fillna(0).astype(int)

    # ── Normalise status values ──────────────────────────────────────────────
    if "status" in udm.columns:
        udm["status"] = udm["status"].str.strip().str.lower().map(
            lambda s: STATUS_NORMALISE.get(s, s.title() if isinstance(s, str) else s)
        )

    # ── Normalise is_prime_slot to bool ─────────────────────────────────────
    if "is_prime_slot" in udm.columns:
        udm["is_prime_slot"] = udm["is_prime_slot"].map(
            lambda x: True if str(x).strip().upper() in ["Y", "YES", "TRUE", "1"] else
                      False if str(x).strip().upper() in ["N", "NO", "FALSE", "0"] else bool(x)
        )

    # ── Pass through extra columns not in UDM (e.g. Pillar for Virtus Health)
    all_aliases = {a.lower() for aliases in COLUMN_ALIASES.values() for a in aliases}
    for col in raw.columns:
        col_lower = col.lower()
        if col_lower not in udm.columns and col_lower not in all_aliases:
            udm[col_lower] = raw[col].values

    return udm


def ingest(filepath) -> tuple:
    """
    Main entry point. Load, standardise and return (dataframe, metadata).
    metadata contains info about what was found/mapped.
    """
    raw = load(filepath)
    udm = standardise(raw)

    meta = {
        "source_file":   Path(filepath).name,
        "raw_rows":      len(raw),
        "raw_columns":   list(raw.columns),
        "udm_columns":   list(udm.columns),
        "missing_udm":   [k for k in UDM_COLUMNS if k not in udm.columns],
        "date_range":    None,
        "providers":     [],
    }

    if "appointment_date" in udm.columns:
        meta["date_range"] = (
            str(udm["appointment_date"].min().date()),
            str(udm["appointment_date"].max().date()),
        )
    if "provider" in udm.columns:
        meta["providers"] = udm["provider"].dropna().unique().tolist()

    return udm, meta
