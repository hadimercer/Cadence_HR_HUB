"""utils/scoring.py — WF3 Attrition Risk Scoring Engine

Pure Python + psycopg2 + pandas.  No Streamlit.
Called by pages/8_WF3_Risk_Dashboard.py and pages/9_WF3_Config.py.

All factor weights, thresholds, and active flags are read from the
risk_factor_config table at runtime.  Nothing is hardcoded here (WF3-FR-001).

Public API
----------
  run_scoring_engine() -> dict
      Full scoring run for all ACTIVE employees.
      Returns {"scored": int, "errors": list[str], "rag_summary": dict}

  get_latest_scores() -> pd.DataFrame
      Most recent score per employee, joined to headcount context.

  get_score_history(employee_id: str, days: int = 30) -> pd.DataFrame
      Score history for one employee, ordered ASC.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta

import pandas as pd
from psycopg2.extras import RealDictCursor

from utils.db import get_connection

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Immutable: factor_code → attrition_risk_scores column name
# ─────────────────────────────────────────────────────────────────────────────
_FACTOR_COL: dict[str, str] = {
    "COMPA_RATIO":       "score_compa_ratio",
    "RATING_TRAJECTORY": "score_rating_trajectory",
    "TIME_SINCE_MERIT":  "score_time_since_merit",
    "TIME_IN_ROLE":      "score_time_in_role",
    "SENTIMENT_TREND":   "score_sentiment_trend",
    "CHECKIN_FREQUENCY": "score_checkin_frequency",
    "FLIGHT_RISK_ROLE":  "score_flight_risk_role",
}


# ─────────────────────────────────────────────────────────────────────────────
# Sub-score calculators — one per factor
# All return float in range 0.0–100.0.
# Thresholds always sourced from the cfg dict (never hardcoded).
# ─────────────────────────────────────────────────────────────────────────────

def _score_compa_ratio(emp: dict, bands: dict[str, float], cfg: dict) -> float:
    """Factor 1 — COMPA_RATIO (direction BELOW).

    Measures salary position vs band midpoint.
    Being below threshold is the risk signal.
    """
    grade    = emp.get("salary_grade")
    salary   = emp.get("salary")
    midpoint = bands.get(grade)

    if not salary or not midpoint or float(midpoint) == 0:
        return 50.0  # insufficient data → medium risk

    compa_ratio = float(salary) / float(midpoint)
    tmed  = float(cfg["threshold_medium"])  # e.g. 0.95
    thigh = float(cfg["threshold_high"])    # e.g. 0.85

    if compa_ratio >= tmed:
        return 0.0
    elif compa_ratio >= thigh:
        return 50.0
    else:
        return 100.0


def _score_rating_trajectory(emp_id: str, reviews: pd.DataFrame, cfg: dict) -> float:
    """Factor 2 — RATING_TRAJECTORY (direction ABOVE).

    Reviews must be pre-sorted by hr_approved_at DESC within each employee.
    Requires at least 2 approved reviews; uses 3 for the 2-consecutive-drop check.
    """
    rating_map = {"EXCEEDS": 3, "MEETS": 2, "BELOW": 1, "NEW_TO_ROLE": 2}

    emp_rev = reviews[reviews["employee_id"] == emp_id]
    if len(emp_rev) < 2:
        return 0.0  # insufficient data — no risk signal

    s0 = rating_map.get(str(emp_rev.iloc[0]["rating_overall"]).upper(), 2)  # most recent
    s1 = rating_map.get(str(emp_rev.iloc[1]["rating_overall"]).upper(), 2)  # second most recent

    if s0 >= s1:
        return 0.0  # stable or improving

    # Rating dropped. Check for a second consecutive drop using the third review.
    if len(emp_rev) >= 3:
        s2 = rating_map.get(str(emp_rev.iloc[2]["rating_overall"]).upper(), 2)
        if s1 < s2:
            return 100.0  # two consecutive drops

    return 50.0  # single drop only (or only 2 reviews available)


def _score_time_since_merit(emp: dict, today: date, cfg: dict) -> float:
    """Factor 3 — TIME_SINCE_MERIT (direction ABOVE).

    last_merit_date not in schema — defaulting to 50
    """
    # last_merit_date not in schema — defaulting to 50
    last_merit = emp.get("last_merit_date")
    if last_merit is None:
        return 50.0

    if isinstance(last_merit, float) and pd.isna(last_merit):
        months = 24.0  # NULL treated as 24 months (high risk default per spec)
    else:
        try:
            lm_date = (
                last_merit
                if isinstance(last_merit, date)
                else pd.Timestamp(last_merit).date()
            )
            months = (today - lm_date).days / 30.44
        except Exception:
            months = 24.0

    tmed  = float(cfg["threshold_medium"])  # e.g. 12
    thigh = float(cfg["threshold_high"])    # e.g. 18

    if months < tmed:
        return 0.0
    elif months < thigh:
        return 50.0
    else:
        return 100.0


def _score_time_in_role(emp: dict, cfg: dict) -> float:
    """Factor 4 — TIME_IN_ROLE (direction ABOVE).

    Long tenure in the same role without progression is a risk signal.
    """
    tenure = emp.get("tenure_in_role_months")
    if tenure is None or (isinstance(tenure, float) and pd.isna(tenure)):
        return 0.0

    tenure = float(tenure)
    tmed  = float(cfg["threshold_medium"])  # e.g. 24
    thigh = float(cfg["threshold_high"])    # e.g. 36

    if tenure < tmed:
        return 0.0
    elif tenure < thigh:
        return 50.0
    else:
        return 100.0


def _score_sentiment_trend(emp_id: str, oo_df: pd.DataFrame, cfg: dict) -> float:
    """Factor 5 — SENTIMENT_TREND.

    Counts the leading run of consecutive CONCERNING flags from the most
    recent 1:1 backwards.  Stops at the first non-CONCERNING record.
    oo_df must be pre-sorted by week_start_date DESC within each employee.
    """
    emp_oo = oo_df[oo_df["employee_id"] == emp_id]

    consecutive = 0
    for _, row in emp_oo.iterrows():
        if str(row.get("sentiment_flag", "")).upper() == "CONCERNING":
            consecutive += 1
        else:
            break

    tmed = float(cfg["threshold_medium"])  # e.g. 2

    if consecutive < tmed:
        return 0.0
    elif consecutive == tmed:
        return 50.0
    else:
        return 100.0


def _score_checkin_frequency(emp_id: str, oo_df: pd.DataFrame, cfg: dict) -> float:
    """Factor 6 — CHECKIN_FREQUENCY.

    Count of MISSED 1:1 records in the last 90 days (pre-filtered in bulk load).
    """
    emp_oo  = oo_df[oo_df["employee_id"] == emp_id]
    missed  = int((emp_oo["status"].str.upper() == "MISSED").sum())

    tmed  = float(cfg["threshold_medium"])  # e.g. 1
    thigh = float(cfg["threshold_high"])    # e.g. 2

    if missed <= tmed:
        return 0.0
    elif missed <= thigh:
        return 50.0
    else:
        return 100.0


def _score_flight_risk_role(emp: dict, cfg: dict) -> float:
    """Factor 7 — FLIGHT_RISK_ROLE (is_binary = True → 0 or 100 only).

    FLIGHT_RISK_ROLE: no role classification data — defaulting to 0
    """
    # FLIGHT_RISK_ROLE: no role classification data — defaulting to 0
    # Neither flight_risk_roles config field nor a headcount column exists.
    flight_risk = emp.get("flight_risk")
    if flight_risk is None:
        return 0.0
    return 100.0 if bool(flight_risk) else 0.0


def _assign_rag(composite: float) -> str:
    """Map composite score (0–100) to GREEN / AMBER / RED."""
    if composite < 35:
        return "GREEN"
    elif composite < 65:
        return "AMBER"
    else:
        return "RED"


# ─────────────────────────────────────────────────────────────────────────────
# Public functions
# ─────────────────────────────────────────────────────────────────────────────

def run_scoring_engine() -> dict:
    """Full scoring run for all ACTIVE employees in the latest headcount.

    Steps
    -----
    1. Load risk_factor_config (all factors, active and inactive).
    2. Load ACTIVE employees from the latest reporting_period.
    3. Bulk-load supporting data (reviews, 1:1s) — never per-employee queries.
    4. Compute 7 sub-scores + composite + RAG for each employee.
    5. UPSERT to attrition_risk_scores — single commit at the end.
    6. Return summary dict — never raises to caller.

    Returns
    -------
    dict with keys:
        "scored"      : int — number of employees successfully scored
        "errors"      : list[str] — per-employee error messages, if any
        "rag_summary" : dict — {"GREEN": n, "AMBER": n, "RED": n}
    """
    errors: list[str] = []
    scored = 0
    today     = date.today()
    cutoff_90 = today - timedelta(days=90)

    try:
        conn = get_connection()
    except Exception as exc:
        return {"scored": 0, "errors": [f"Connection failed: {exc}"], "rag_summary": {}}

    try:
        # ── 1. Factor config ──────────────────────────────────────────────
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT factor_code, factor_name, is_active, weight,
                       threshold_medium, threshold_high, threshold_direction, is_binary
                FROM risk_factor_config
                ORDER BY factor_code
            """)
            all_factors = [dict(r) for r in cur.fetchall()]

        active_factors  = [f for f in all_factors if f["is_active"]]
        config_by_code  = {f["factor_code"]: f for f in all_factors}

        total_weight = sum(float(f["weight"]) for f in active_factors)
        if total_weight == 0:
            return {
                "scored": 0,
                "errors": ["No active factors with non-zero weights."],
                "rag_summary": {},
            }

        # Redistribute proportionally if active weights don't sum to 100.
        effective_weights = {
            f["factor_code"]: float(f["weight"]) / total_weight
            for f in active_factors
        }

        # Config snapshot stored with every score row (audit trail).
        config_snapshot = json.dumps({
            f["factor_code"]: {
                "weight":           float(f["weight"]),
                "threshold_medium": float(f["threshold_medium"]) if f["threshold_medium"] is not None else None,
                "threshold_high":   float(f["threshold_high"])   if f["threshold_high"]   is not None else None,
                "is_active":        f["is_active"],
            }
            for f in all_factors
        })

        # ── 2. ACTIVE employees (latest reporting_period) ─────────────────
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    h.employee_id, h.first_name, h.last_name,
                    h.department, h.job_title, h.salary, h.salary_grade,
                    h.manager_id, h.tenure_in_role_months, h.status
                FROM headcount_snapshots h
                WHERE h.reporting_period = (
                    SELECT MAX(reporting_period) FROM headcount_snapshots
                )
                AND h.status = 'ACTIVE'
            """)
            emp_rows = [dict(r) for r in cur.fetchall()]

        if not emp_rows:
            return {"scored": 0, "errors": ["No active employees found."], "rag_summary": {}}

        # ── Salary bands: grade → midpoint ────────────────────────────────
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT salary_grade, band_midpoint FROM salary_bands")
            bands: dict[str, float] = {
                row["salary_grade"]: float(row["band_midpoint"])
                for row in cur.fetchall()
                if row["band_midpoint"] is not None
            }

        # ── 3. Bulk supporting data ────────────────────────────────────────

        # Last 3 approved performance reviews per employee (most recent first).
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT employee_id, rating_overall, review_quarter, hr_approved_at
                FROM (
                    SELECT
                        employee_id, rating_overall, review_quarter, hr_approved_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY employee_id
                            ORDER BY hr_approved_at DESC NULLS LAST
                        ) AS rn
                    FROM performance_reviews
                    WHERE status = 'APPROVED'
                ) ranked
                WHERE rn <= 3
            """)
            rev_rows = cur.fetchall()

        if rev_rows:
            reviews_df = pd.DataFrame([dict(r) for r in rev_rows])
            reviews_df = reviews_df.sort_values(
                ["employee_id", "hr_approved_at"], ascending=[True, False]
            )
        else:
            reviews_df = pd.DataFrame(
                columns=["employee_id", "rating_overall", "review_quarter", "hr_approved_at"]
            )

        # 1:1 records in the last 90 days, most recent first per employee.
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT employee_id, week_start_date, sentiment_flag, status
                FROM one_on_ones
                WHERE week_start_date >= %s
                ORDER BY employee_id, week_start_date DESC
            """, (str(cutoff_90),))
            oo_rows = cur.fetchall()

        if oo_rows:
            oo_df = pd.DataFrame([dict(r) for r in oo_rows])
        else:
            oo_df = pd.DataFrame(
                columns=["employee_id", "week_start_date", "sentiment_flag", "status"]
            )

        # ── 4. Score each employee ─────────────────────────────────────────
        score_records: list[dict] = []

        for emp in emp_rows:
            emp_id = str(emp["employee_id"])
            sub_scores: dict[str, float] = {}

            try:
                for factor in active_factors:
                    code = factor["factor_code"]
                    cfg  = config_by_code[code]

                    if code == "COMPA_RATIO":
                        sub_scores[code] = _score_compa_ratio(emp, bands, cfg)

                    elif code == "RATING_TRAJECTORY":
                        sub_scores[code] = _score_rating_trajectory(emp_id, reviews_df, cfg)

                    elif code == "TIME_SINCE_MERIT":
                        sub_scores[code] = _score_time_since_merit(emp, today, cfg)

                    elif code == "TIME_IN_ROLE":
                        sub_scores[code] = _score_time_in_role(emp, cfg)

                    elif code == "SENTIMENT_TREND":
                        sub_scores[code] = _score_sentiment_trend(emp_id, oo_df, cfg)

                    elif code == "CHECKIN_FREQUENCY":
                        sub_scores[code] = _score_checkin_frequency(emp_id, oo_df, cfg)

                    elif code == "FLIGHT_RISK_ROLE":
                        sub_scores[code] = _score_flight_risk_role(emp, cfg)

                    else:
                        # Unknown factor code — skip silently, contribute 0
                        sub_scores[code] = 0.0

                composite = round(
                    sum(
                        sub_scores[f["factor_code"]] * effective_weights[f["factor_code"]]
                        for f in active_factors
                    ),
                    2,
                )
                rag = _assign_rag(composite)

                score_records.append({
                    "employee_id":             emp_id,
                    "calculation_date":        str(today),
                    "composite_score":         composite,
                    "rag_status":              rag,
                    "score_compa_ratio":       sub_scores.get("COMPA_RATIO",       0.0),
                    "score_rating_trajectory": sub_scores.get("RATING_TRAJECTORY", 0.0),
                    "score_time_since_merit":  sub_scores.get("TIME_SINCE_MERIT",  0.0),
                    "score_time_in_role":      sub_scores.get("TIME_IN_ROLE",       0.0),
                    "score_sentiment_trend":   sub_scores.get("SENTIMENT_TREND",   0.0),
                    "score_checkin_frequency": sub_scores.get("CHECKIN_FREQUENCY", 0.0),
                    "score_flight_risk_role":  sub_scores.get("FLIGHT_RISK_ROLE",  0.0),
                    "config_snapshot":         config_snapshot,
                })
                scored += 1

            except Exception as exc:
                errors.append(f"{emp_id}: {exc}")
                logger.exception("Error scoring employee %s", emp_id)

        # ── 5. UPSERT — single transaction, commit once ───────────────────
        if score_records:
            upsert_sql = """
                INSERT INTO attrition_risk_scores (
                    employee_id, calculation_date, composite_score, rag_status,
                    score_compa_ratio, score_rating_trajectory, score_time_since_merit,
                    score_time_in_role, score_sentiment_trend, score_checkin_frequency,
                    score_flight_risk_role, config_snapshot
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (employee_id, calculation_date) DO UPDATE SET
                    composite_score         = EXCLUDED.composite_score,
                    rag_status              = EXCLUDED.rag_status,
                    score_compa_ratio       = EXCLUDED.score_compa_ratio,
                    score_rating_trajectory = EXCLUDED.score_rating_trajectory,
                    score_time_since_merit  = EXCLUDED.score_time_since_merit,
                    score_time_in_role      = EXCLUDED.score_time_in_role,
                    score_sentiment_trend   = EXCLUDED.score_sentiment_trend,
                    score_checkin_frequency = EXCLUDED.score_checkin_frequency,
                    score_flight_risk_role  = EXCLUDED.score_flight_risk_role,
                    config_snapshot         = EXCLUDED.config_snapshot
            """
            with conn.cursor() as cur:
                for rec in score_records:
                    cur.execute(upsert_sql, (
                        rec["employee_id"],
                        rec["calculation_date"],
                        rec["composite_score"],
                        rec["rag_status"],
                        rec["score_compa_ratio"],
                        rec["score_rating_trajectory"],
                        rec["score_time_since_merit"],
                        rec["score_time_in_role"],
                        rec["score_sentiment_trend"],
                        rec["score_checkin_frequency"],
                        rec["score_flight_risk_role"],
                        rec["config_snapshot"],
                    ))
            conn.commit()  # Single commit for the entire batch

        rag_summary = {
            "GREEN": sum(1 for r in score_records if r["rag_status"] == "GREEN"),
            "AMBER": sum(1 for r in score_records if r["rag_status"] == "AMBER"),
            "RED":   sum(1 for r in score_records if r["rag_status"] == "RED"),
        }

        return {"scored": scored, "errors": errors, "rag_summary": rag_summary}

    except Exception as exc:
        errors.append(f"Engine failed: {exc}")
        logger.exception("Scoring engine top-level failure")
        return {"scored": scored, "errors": errors, "rag_summary": {}}

    finally:
        conn.close()


def get_latest_scores() -> pd.DataFrame:
    """Most recent score per employee, joined to headcount context.

    Uses DISTINCT ON to pick the latest calculation_date per employee.
    Returns rows ordered by composite_score DESC (highest risk first).

    Columns
    -------
    employee_id, full_name, department, job_title, manager_id,
    composite_score, rag_status,
    score_compa_ratio, score_rating_trajectory, score_time_since_merit,
    score_time_in_role, score_sentiment_trend, score_checkin_frequency,
    score_flight_risk_role, calculation_date
    """
    sql = """
        SELECT
            s.employee_id,
            h.first_name || ' ' || h.last_name AS full_name,
            h.department,
            h.job_title,
            h.manager_id,
            s.composite_score,
            s.rag_status,
            s.score_compa_ratio,
            s.score_rating_trajectory,
            s.score_time_since_merit,
            s.score_time_in_role,
            s.score_sentiment_trend,
            s.score_checkin_frequency,
            s.score_flight_risk_role,
            s.calculation_date
        FROM (
            SELECT DISTINCT ON (employee_id)
                employee_id,
                calculation_date,
                composite_score,
                rag_status,
                score_compa_ratio,
                score_rating_trajectory,
                score_time_since_merit,
                score_time_in_role,
                score_sentiment_trend,
                score_checkin_frequency,
                score_flight_risk_role
            FROM attrition_risk_scores
            ORDER BY employee_id, calculation_date DESC
        ) s
        JOIN headcount_snapshots h
          ON h.employee_id = s.employee_id
         AND h.reporting_period = (
             SELECT MAX(reporting_period) FROM headcount_snapshots
         )
        ORDER BY s.composite_score DESC
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])
    finally:
        conn.close()


def get_score_history(employee_id: str, days: int = 30) -> pd.DataFrame:
    """Score history for one employee over the last N days.

    Ordered by calculation_date ASC (oldest → newest) for trend charting.

    Columns
    -------
    calculation_date, composite_score, rag_status,
    score_compa_ratio, score_rating_trajectory, score_time_since_merit,
    score_time_in_role, score_sentiment_trend, score_checkin_frequency,
    score_flight_risk_role
    """
    cutoff = date.today() - timedelta(days=days)
    sql = """
        SELECT
            calculation_date,
            composite_score,
            rag_status,
            score_compa_ratio,
            score_rating_trajectory,
            score_time_since_merit,
            score_time_in_role,
            score_sentiment_trend,
            score_checkin_frequency,
            score_flight_risk_role
        FROM attrition_risk_scores
        WHERE employee_id = %s
          AND calculation_date >= %s
        ORDER BY calculation_date ASC
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (employee_id, str(cutoff)))
            rows = cur.fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])
    finally:
        conn.close()
