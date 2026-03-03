"""pages/4_WF4_Monthly_Checkin.py — WF4 Monthly Check-in

Three-tab page:
  Tab 1 — Submit Check-in       (Manager workflow)
  Tab 2 — Acknowledgements      (Employee / HR workflow)
  Tab 3 — Compliance Dashboard  (HR Admin view)
"""

import json
from datetime import date

import pandas as pd
import streamlit as st

from utils.db import query_df, run_mutation

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="WF4 \u2014 Monthly Check-in", layout="wide")

# ─── CONSTANTS ───────────────────────────────────────────────────────────────
_SYSTEM_USER = "2ad731c3-80c2-4848-a29d-e14361113cfb"

ACCENT  = "#4DB6AC"
AMBER   = "#E8A838"
RED     = "#E05252"
GREEN   = "#2ECC7A"
MUTED   = "#8892A4"

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Cadence")
    st.markdown("HR Process Automation Hub")
    st.divider()
    st.markdown("**Workflow Navigation**")
    st.page_link("pages/1_WF1_Data_Upload.py",     label="WF1 \u2014 Data Upload")
    st.page_link("pages/2_WF1_Dashboard.py",        label="WF1 \u2014 KPI Dashboard")
    st.page_link("pages/3_WF4_Weekly_1on1.py",      label="WF4 \u2014 Weekly 1:1")
    st.page_link("pages/4_WF4_Monthly_Checkin.py",  label="WF4 \u2014 Monthly Check-in")
    st.page_link("pages/5_WF4_Quarterly_Review.py", label="WF4 \u2014 Quarterly Review")
    st.page_link("pages/6_WF2_Merit_Cycle.py",      label="WF2 \u2014 Merit Cycle")
    st.page_link("pages/7_WF2_Eligibility.py",      label="WF2 \u2014 Eligibility Engine")
    st.page_link("pages/8_WF3_Risk_Dashboard.py",   label="WF3 \u2014 Risk Dashboard")
    st.page_link("pages/9_WF3_Config.py",           label="WF3 \u2014 Config")

# ─── PAGE HEADER ─────────────────────────────────────────────────────────────
st.title("WF4 \u2014 Monthly Check-in")
st.caption(
    "Submit and acknowledge monthly performance check-ins \u00b7 "
    "Track manager compliance"
)
st.divider()

# ─── TAB CSS (from CLAUDE.md Section 14) ─────────────────────────────────────
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

# ─── CURRENT PERIOD ───────────────────────────────────────────────────────────
today = date.today()
current_period     = date(today.year, today.month, 1)
current_period_str = str(current_period)
current_period_label = today.strftime("%B %Y")
is_past_20th = today.day >= 20

# Prior two months for consecutive-miss calculation (no external deps)
if today.month == 1:
    _m1 = date(today.year - 1, 12, 1)
    _m2 = date(today.year - 1, 11, 1)
elif today.month == 2:
    _m1 = date(today.year, 1, 1)
    _m2 = date(today.year - 1, 12, 1)
else:
    _m1 = date(today.year, today.month - 1, 1)
    _m2 = date(today.year, today.month - 2, 1)

# ─── TABS ────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "Submit Check-in",
    "Acknowledgements",
    "Compliance Dashboard",
])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — SUBMIT CHECK-IN (Manager workflow)
# ═════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader(f"Submit Monthly Check-in — {current_period_label}")
    st.caption("Select a direct report and complete their check-in form for this period.")

    emp_df = query_df("""
        SELECT employee_id, first_name, last_name, department, manager_id
        FROM headcount_snapshots
        WHERE reporting_period = (
            SELECT MAX(reporting_period)
            FROM headcount_snapshots
            WHERE status = 'ACTIVE'
        )
        AND status = 'ACTIVE'
        ORDER BY last_name, first_name
    """)

    if emp_df.empty:
        st.info("No active headcount data found. Upload a headcount CSV on the Data Upload page first.")
    else:
        # Employee selectbox
        emp_labels = [
            f"{r['last_name']}, {r['first_name']}  |  {r['department']}  |  {r['employee_id']}"
            for _, r in emp_df.iterrows()
        ]
        emp_ids = emp_df["employee_id"].tolist()

        selected_label = st.selectbox("Select Employee", emp_labels, key="t1_emp")
        sel_idx    = emp_labels.index(selected_label)
        sel_emp_id = emp_ids[sel_idx]
        sel_row    = emp_df[emp_df["employee_id"] == sel_emp_id].iloc[0]

        mgr_id_raw = sel_row["manager_id"]
        mgr_id = (
            str(mgr_id_raw).strip()
            if (mgr_id_raw is not None and not (isinstance(mgr_id_raw, float) and pd.isna(mgr_id_raw)) and str(mgr_id_raw).strip())
            else _SYSTEM_USER
        )

        st.caption(
            f"Employee: **{sel_row['first_name']} {sel_row['last_name']}** &nbsp;|&nbsp; "
            f"Department: **{sel_row['department']}** &nbsp;|&nbsp; "
            f"ID: **{sel_emp_id}**"
        )

        # Check for an existing check-in this period
        existing_df = query_df("""
            SELECT id, status, goal_progress, key_achievements,
                   development_focus, sentiment_rating, manager_submitted_at
            FROM monthly_checkins
            WHERE employee_id = %s
              AND checkin_period = %s
        """, (sel_emp_id, current_period_str))

        if not existing_df.empty:
            ex = existing_df.iloc[0]
            ex_status = str(ex["status"])

            if ex_status == "ACKED":
                # Guard: already fully acknowledged — block re-submission
                st.info(
                    f"✅ Check-in already acknowledged for {current_period_label}. "
                    "No further action required."
                )
            else:
                # PENDING_ACK — submitted but awaiting employee acknowledgement
                st.warning(
                    f"⚠️ A check-in for this employee has already been submitted for "
                    f"{current_period_label} (status: **{ex_status}**). "
                    "Awaiting acknowledgement in the Acknowledgements tab."
                )
                with st.expander("View submitted check-in details"):
                    try:
                        goals = json.loads(str(ex["goal_progress"] or "{}"))
                    except Exception:
                        goals = {}
                    if goals:
                        st.markdown("**Goal Progress**")
                        for gname, gpct in goals.items():
                            st.markdown(f"- {gname}: **{gpct}%**")
                    st.markdown(f"**Key Achievements**  \n{ex['key_achievements']}")
                    st.markdown(f"**Development Focus**  \n{ex['development_focus']}")
        else:
            # No check-in yet for this employee this period — show submission form
            st.markdown("---")

            goal_entries = []

            with st.form("monthly_checkin_form"):
                st.markdown("**Goal Progress**")
                st.caption("Enter up to 5 goals. Leave Goal Name blank to skip a row.")

                hc1, hc2 = st.columns([3, 1])
                hc1.markdown(
                    '<span style="font-size:0.82rem; color:#8892A4;">Goal Name</span>',
                    unsafe_allow_html=True,
                )
                hc2.markdown(
                    '<span style="font-size:0.82rem; color:#8892A4;">Progress %</span>',
                    unsafe_allow_html=True,
                )

                for i in range(5):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        g_name = st.text_input(
                            label=f"g_name_{i}",
                            key=f"g_name_{i}",
                            placeholder=f"Goal {i + 1}",
                            label_visibility="collapsed",
                        )
                    with c2:
                        g_pct = st.number_input(
                            label=f"g_pct_{i}",
                            key=f"g_pct_{i}",
                            min_value=0,
                            max_value=100,
                            value=0,
                            step=5,
                            label_visibility="collapsed",
                        )
                    goal_entries.append((g_name, g_pct))

                st.markdown("---")

                key_achievements = st.text_area(
                    "Key Achievements *",
                    placeholder="Describe the employee's key achievements this month...",
                    height=110,
                )
                development_focus = st.text_area(
                    "Development Focus *",
                    placeholder="Describe development priorities for the next period...",
                    height=110,
                )
                sentiment_rating = st.selectbox(
                    "Check-in Sentiment",
                    ["POSITIVE", "NEUTRAL", "CONCERNING"],
                )

                form_submitted = st.form_submit_button(
                    "Submit Check-in", type="primary", use_container_width=True
                )

            if form_submitted:
                errors = []
                if not key_achievements.strip():
                    errors.append("Key Achievements is required.")
                if not development_focus.strip():
                    errors.append("Development Focus is required.")

                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    goals_dict = {
                        g_name.strip(): int(g_pct)
                        for g_name, g_pct in goal_entries
                        if g_name.strip()
                    }
                    goal_progress_json = json.dumps(goals_dict)

                    try:
                        run_mutation(
                            """
                            INSERT INTO monthly_checkins
                                (employee_id, manager_id, checkin_period,
                                 goal_progress, key_achievements, development_focus,
                                 sentiment_rating, status, manager_submitted_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING_ACK', NOW())
                            """,
                            (
                                sel_emp_id,
                                mgr_id,
                                current_period_str,
                                goal_progress_json,
                                key_achievements.strip(),
                                development_focus.strip(),
                                sentiment_rating,
                            ),
                        )
                        query_df.clear()
                        st.success(
                            f"✅ Check-in submitted for "
                            f"{sel_row['first_name']} {sel_row['last_name']} "
                            f"— {current_period_label}."
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Database error: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — ACKNOWLEDGEMENTS (Employee / HR workflow)
# ═════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader(f"Pending Acknowledgements — {current_period_label}")
    st.caption("Review submitted check-ins and acknowledge receipt.")

    # EMPLOYEE ROLE: sentiment_rating is hidden from employees in a role-gated
    # implementation. In this phase (no auth), it is shown with an HR-only badge.
    # When Supabase Auth is wired up, gate this field on MANAGER / HR_ADMIN roles.

    pending_df = query_df("""
        SELECT
            mc.id,
            mc.employee_id,
            mc.manager_id,
            mc.key_achievements,
            mc.development_focus,
            mc.sentiment_rating,
            mc.manager_submitted_at,
            (hs_e.first_name || ' ' || hs_e.last_name) AS employee_name,
            (hs_m.first_name || ' ' || hs_m.last_name) AS manager_name
        FROM monthly_checkins mc
        LEFT JOIN headcount_snapshots hs_e
            ON hs_e.employee_id = mc.employee_id
           AND hs_e.reporting_period = (SELECT MAX(reporting_period) FROM headcount_snapshots)
        LEFT JOIN headcount_snapshots hs_m
            ON hs_m.employee_id = mc.manager_id
           AND hs_m.reporting_period = (SELECT MAX(reporting_period) FROM headcount_snapshots)
        WHERE mc.status = 'PENDING_ACK'
          AND mc.checkin_period = %s
        ORDER BY employee_name
    """, (current_period_str,))

    if pending_df.empty:
        st.info(
            f"No pending acknowledgements for {current_period_label}. "
            "All submitted check-ins are up to date."
        )
    else:
        st.markdown(
            f'<div style="color:{MUTED}; font-size:0.9rem; margin-bottom:0.8rem;">'
            f'{len(pending_df)} check-in(s) awaiting acknowledgement</div>',
            unsafe_allow_html=True,
        )

        for _, row in pending_df.iterrows():
            checkin_id = str(row["id"])
            emp_name_raw = row["employee_name"]
            mgr_name_raw = row["manager_name"]
            emp_name = (
                str(emp_name_raw).strip()
                if (emp_name_raw is not None and not (isinstance(emp_name_raw, float) and pd.isna(emp_name_raw)))
                else str(row["employee_id"])
            )
            mgr_name = (
                str(mgr_name_raw).strip()
                if (mgr_name_raw is not None and not (isinstance(mgr_name_raw, float) and pd.isna(mgr_name_raw)))
                else str(row["manager_id"])
            )
            sentiment = str(row["sentiment_rating"])
            sent_color = GREEN if sentiment == "POSITIVE" else AMBER if sentiment == "NEUTRAL" else RED

            with st.expander(f"{emp_name}  |  Manager: {mgr_name}", expanded=False):
                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown("**Key Achievements**")
                    st.write(str(row["key_achievements"]))
                with col_right:
                    st.markdown("**Development Focus**")
                    st.write(str(row["development_focus"]))

                # EMPLOYEE ROLE: sentiment_rating hidden in employee view
                st.markdown(
                    f'<div style="margin-top:0.6rem;">'
                    f'<span style="color:{MUTED}; font-size:0.82rem;">'
                    f'Sentiment (HR view only):</span>&nbsp;'
                    f'<span style="background:{sent_color}; color:#FFFFFF; '
                    f'font-size:0.82rem; font-weight:700; '
                    f'padding:0.15rem 0.55rem; border-radius:999px;">'
                    f'{sentiment}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                st.markdown("")
                if st.button("✓ Acknowledge", key=f"ack_{checkin_id}", type="primary"):
                    run_mutation(
                        """
                        UPDATE monthly_checkins
                        SET status = 'ACKED',
                            employee_acknowledged_at = NOW()
                        WHERE id::text = %s
                        """,
                        (checkin_id,),
                    )
                    query_df.clear()
                    st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — COMPLIANCE DASHBOARD (HR Admin view)
# ═════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader(f"Compliance Dashboard — {current_period_label}")
    st.caption(
        "Manager-level check-in submission compliance. "
        "Overdue = past the 20th of the month with submissions missing."
    )

    # Managers with their direct-report counts from the latest headcount period.
    # LEFT JOIN to resolve manager names from the same headcount snapshot.
    mgr_df = query_df("""
        SELECT
            hs.manager_id,
            COALESCE(mgr.first_name || ' ' || mgr.last_name, hs.manager_id) AS manager_name,
            COUNT(hs.employee_id) AS direct_reports
        FROM headcount_snapshots hs
        LEFT JOIN headcount_snapshots mgr
            ON mgr.employee_id = hs.manager_id
           AND mgr.reporting_period = (SELECT MAX(reporting_period) FROM headcount_snapshots)
        WHERE hs.reporting_period = (SELECT MAX(reporting_period) FROM headcount_snapshots)
          AND hs.status = 'ACTIVE'
          AND hs.manager_id IS NOT NULL
          AND hs.manager_id != ''
        GROUP BY hs.manager_id, mgr.first_name, mgr.last_name
        ORDER BY manager_name
    """)

    if mgr_df.empty:
        st.info("No manager data available. Ensure headcount data has been loaded.")
    else:
        # Check-ins submitted this month (any status counts as submitted)
        submitted_df = query_df("""
            SELECT manager_id, COUNT(*) AS submitted
            FROM monthly_checkins
            WHERE checkin_period = %s
            GROUP BY manager_id
        """, (current_period_str,))

        # Historical check-ins for the two prior months (consecutive-miss check)
        hist_df = query_df("""
            SELECT manager_id, checkin_period, COUNT(*) AS submitted_count
            FROM monthly_checkins
            WHERE checkin_period IN (%s, %s)
            GROUP BY manager_id, checkin_period
        """, (str(_m1), str(_m2)))

        if not hist_df.empty:
            hist_df["checkin_period"] = pd.to_datetime(hist_df["checkin_period"]).dt.date

        # Build one compliance row per manager
        comp_rows = []
        for _, mgr in mgr_df.iterrows():
            mid      = str(mgr["manager_id"]).strip()
            mname    = str(mgr["manager_name"]).strip() if mgr["manager_name"] else mid
            dr_count = int(mgr["direct_reports"])

            if dr_count == 0:
                continue

            # Submitted count for current month
            sub_match = (
                submitted_df[submitted_df["manager_id"] == mid]
                if not submitted_df.empty
                else pd.DataFrame()
            )
            submitted_count = int(sub_match["submitted"].values[0]) if not sub_match.empty else 0

            # Overdue: only flagged after the 20th
            overdue = max(0, dr_count - submitted_count) if is_past_20th else 0

            # Consecutive miss: < 100% completion in both _m1 and _m2
            m1_sub = m2_sub = 0
            if not hist_df.empty:
                r1 = hist_df[(hist_df["manager_id"] == mid) & (hist_df["checkin_period"] == _m1)]
                r2 = hist_df[(hist_df["manager_id"] == mid) & (hist_df["checkin_period"] == _m2)]
                m1_sub = int(r1["submitted_count"].values[0]) if not r1.empty else 0
                m2_sub = int(r2["submitted_count"].values[0]) if not r2.empty else 0

            consecutive_miss = (m1_sub < dr_count) and (m2_sub < dr_count)

            comp_rows.append({
                "Manager":               mname,
                "Direct Reports":        dr_count,
                "Submitted (This Month)": submitted_count,
                "Overdue":               overdue,
                "Consecutive Miss":      consecutive_miss,
            })

        if not comp_rows:
            st.info("No compliance data to display.")
        else:
            comp_df = pd.DataFrame(comp_rows)

            # Summary metric cards
            total_mgrs      = len(comp_df)
            fully_compliant = int((comp_df["Overdue"] == 0).sum())
            pct_compliance  = round(fully_compliant / total_mgrs * 100) if total_mgrs > 0 else 0
            total_overdue   = int(comp_df["Overdue"].sum())

            m_col1, m_col2, m_col3 = st.columns(3)
            m_col1.metric("Total Managers",    total_mgrs)
            m_col2.metric("% Full Compliance", f"{pct_compliance}%")
            m_col3.metric("Total Overdue",     total_overdue)

            st.divider()

            # Conditional row styling: red for consecutive miss, amber for overdue
            def _highlight(row):
                if row["Consecutive Miss"]:
                    return [f"background-color: {RED}; color: #FFFFFF; font-weight: 600;"] * len(row)
                if row["Overdue"] > 0:
                    return [f"background-color: {AMBER}; color: #FFFFFF; font-weight: 600;"] * len(row)
                return [""] * len(row)

            styled = comp_df.style.apply(_highlight, axis=1)
            st.dataframe(styled, use_container_width=True, hide_index=True)

            # Legend
            st.markdown(
                f'<div style="display:flex; gap:1.4rem; margin-top:0.5rem; font-size:0.82rem; color:{MUTED};">'
                f'<span><span style="background:{RED}; color:#FFF; '
                f'padding:0.1rem 0.45rem; border-radius:4px; margin-right:0.3rem;">■</span>'
                f'Consecutive miss (2+ months &lt;100%)</span>'
                f'<span><span style="background:{AMBER}; color:#FFF; '
                f'padding:0.1rem 0.45rem; border-radius:4px; margin-right:0.3rem;">■</span>'
                f'Overdue check-ins this month</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
