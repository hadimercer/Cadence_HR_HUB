"""pages/7_WF2_Eligibility.py — WF2 Eligibility Engine

Three-tab page:
  Tab 1 — Run Eligibility       (HR triggers the 6-gate engine)
  Tab 2 — Eligibility Results   (Full drill-down + HR override)
  Tab 3 — Manager Input Forms   (Merit recommendations — WF4->WF2 handoff)
"""

import pandas as pd
import streamlit as st

from utils.db import get_connection, query_df, run_mutation

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
_SYSTEM_USER = "2ad731c3-80c2-4848-a29d-e14361113cfb"

# The six eligibility gates.
# key   -> used as dict key inside the engine gate_results evaluation.
# label -> human-readable string stored in merit_eligibility.ineligibility_reasons.
GATES = [
    ("gate_active",       "Active Employment Status"),
    ("gate_permanent",    "Employment Type: Permanent"),
    ("gate_tenure",       "Tenure in Role \u2265 6 Months"),
    ("gate_rating",       "Performance Rating: Meets or Exceeds"),
    ("gate_review_filed", "HR-Approved Review on File"),
    ("gate_no_pip",       "Not on Performance Improvement Plan"),
]

# Colors — CADENCE.md Section 5
ACCENT  = "#4DB6AC"
GOLD    = "#D4A843"
RED     = "#E05252"
AMBER   = "#E8A838"
GREEN   = "#2ECC7A"
TEXT    = "#FAFAFA"
SURFACE = "#262730"
MUTED   = "#8892A4"


# ─── HELPERS ─────────────────────────────────────────────────────────────────
def _safe_str(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val)


def _safe_float(val) -> float:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _fmt_currency(val) -> str:
    try:
        return f"${float(val):,.0f}"
    except (TypeError, ValueError):
        return "N/A"


# ─── ELIGIBILITY ENGINE ───────────────────────────────────────────────────────
def _run_eligibility_engine(cycle_id: str):
    """Evaluate all 6 gates for every active employee and UPSERT to merit_eligibility.

    Uses get_connection() directly for writes — not query_df (which is cached reads).
    Returns (eligible_count, ineligible_count, error_list).
    """
    # Step A — Active employees from the latest headcount period
    emp_df = query_df("""
        SELECT
            h.employee_id,
            h.first_name || ' ' || h.last_name AS full_name,
            h.employment_type,
            h.status                            AS emp_status,
            h.tenure_in_role_months
        FROM headcount_snapshots h
        WHERE h.reporting_period = (
            SELECT MAX(reporting_period) FROM headcount_snapshots
        )
          AND h.status = 'ACTIVE'
    """)

    if emp_df.empty:
        return 0, 0, ["No active headcount data found. Upload a headcount CSV first."]

    # is_on_pip not in schema — defaulting to False for all employees (WF2 gate 6)
    emp_df["is_on_pip"] = False

    # Step B — Most recent HR-approved quarterly review per employee
    reviews_df = query_df("""
        SELECT DISTINCT ON (employee_id)
               employee_id,
               rating_overall,
               hr_approved_at
        FROM performance_reviews
        WHERE status = 'APPROVED'
        ORDER BY employee_id, hr_approved_at DESC
    """)

    review_lookup: dict = {}
    if not reviews_df.empty:
        for _, rev in reviews_df.iterrows():
            eid        = _safe_str(rev["employee_id"])
            rating_raw = rev["rating_overall"]
            is_null    = rating_raw is None or (isinstance(rating_raw, float) and pd.isna(rating_raw))
            rating     = _safe_str(rating_raw).upper().strip() if not is_null else None
            review_lookup[eid] = {"rating": rating, "has_review": True}

    eligible_count   = 0
    ineligible_count = 0
    errors: list     = []

    # Step C + D — Evaluate gates, then UPSERT each result individually
    conn = get_connection()
    try:
        for _, emp in emp_df.iterrows():
            emp_id     = _safe_str(emp["employee_id"])
            emp_type   = _safe_str(emp["employment_type"]).upper().strip()
            emp_status = _safe_str(emp["emp_status"]).upper().strip()
            tenure     = _safe_float(emp["tenure_in_role_months"])
            is_on_pip  = bool(emp["is_on_pip"])

            rev        = review_lookup.get(emp_id)
            has_review = rev is not None
            rating     = rev["rating"] if rev else None

            gate_results = {
                "gate_active":       emp_status == "ACTIVE",
                "gate_permanent":    emp_type == "PERMANENT",
                "gate_tenure":       tenure >= 6.0,
                "gate_rating":       has_review and rating in ("MEETS", "EXCEEDS"),
                "gate_review_filed": has_review,
                "gate_no_pip":       not is_on_pip,
            }

            failed_labels         = [label for key, label in GATES if not gate_results[key]]
            determination         = "ELIGIBLE" if not failed_labels else "INELIGIBLE"
            ineligibility_reasons = ", ".join(failed_labels)

            if determination == "ELIGIBLE":
                eligible_count += 1
            else:
                ineligible_count += 1

            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM merit_eligibility "
                        "WHERE cycle_id::text = %s AND employee_id = %s",
                        (cycle_id, emp_id),
                    )
                    existing = cur.fetchone()
                    if existing:
                        cur.execute(
                            """
                            UPDATE merit_eligibility
                               SET determination         = %s,
                                   ineligibility_reasons = %s
                             WHERE cycle_id::text = %s
                               AND employee_id    = %s
                            """,
                            (determination, ineligibility_reasons, cycle_id, emp_id),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO merit_eligibility
                                (cycle_id, employee_id, determination, ineligibility_reasons)
                            VALUES (%s::uuid, %s, %s, %s)
                            """,
                            (cycle_id, emp_id, determination, ineligibility_reasons),
                        )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                errors.append(f"{emp_id}: {exc}")
    finally:
        conn.close()

    return eligible_count, ineligible_count, errors


# ─── PAGE CONFIG ──────────────────────────────────────────────────────────────
def page_header(title, subtitle=""):
    sub = f'<p style="color:rgba(255,255,255,0.82); font-size:0.95rem; margin:0;">{subtitle}</p>' if subtitle else ""
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,#1B4F72 0%,#2E86C1 100%);
                border-radius:0.6rem;padding:1rem 1.4rem 0.9rem;margin-bottom:1.2rem;">
      <h1 style="color:#FFFFFF;font-size:1.8rem;font-weight:700;
                 margin:0 0 0.2rem 0;line-height:1.2;">{title}</h1>
      {sub}
    </div>""", unsafe_allow_html=True)


st.set_page_config(page_title="Eligibility & Recommendations \u2014 Cadence", layout="wide")

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.sidebar.markdown("""
<div style="background:linear-gradient(90deg,#1B4F72 0%,#2E86C1 100%);
            border-radius:0.6rem;padding:0.9rem 1.1rem 0.8rem;
            margin-bottom:0.5rem;">
  <div style="display:flex;align-items:center;gap:0.5rem;
              margin-bottom:0.3rem;">
    <span style="font-size:1.3rem;">⚙️</span>
    <span style="color:#FFFFFF;font-size:1.15rem;font-weight:700;
                 line-height:1.2;">Cadence</span>
  </div>
  <p style="color:rgba(255,255,255,0.82);font-size:0.82rem;
            margin:0;line-height:1.3;">
    HR Process Automation Hub
  </p>
</div>
""", unsafe_allow_html=True)
    st.sidebar.page_link("app.py", label="🏠 Home")
    st.sidebar.divider()
    st.markdown("**Workforce Intelligence**")
    st.page_link("pages/1_WF1_Data_Upload.py",      label="Data Upload & Pipeline")
    st.page_link("pages/2_WF1_Dashboard.py",         label="KPI Dashboard")
    st.divider()
    st.markdown("**Performance Management**")
    st.page_link("pages/3_WF4_Weekly_1on1.py",       label="Weekly 1:1s")
    st.page_link("pages/4_WF4_Monthly_Checkin.py",   label="Monthly Check-ins")
    st.page_link("pages/5_WF4_Quarterly_Review.py",  label="Quarterly Reviews")
    st.divider()
    st.markdown("**Compensation Review**")
    st.page_link("pages/6_WF2_Merit_Cycle.py",       label="Merit Cycle")
    st.page_link("pages/7_WF2_Eligibility.py",       label="Eligibility & Recommendations")
    st.divider()
    st.markdown("**Attrition Risk**")
    st.page_link("pages/8_WF3_Risk_Dashboard.py",    label="Risk Dashboard")
    st.page_link("pages/9_WF3_Config.py",            label="Scoring Config")

page_header("Eligibility & Recommendations", "Six-gate eligibility engine. Manager recommendation forms for eligible employees.")

# ─── TAB CSS (CLAUDE.md Section 14) ──────────────────────────────────────────
st.markdown("""
<style>
button[data-baseweb="tab"] {
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    padding: 0.6rem 1.2rem !important;
    border-radius: 0.5rem 0.5rem 0 0 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    background: rgba(46,134,193,0.28) !important;
    border: 1px solid rgba(93,173,226,0.5) !important;
    border-bottom: none !important;
}
div[data-testid="stTabsContent"] {
    background: rgba(255,255,255,0.035);
    border-radius: 0 0 0.6rem 0.6rem;
    padding: 1.2rem 2rem 1.5rem 2rem;
    border: 1px solid rgba(255,255,255,0.06);
    border-top: none;
    margin-top: 0;
}
</style>""", unsafe_allow_html=True)

# ─── ACTIVE CYCLE — loaded once, used in all three tabs ───────────────────────
cycle_df = query_df("""
    SELECT id, cycle_label, status, submission_deadline
    FROM merit_cycles
    WHERE status = 'OPEN'
    ORDER BY opened_at DESC
    LIMIT 1
""")

if cycle_df.empty:
    st.info(
        "\u2139\ufe0f No active merit cycle found. "
        "Open a cycle on the **Merit Cycle** page first."
    )
    st.stop()

cycle_row   = cycle_df.iloc[0]
cycle_id    = str(cycle_row["id"])
cycle_label = _safe_str(cycle_row["cycle_label"])

# Active cycle context banner
st.markdown(
    f'<div style="background:{SURFACE};border-radius:0.5rem;'
    f'padding:0.7rem 1.2rem;margin-bottom:0.6rem;display:flex;'
    f'align-items:center;gap:0.8rem;">'
    f'<span style="color:{MUTED};font-size:0.85rem;">Active cycle:</span>'
    f'<span style="color:{ACCENT};font-weight:700;">{cycle_label}</span>'
    f'<span style="background:{GREEN};color:#FFF;font-size:0.75rem;'
    f'font-weight:600;padding:2px 8px;border-radius:999px;">OPEN</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ─── TABS ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "Run Eligibility",
    "Eligibility Results",
    "Manager Input Forms",
])


# =============================================================================
# TAB 1 — RUN ELIGIBILITY
# =============================================================================
with tab1:
    st.subheader("Run Eligibility Engine")
    st.caption(
        "Evaluates all 6 gates for every active employee and writes results to the database. "
        "Re-running is safe \u2014 existing results are updated, not duplicated."
    )

    # Post-run success message displayed after st.rerun() via session_state
    if st.session_state.get("_elig_run_done"):
        result = st.session_state.pop("_elig_run_done")
        st.success(
            f"\u2705 Eligibility run complete \u2014 "
            f"**{result['eligible']}** eligible, **{result['ineligible']}** ineligible."
        )
        if result.get("errors"):
            with st.expander(f"\u26a0 {len(result['errors'])} employee(s) had errors"):
                for err in result["errors"][:15]:
                    st.caption(f"\u2022 {err}")

    # Current eligibility summary for this cycle
    summary_df = query_df(
        "SELECT determination, COUNT(*) AS cnt "
        "FROM merit_eligibility "
        "WHERE cycle_id = %s::uuid "
        "GROUP BY determination",
        (cycle_id,),
    )

    if summary_df.empty:
        st.info(
            "\u2139\ufe0f Eligibility has not been run for this cycle yet. "
            "Click the button below to start the engine."
        )
    else:
        eligible_now   = 0
        ineligible_now = 0
        for _, sr in summary_df.iterrows():
            det = _safe_str(sr["determination"]).upper()
            cnt = int(_safe_float(sr["cnt"]))
            if det == "ELIGIBLE":
                eligible_now = cnt
            elif det == "INELIGIBLE":
                ineligible_now = cnt

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Eligible",        eligible_now)
        mc2.metric("Ineligible",      ineligible_now)
        mc3.metric("Total Evaluated", eligible_now + ineligible_now)

    st.divider()

    with st.expander("Six gates evaluated by the engine"):
        for i, (_, label) in enumerate(GATES, start=1):
            st.markdown(f"**Gate {i}:** {label}")

    st.markdown("")

    if st.button(
        "\u25b6  Run Eligibility Engine",
        type="primary",
        use_container_width=True,
        key="run_engine_btn",
    ):
        with st.spinner("Running eligibility checks for all active employees\u2026"):
            try:
                el, inel, errors = _run_eligibility_engine(cycle_id)
            except Exception as exc:
                st.error(f"Engine failed with an unexpected error: {exc}")
                st.stop()

        st.session_state["_elig_run_done"] = {
            "eligible":   el,
            "ineligible": inel,
            "errors":     errors,
        }
        query_df.clear()
        st.rerun()


# =============================================================================
# TAB 2 — ELIGIBILITY RESULTS
# =============================================================================
with tab2:
    st.subheader(f"Eligibility Results \u2014 {cycle_label}")

    results_df = query_df(
        """
        SELECT
            me.employee_id,
            me.determination,
            me.ineligibility_reasons,
            me.override_determination,
            me.override_justification,
            me.overridden_at,
            h.first_name || ' ' || h.last_name AS full_name,
            h.department,
            h.job_title,
            h.employment_type,
            h.tenure_in_role_months,
            pr.rating_overall
        FROM merit_eligibility me
        JOIN headcount_snapshots h
          ON h.employee_id = me.employee_id
         AND h.reporting_period = (
               SELECT MAX(reporting_period) FROM headcount_snapshots
             )
        LEFT JOIN (
            SELECT DISTINCT ON (employee_id)
                   employee_id,
                   rating_overall
            FROM performance_reviews
            WHERE status = 'APPROVED'
            ORDER BY employee_id, hr_approved_at DESC
        ) pr ON pr.employee_id = me.employee_id
        WHERE me.cycle_id = %s::uuid
        ORDER BY me.determination, h.department, full_name
        """,
        (cycle_id,),
    )

    if results_df.empty:
        st.info(
            "\u2139\ufe0f No eligibility results for this cycle. "
            "Run the engine in the \u2018Run Eligibility\u2019 tab first."
        )
    else:
        # ── Filter controls ──────────────────────────────────────────────────
        fc1, fc2, fc3 = st.columns([1.5, 2, 2.5])
        with fc1:
            filter_det = st.selectbox(
                "Determination",
                ["All", "ELIGIBLE", "INELIGIBLE"],
                key="t2_det",
            )
        with fc2:
            dept_opts = ["All"] + sorted(
                results_df["department"].dropna().unique().tolist()
            )
            filter_dept = st.selectbox("Department", dept_opts, key="t2_dept")
        with fc3:
            filter_name = st.text_input(
                "Search employee name",
                placeholder="Type to filter\u2026",
                key="t2_name",
            )

        # Apply filters in Python (not SQL — keeps query simple and cacheable)
        fdf = results_df.copy()
        if filter_det != "All":
            fdf = fdf[fdf["determination"] == filter_det]
        if filter_dept != "All":
            fdf = fdf[fdf["department"] == filter_dept]
        if filter_name.strip():
            fdf = fdf[
                fdf["full_name"].str.contains(
                    filter_name.strip(), case=False, na=False
                )
            ]

        st.caption(f"Showing {len(fdf)} of {len(results_df)} employees")

        # ── Build and style display dataframe ────────────────────────────────
        disp = fdf[[
            "full_name", "department", "job_title", "employment_type",
            "tenure_in_role_months", "rating_overall",
            "determination", "ineligibility_reasons", "override_determination",
        ]].copy()

        disp["tenure_in_role_months"] = disp["tenure_in_role_months"].apply(
            lambda x: f"{_safe_float(x):.0f}" if x is not None else "\u2014"
        )
        disp["rating_overall"] = disp["rating_overall"].fillna("\u2014")
        disp["override_determination"] = disp["override_determination"].apply(
            lambda x: _safe_str(x) if _safe_str(x) else "\u2014"
        )
        disp["ineligibility_reasons"] = disp["ineligibility_reasons"].fillna("")

        disp = disp.rename(columns={
            "full_name":              "Name",
            "department":             "Dept",
            "job_title":              "Job Title",
            "employment_type":        "Type",
            "tenure_in_role_months":  "Tenure (mo)",
            "rating_overall":         "Rating",
            "determination":          "Determination",
            "ineligibility_reasons":  "Reasons",
            "override_determination": "Override",
        })

        def _style_determination(val):
            if val == "ELIGIBLE":
                return f"background-color: {GREEN}; color: #FFFFFF; font-weight: 600;"
            if val == "INELIGIBLE":
                return f"background-color: {RED}; color: #FFFFFF; font-weight: 600;"
            return ""

        styled = disp.style.map(_style_determination, subset=["Determination"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # ── HR Override ──────────────────────────────────────────────────────
        st.divider()
        st.subheader("Override Eligibility Determination")
        st.caption(
            "All overrides are permanently logged. "
            "Use only for documented exceptions approved outside the standard process."
        )

        emp_override_opts = {
            f"{row['full_name']}  |  {row['department']}  |  {row['determination']}": row["employee_id"]
            for _, row in results_df.iterrows()
        }
        override_label = st.selectbox(
            "Select Employee to Override",
            ["\u2014 Select \u2014"] + list(emp_override_opts.keys()),
            key="t2_override_emp",
        )

        if override_label != "\u2014 Select \u2014":
            override_emp_id  = emp_override_opts[override_label]
            override_emp_row = results_df[results_df["employee_id"] == override_emp_id].iloc[0]

            det_now     = _safe_str(override_emp_row["determination"])
            reasons_now = _safe_str(override_emp_row["ineligibility_reasons"]) or "None"
            st.info(
                f"Current determination: **{det_now}** | "
                f"Failed gates: {reasons_now}"
            )

            oc1, oc2 = st.columns([1.5, 3])
            with oc1:
                override_det = st.selectbox(
                    "Override To",
                    ["ELIGIBLE", "INELIGIBLE"],
                    key="t2_override_det",
                )
            with oc2:
                override_just = st.text_area(
                    "Justification (mandatory)",
                    height=100,
                    placeholder="Document the business reason for this exception\u2026",
                    key="t2_override_just",
                )

            if st.button("Apply Override", type="primary", key="t2_override_btn"):
                if not override_just.strip():
                    st.error("Justification is required for all overrides.")
                else:
                    try:
                        run_mutation(
                            """
                            UPDATE merit_eligibility
                               SET override_determination = %s,
                                   override_justification = %s,
                                   overridden_by          = %s::uuid,
                                   overridden_at          = NOW()
                             WHERE cycle_id    = %s::uuid
                               AND employee_id = %s
                            """,
                            (
                                override_det,
                                override_just.strip(),
                                _SYSTEM_USER,
                                cycle_id,
                                override_emp_id,
                            ),
                        )
                        query_df.clear()
                        st.success(
                            f"\u2713 Override applied for "
                            f"**{_safe_str(override_emp_row['full_name'])}**: "
                            f"\u2192 {override_det}."
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Database error: {e}")


# =============================================================================
# TAB 3 — MANAGER INPUT FORMS
# =============================================================================
with tab3:
    st.subheader(f"Manager Input Forms \u2014 {cycle_label}")
    st.caption(
        "Employees appear here because they hold an HR-approved quarterly review "
        "with a qualifying rating \u2014 fed from WF4."
    )

    elig_df = query_df(
        """
        SELECT
            me.employee_id,
            h.first_name || ' ' || h.last_name AS full_name,
            h.department,
            h.job_title,
            h.salary,
            h.tenure_in_role_months,
            h.manager_id,
            pr.rating_overall,
            mr.id                             AS rec_id,
            mr.status                         AS rec_status,
            mr.base_increase_pct,
            mr.bonus_amount,
            mr.justification_note             AS rec_justification
        FROM merit_eligibility me
        JOIN headcount_snapshots h
          ON h.employee_id = me.employee_id
         AND h.reporting_period = (
               SELECT MAX(reporting_period) FROM headcount_snapshots
             )
        LEFT JOIN (
            SELECT DISTINCT ON (employee_id)
                   employee_id,
                   rating_overall
            FROM performance_reviews
            WHERE status = 'APPROVED'
            ORDER BY employee_id, hr_approved_at DESC
        ) pr ON pr.employee_id = me.employee_id
        LEFT JOIN merit_recommendations mr
          ON mr.employee_id = me.employee_id
         AND mr.cycle_id    = me.cycle_id
        WHERE me.cycle_id = %s::uuid
          AND (
                me.determination          = 'ELIGIBLE'
             OR me.override_determination = 'ELIGIBLE'
          )
        ORDER BY h.department, full_name
        """,
        (cycle_id,),
    )

    if elig_df.empty:
        st.info(
            "\u2139\ufe0f No eligible employees for this cycle. "
            "Run the Eligibility Engine first, or check that employees hold "
            "an approved performance review with a qualifying rating."
        )
    else:
        # Summary progress
        total_elig      = len(elig_df)
        submitted_count = int(elig_df["rec_id"].notna().sum())
        pct_complete    = submitted_count / total_elig if total_elig > 0 else 0.0

        pm1, pm2 = st.columns([2, 3])
        with pm1:
            st.metric(
                "Recommendations Submitted",
                f"{submitted_count} / {total_elig}",
                delta=f"{pct_complete:.0%} complete",
            )
        with pm2:
            st.progress(
                pct_complete,
                text=f"{pct_complete:.0%} of eligible employees have submissions",
            )

        st.divider()

        # ── One expander per eligible employee ───────────────────────────────
        for _, row in elig_df.iterrows():
            emp_id   = _safe_str(row["employee_id"])
            name     = _safe_str(row["full_name"]) or emp_id
            dept     = _safe_str(row["department"])
            job      = _safe_str(row["job_title"])
            salary   = _safe_float(row["salary"])
            tenure   = _safe_float(row["tenure_in_role_months"])
            rating   = _safe_str(row["rating_overall"]).upper().strip()
            rec_id   = row["rec_id"]
            rec_stat = _safe_str(row["rec_status"]).upper().strip()

            rec_has_rec = not (
                rec_id is None or (isinstance(rec_id, float) and pd.isna(rec_id))
            )
            show_form = (not rec_has_rec) or (rec_stat == "REJECTED")

            rating_color = (
                GREEN  if rating == "EXCEEDS"
                else ACCENT if rating == "MEETS"
                else MUTED
            )
            rating_label = rating if rating else "No Rating"

            rec_status_colors = {
                "SUBMITTED":     ACCENT,
                "HR_APPROVED":   GREEN,
                "REJECTED":      AMBER,
                "CHRO_APPROVED": GOLD,
                "PENDING":       MUTED,
            }

            exp_label = (
                f"{name}  \u2014  {dept}  \u2014  {job}  \u2014  "
                f"Current salary: {_fmt_currency(salary)}"
            )

            with st.expander(exp_label, expanded=False):
                # Context strip — rating | tenure | rec status badge
                ctx1, ctx2, ctx3 = st.columns(3)
                with ctx1:
                    st.markdown(
                        f'<span style="background:{rating_color};color:#FFFFFF;'
                        f'font-size:0.82rem;font-weight:700;'
                        f'padding:3px 10px;border-radius:999px;">'
                        f'Rating: {rating_label}</span>',
                        unsafe_allow_html=True,
                    )
                with ctx2:
                    st.caption(f"Tenure in role: **{tenure:.0f}** months")
                with ctx3:
                    if rec_has_rec:
                        badge_color = rec_status_colors.get(rec_stat, MUTED)
                        st.markdown(
                            f'<span style="background:{badge_color};color:#FFFFFF;'
                            f'font-size:0.82rem;font-weight:700;'
                            f'padding:3px 10px;border-radius:999px;">'
                            f'{rec_stat}</span>',
                            unsafe_allow_html=True,
                        )

                st.markdown("")

                # READ-ONLY VIEW — recommendation exists and is not REJECTED
                if rec_has_rec and rec_stat != "REJECTED":
                    ro1, ro2 = st.columns(2)
                    ro1.metric(
                        "Base Increase",
                        f"{_safe_float(row['base_increase_pct']):.1f}%",
                    )
                    ro2.metric(
                        "Flat Bonus",
                        _fmt_currency(row["bonus_amount"]),
                    )
                    just_val = _safe_str(row["rec_justification"])
                    if just_val:
                        st.markdown(f"**Justification:** {just_val}")

                # EDITABLE FORM — no recommendation yet, or RETURNED
                if show_form:
                    prefill_base  = _safe_float(row["base_increase_pct"]) if rec_has_rec else 0.0
                    prefill_bonus = _safe_float(row["bonus_amount"])        if rec_has_rec else 0.0
                    prefill_just  = _safe_str(row["rec_justification"])               if rec_has_rec else ""

                    base_pct = st.number_input(
                        "Base Increase %",
                        min_value=0.0,
                        max_value=15.0,
                        step=0.5,
                        format="%.1f",
                        value=prefill_base,
                        key=f"base_{emp_id}",
                    )
                    bonus_flat = st.number_input(
                        "Flat Bonus ($)",
                        min_value=0.0,
                        step=100.0,
                        format="%.0f",
                        value=prefill_bonus,
                        key=f"bonus_{emp_id}",
                    )
                    justification = st.text_area(
                        "Justification",
                        height=80,
                        placeholder=(
                            "Required if 0% base increase and $0 bonus. "
                            "Explain the rationale."
                        ),
                        value=prefill_just,
                        key=f"just_{emp_id}",
                    )

                    if st.button("Submit", type="primary", key=f"submit_{emp_id}"):
                        # Validation: justification required when both amounts are 0
                        if base_pct == 0.0 and bonus_flat == 0.0 and not justification.strip():
                            st.error(
                                "Justification is required when both Base Increase "
                                "and Flat Bonus are zero."
                            )
                        else:
                            try:
                                if rec_has_rec:
                                    # REJECTED status — UPDATE existing record
                                    run_mutation(
                                        """
                                        UPDATE merit_recommendations
                                           SET base_increase_pct = %s,
                                               bonus_amount        = %s,
                                               justification_note  = %s,
                                               status                        = 'SUBMITTED',
                                               submitted_at                  = NOW()
                                         WHERE id::text = %s
                                        """,
                                        (
                                            base_pct,
                                            bonus_flat,
                                            justification.strip(),
                                            str(rec_id),
                                        ),
                                    )
                                else:
                                    # No prior record — INSERT new recommendation
                                    run_mutation(
                                        """
                                        INSERT INTO merit_recommendations
                                            (cycle_id, employee_id, manager_id,
                                             base_increase_pct,
                                             bonus_amount,
                                             justification_note, status, submitted_at)
                                        VALUES
                                            (%s::uuid, %s, %s::uuid,
                                             %s, %s, %s,
                                             'SUBMITTED', NOW())
                                        """,
                                        (
                                            cycle_id,
                                            emp_id,
                                            _SYSTEM_USER,
                                            base_pct,
                                            bonus_flat,
                                            justification.strip(),
                                        ),
                                    )
                                query_df.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Database error: {e}")
