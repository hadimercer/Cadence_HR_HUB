import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
from utils.db import query_df, run_mutation

st.set_page_config(page_title="WF2 \u2014 Merit Cycle", layout="wide")

# ── Constants ─────────────────────────────────────────────────────────────────
_SYSTEM_USER   = "2ad731c3-80c2-4848-a29d-e14361113cfb"
CYCLE_STATUSES = ["DRAFT", "OPEN", "CLOSED", "COMPLETE"]

# Colors — CADENCE.md Section 5
ACCENT  = "#4DB6AC"
GOLD    = "#D4A843"
RED     = "#E05252"
AMBER   = "#E8A838"
GREEN   = "#2ECC7A"
TEXT    = "#FAFAFA"
SURFACE = "#262730"
MUTED   = "#8892A4"

REC_STATUS_COLORS = {
    "PENDING":       MUTED,
    "SUBMITTED":     ACCENT,
    "HR_APPROVED":   GREEN,
    "RETURNED":      AMBER,
    "CHRO_APPROVED": GOLD,
}
CYCLE_BADGE_COLORS = {
    "DRAFT":    MUTED,
    "OPEN":     GREEN,
    "CLOSED":   AMBER,
    "COMPLETE": ACCENT,
}


# ── Helpers ───────────────────────────────────────────────────────────────────
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


def _dark(fig):
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT),
        legend=dict(font=dict(color=TEXT)),
    )
    fig.update_xaxes(gridcolor=SURFACE)
    fig.update_yaxes(gridcolor=SURFACE)
    return fig


def _days_pill(deadline_date: datetime.date) -> str:
    days = (deadline_date - datetime.date.today()).days
    if days > 7:
        color, label = GREEN, f"{days} days remaining"
    elif days >= 3:
        color, label = AMBER, f"{days} days remaining"
    elif days >= 0:
        color, label = RED, f"{days} days remaining \u2014 URGENT"
    else:
        color, label = RED, "DEADLINE PASSED"
    return (
        f'<span style="background:{color};color:#FFFFFF;'
        f'padding:2px 10px;border-radius:999px;'
        f'font-size:0.82rem;font-weight:600;">{label}</span>'
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────
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

# ── Header ────────────────────────────────────────────────────────────────────
st.title("WF2 \u2014 Merit Cycle")
st.caption(
    "Cycle management \u00b7 Budget utilisation \u00b7 Eligibility \u00b7 Recommendations"
)
st.divider()

tab_active, tab_admin, tab_hist = st.tabs(
    ["Active Cycle", "Cycle Admin", "Cycle History"]
)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — Active Cycle
# ═════════════════════════════════════════════════════════════════════════════
with tab_active:
    st.subheader("Active Cycle")

    active_df = query_df(
        "SELECT * FROM merit_cycles "
        "WHERE status = 'OPEN' ORDER BY opened_at DESC LIMIT 1"
    )

    if active_df.empty:
        st.info(
            "\u2139\ufe0f No active merit cycle. "
            "Use the \u2018Cycle Admin\u2019 tab to open a new cycle."
        )
    else:
        row          = active_df.iloc[0]
        cycle_id     = str(row["id"])
        cycle_label  = _safe_str(row["cycle_label"])
        cycle_period = _safe_str(row["cycle_period"])
        emp_group    = _safe_str(row["employee_group"])
        total_budget = _safe_float(row["total_budget"])

        try:
            deadline_date = pd.Timestamp(row["submission_deadline"]).date()
        except Exception:
            deadline_date = datetime.date.today()

        # ── Cycle header ──────────────────────────────────────────────────────
        pill_html = _days_pill(deadline_date)
        st.markdown(
            f'<div style="background:{SURFACE};border-radius:0.6rem;'
            f'padding:1.2rem 1.5rem;margin-bottom:1.2rem;">'
            f'<div style="font-size:1.6rem;font-weight:700;color:{ACCENT};'
            f'margin-bottom:0.3rem;">{cycle_label}</div>'
            f'<div style="color:{TEXT};font-size:0.9rem;margin-bottom:0.5rem;">'
            f'Period: {cycle_period} &nbsp;&middot;&nbsp; Group: {emp_group}</div>'
            f'<div style="display:flex;align-items:center;gap:0.75rem;'
            f'margin-bottom:0.4rem;">'
            f'<span style="color:{TEXT};">'
            f'Deadline: {deadline_date.strftime("%d %b %Y")}</span>'
            f'{pill_html}</div>'
            f'<div style="color:{MUTED};font-size:0.85rem;">Total Budget: '
            f'<strong style="color:{GOLD};">{_fmt_currency(total_budget)}</strong>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        # ── Budget utilisation metrics ────────────────────────────────────────
        util_df = query_df(
            "SELECT "
            "COUNT(*) FILTER (WHERE mr.status IN "
            "  ('SUBMITTED','HR_APPROVED','CHRO_APPROVED')) AS submitted_count, "
            "COUNT(*) FILTER (WHERE mr.status = 'PENDING') AS pending_count, "
            "SUM(mr.recommended_base_increase_pct * h.salary / 100) "
            "  FILTER (WHERE mr.status IN "
            "  ('HR_APPROVED','CHRO_APPROVED')) AS approved_spend, "
            "COUNT(DISTINCT mr.employee_id) AS total_in_scope "
            "FROM merit_recommendations mr "
            "JOIN headcount_snapshots h ON h.employee_id = mr.employee_id "
            "  AND h.reporting_period = "
            "    (SELECT MAX(reporting_period) FROM headcount_snapshots) "
            "WHERE mr.cycle_id = %s::uuid",
            (cycle_id,),
        )

        submitted_count = 0
        pending_count   = 0
        approved_spend  = 0.0

        if not util_df.empty:
            submitted_count = int(_safe_float(util_df["submitted_count"].iloc[0]))
            pending_count   = int(_safe_float(util_df["pending_count"].iloc[0]))
            approved_spend  = _safe_float(util_df["approved_spend"].iloc[0])

        pct_used         = (approved_spend / total_budget * 100) if total_budget > 0 else 0.0
        budget_remaining = total_budget - approved_spend

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Recommendations Submitted", submitted_count)
        mc2.metric("Pending Manager Input", pending_count)
        mc3.metric("Approved Spend", _fmt_currency(approved_spend))
        mc4.metric(
            "Budget Remaining",
            _fmt_currency(budget_remaining),
            delta=f"{pct_used:.0f}% utilised",
            delta_color="inverse",
        )

        st.divider()

        # ── Charts ────────────────────────────────────────────────────────────
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            elig_df = query_df(
                "SELECT determination, COUNT(*) AS count "
                "FROM merit_eligibility "
                "WHERE cycle_id = %s::uuid GROUP BY determination",
                (cycle_id,),
            )
            if not elig_df.empty:
                fig_elig = px.bar(
                    elig_df,
                    x="count",
                    y="determination",
                    orientation="h",
                    text="count",
                    color="determination",
                    color_discrete_map={"ELIGIBLE": GREEN, "INELIGIBLE": RED},
                    title=f"Eligibility Breakdown \u2014 {cycle_label}",
                    labels={"count": "Employees", "determination": ""},
                )
                _dark(fig_elig)
                fig_elig.update_traces(textposition="outside")
                fig_elig.update_layout(showlegend=False)
                st.plotly_chart(fig_elig, use_container_width=True)
            else:
                st.info("\u2139\ufe0f No eligibility data for this cycle.")

        with chart_col2:
            rec_status_df = query_df(
                "SELECT status, COUNT(*) AS count "
                "FROM merit_recommendations "
                "WHERE cycle_id = %s::uuid GROUP BY status",
                (cycle_id,),
            )
            if not rec_status_df.empty:
                fig_donut = px.pie(
                    rec_status_df,
                    values="count",
                    names="status",
                    hole=0.45,
                    title="Recommendation Status",
                    color="status",
                    color_discrete_map=REC_STATUS_COLORS,
                )
                _dark(fig_donut)
                fig_donut.update_traces(textfont_color=TEXT)
                st.plotly_chart(fig_donut, use_container_width=True)
            else:
                st.info("\u2139\ufe0f No recommendation data for this cycle.")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — Cycle Admin
# ═════════════════════════════════════════════════════════════════════════════
with tab_admin:
    st.subheader("Cycle Administration")

    # Single query shared by both Section A and Section B
    open_check_df = query_df(
        "SELECT id, cycle_label FROM merit_cycles WHERE status = 'OPEN' LIMIT 1"
    )
    has_open   = not open_check_df.empty
    open_label = _safe_str(open_check_df["cycle_label"].iloc[0]) if has_open else ""
    open_id    = str(open_check_df["id"].iloc[0]) if has_open else ""

    # ── Section A — Open New Cycle ────────────────────────────────────────────
    st.markdown("#### Open New Cycle")

    if has_open:
        st.warning(
            f"An active cycle is already open: **{open_label}**. "
            "Close it before opening a new one."
        )
    else:
        with st.form("open_cycle_form"):
            cycle_label_in = st.text_input(
                "Cycle Label", placeholder="e.g. 2026 H2 Merit"
            )
            cycle_period_in = st.selectbox(
                "Period", ["2026-H1", "2026-H2", "2027-H1", "2027-H2"]
            )
            employee_group_in = st.selectbox(
                "Employee Group", ["All Employees", "General", "Sales"]
            )
            total_budget_in = st.number_input(
                "Total Budget ($)", min_value=0.0, step=1000.0
            )
            deadline_in = st.date_input(
                "Submission Deadline",
                value=datetime.date.today() + datetime.timedelta(days=21),
            )
            open_btn = st.form_submit_button("Open Cycle", type="primary")

        if open_btn:
            if not cycle_label_in.strip():
                st.error("Cycle label cannot be empty.")
            elif total_budget_in <= 0:
                st.error("Total budget must be greater than zero.")
            else:
                try:
                    run_mutation(
                        "INSERT INTO merit_cycles "
                        "(cycle_label, cycle_period, employee_group, status, "
                        "submission_deadline, total_budget, opened_by, opened_at) "
                        "VALUES (%s, %s, %s, 'OPEN', %s, %s, %s::uuid, NOW())",
                        (
                            cycle_label_in.strip(),
                            cycle_period_in,
                            employee_group_in,
                            str(deadline_in),
                            total_budget_in,
                            _SYSTEM_USER,
                        ),
                    )
                    query_df.clear()
                    st.success(
                        f"\u2713 Cycle \u2018{cycle_label_in.strip()}\u2019 "
                        "opened successfully."
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Database error: {str(e)}")

    # ── Section B — Close Active Cycle ───────────────────────────────────────
    if has_open:
        st.divider()
        st.markdown("#### Close Active Cycle")
        st.warning(
            f"Closing **\u2018{open_label}\u2019** will prevent further "
            "manager submissions."
        )
        if st.button("Close Cycle", key="close_cycle_btn"):
            try:
                run_mutation(
                    "UPDATE merit_cycles SET status='CLOSED', closed_at=NOW() "
                    "WHERE id = %s::uuid",
                    (open_id,),
                )
                query_df.clear()
                st.success(f"\u2713 Cycle \u2018{open_label}\u2019 has been closed.")
                st.rerun()
            except Exception as e:
                st.error(f"Database error: {str(e)}")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — Cycle History
# ═════════════════════════════════════════════════════════════════════════════
with tab_hist:
    st.subheader("Cycle History")
    st.caption("Full audit trail of all merit cycles")

    hist_df = query_df(
        "SELECT mc.id, mc.cycle_label, mc.cycle_period, mc.employee_group, "
        "mc.status, mc.submission_deadline, mc.total_budget, "
        "mc.opened_at, mc.closed_at, "
        "COALESCE(u.full_name, '') AS opened_by_name "
        "FROM merit_cycles mc "
        "LEFT JOIN users u ON u.id = mc.opened_by "
        "ORDER BY mc.opened_at DESC"
    )

    if hist_df.empty:
        st.info("\u2139\ufe0f No cycles found.")
    else:
        display_df = hist_df.copy()

        # Format date/numeric columns
        display_df["submission_deadline"] = pd.to_datetime(
            display_df["submission_deadline"], errors="coerce"
        ).dt.strftime("%d %b %Y")
        display_df["opened_at"] = pd.to_datetime(
            display_df["opened_at"], errors="coerce"
        ).dt.strftime("%d %b %Y %H:%M")
        display_df["closed_at"] = pd.to_datetime(
            display_df["closed_at"], errors="coerce"
        ).dt.strftime("%d %b %Y %H:%M")
        display_df["total_budget"] = display_df["total_budget"].apply(_fmt_currency)

        display_df = display_df.rename(
            columns={
                "cycle_label":         "Label",
                "cycle_period":        "Period",
                "employee_group":      "Group",
                "status":              "Status",
                "submission_deadline": "Deadline",
                "total_budget":        "Budget",
                "opened_by_name":      "Opened By",
                "opened_at":           "Opened At",
                "closed_at":           "Closed At",
            }
        )
        display_df = display_df.drop(columns=["id"], errors="ignore")

        def _style_cycle_status(val):
            color = CYCLE_BADGE_COLORS.get(str(val), "")
            if color:
                return f"background-color: {color}; color: #FFFFFF; font-weight: 600;"
            return ""

        styled = display_df.style.map(_style_cycle_status, subset=["Status"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Budget by cycle chart — only when > 1 cycle exists
        if len(hist_df) > 1:
            chart_df = hist_df.copy()
            chart_df["budget_num"] = chart_df["total_budget"].apply(_safe_float)
            chart_df = chart_df.sort_values("opened_at", ascending=True)

            fig_budget = px.bar(
                chart_df,
                x="cycle_label",
                y="budget_num",
                title="Merit Budget by Cycle",
                color_discrete_sequence=[GOLD],
                text="budget_num",
                labels={"cycle_label": "Cycle", "budget_num": "Budget ($)"},
            )
            _dark(fig_budget)
            fig_budget.update_traces(
                texttemplate="$%{text:,.0f}", textposition="outside"
            )
            st.plotly_chart(fig_budget, use_container_width=True)
