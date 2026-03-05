import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from utils.db import query_df, run_mutation

def page_header(title, subtitle=""):
    sub = f'<p style="color:rgba(255,255,255,0.82); font-size:0.95rem; margin:0;">{subtitle}</p>' if subtitle else ""
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,#1B4F72 0%,#2E86C1 100%);
                border-radius:0.6rem;padding:1rem 1.4rem 0.9rem;margin-bottom:1.2rem;">
      <h1 style="color:#FFFFFF;font-size:1.8rem;font-weight:700;
                 margin:0 0 0.2rem 0;line-height:1.2;">{title}</h1>
      {sub}
    </div>""", unsafe_allow_html=True)


st.set_page_config(page_title="Weekly 1:1s \u2014 Cadence", layout="wide")

_SYSTEM_USER = "2ad731c3-80c2-4848-a29d-e14361113cfb"


def _week_start_label() -> str:
    """Return current ISO week start (Monday) as a readable string."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%d %b %Y")


def _safe_str(val) -> str:
    """Return val as string, empty string on None/NaN."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val)


# ── Sidebar ───────────────────────────────────────────────────────────────────
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

page_header("Weekly 1:1s", "Structured capture of weekly check-ins. Missed meeting alerts at 14 days.")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_log, tab_history = st.tabs(["Log 1:1", "History & Alerts"])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — Log 1:1
# ═════════════════════════════════════════════════════════════════════════════
with tab_log:
    st.subheader("Log a 1:1")
    st.caption(f"Current week starts: **{_week_start_label()}**")

    # Load active employees from latest headcount period
    employees_df = query_df(
        "SELECT employee_id, first_name || ' ' || last_name AS full_name "
        "FROM headcount_snapshots "
        "WHERE reporting_period = (SELECT MAX(reporting_period) FROM headcount_snapshots) "
        "AND status = 'ACTIVE' "
        "ORDER BY last_name, first_name"
    )

    if employees_df.empty:
        st.info(
            "\u2139\ufe0f No active employees found. "
            "Upload a headcount CSV via WF1 \u2014 Data Upload first."
        )
    else:
        # ── Employee selector ─────────────────────────────────────────────────
        emp_labels = ["— Select employee —"] + employees_df["full_name"].tolist()
        emp_id_map = dict(
            zip(employees_df["full_name"], employees_df["employee_id"])
        )

        selected_name = st.selectbox("Employee", options=emp_labels)

        if selected_name == "— Select employee —":
            st.info("Select an employee above to log a 1:1.")
        else:
            selected_emp_id = emp_id_map[selected_name]

            # ── Fetch existing record for current week ────────────────────────
            existing_df = query_df(
                "SELECT id, employee_topics, agreed_actions, blockers_raised, "
                "sentiment_flag, status, manager_submitted_at "
                "FROM one_on_ones "
                "WHERE employee_id = %s "
                "AND week_start_date = date_trunc('week', CURRENT_DATE)::date",
                (selected_emp_id,),
            )

            # ── Show employee topic if submitted ──────────────────────────────
            if not existing_df.empty:
                topic = _safe_str(existing_df["employee_topics"].iloc[0])
                if topic:
                    st.info(f"\U0001f4ac **Employee topic for this week:** {topic}")
                else:
                    st.caption("No topic submitted by employee for this week.")

                current_status = _safe_str(existing_df["status"].iloc[0])
                if current_status == "COMPLETED":
                    st.success(
                        "\u2713 This 1:1 is already logged as COMPLETED. "
                        "You can update it below."
                    )
            else:
                st.caption("No record exists for this employee this week.")

            # ── Pre-fill form values if an existing record is present ─────────
            prefill_actions  = ""
            prefill_blockers = ""
            prefill_sent_idx = 1  # Default: NEUTRAL

            if not existing_df.empty:
                prefill_actions  = _safe_str(existing_df["agreed_actions"].iloc[0])
                prefill_blockers = _safe_str(existing_df["blockers_raised"].iloc[0])
                raw_s = _safe_str(existing_df["sentiment_flag"].iloc[0])
                prefill_sent_idx = {"POSITIVE": 0, "NEUTRAL": 1, "CONCERNING": 2}.get(
                    raw_s, 1
                )

            # ── Form ──────────────────────────────────────────────────────────
            with st.form("log_1on1_form", clear_on_submit=False):
                agreed_actions = st.text_area(
                    "Agreed Actions",
                    value=prefill_actions,
                    help="Key outcomes and next steps agreed during this 1:1.",
                    height=120,
                )
                blockers_raised = st.text_area(
                    "Blockers Raised (optional)",
                    value=prefill_blockers,
                    help="Any blockers or concerns raised by the employee.",
                    height=100,
                )
                sentiment_flag = st.selectbox(
                    "Overall Sentiment",
                    options=["POSITIVE", "NEUTRAL", "CONCERNING"],
                    index=prefill_sent_idx,
                    help="Manager's assessment of employee engagement in this conversation.",
                )
                submit_btn = st.form_submit_button("Submit 1:1", type="primary")

            if submit_btn:
                blockers_val = (
                    blockers_raised.strip() if blockers_raised.strip() else None
                )

                try:
                    if existing_df.empty:
                        run_mutation(
                            "INSERT INTO one_on_ones "
                            "(id, employee_id, manager_id, week_start_date, status, "
                            "agreed_actions, blockers_raised, sentiment_flag, "
                            "manager_submitted_at) "
                            "VALUES (gen_random_uuid(), %s, %s::uuid, "
                            "date_trunc('week', CURRENT_DATE)::date, "
                            "'COMPLETED', %s, %s, %s, NOW())",
                            (
                                selected_emp_id,
                                _SYSTEM_USER,
                                agreed_actions,
                                blockers_val,
                                sentiment_flag,
                            ),
                        )
                    else:
                        record_id = str(existing_df["id"].iloc[0])
                        run_mutation(
                            "UPDATE one_on_ones "
                            "SET status = 'COMPLETED', agreed_actions = %s, "
                            "blockers_raised = %s, sentiment_flag = %s, "
                            "manager_submitted_at = NOW() "
                            "WHERE id = %s::uuid",
                            (agreed_actions, blockers_val, sentiment_flag, record_id),
                        )

                    query_df.clear()
                    st.success(
                        f"\u2713 1:1 logged for **{selected_name}** "
                        f"\u00b7 Week of {_week_start_label()} "
                        f"\u00b7 Status: COMPLETED"
                    )
                    st.rerun()

                except Exception as e:
                    st.error(f"Database error: {str(e)}")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — History & Alerts
# ═════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.subheader("Completion Alerts")

    # ── Alert: employees with no COMPLETED 1:1 in the last 14 calendar days ──
    overdue_df = query_df(
        "SELECT hs.employee_id, "
        "hs.first_name || ' ' || hs.last_name AS employee_name "
        "FROM headcount_snapshots hs "
        "WHERE hs.reporting_period = "
        "  (SELECT MAX(reporting_period) FROM headcount_snapshots) "
        "AND hs.status = 'ACTIVE' "
        "AND hs.employee_id NOT IN ( "
        "  SELECT DISTINCT o.employee_id "
        "  FROM one_on_ones o "
        "  WHERE o.status = 'COMPLETED' "
        "  AND o.week_start_date >= CURRENT_DATE - INTERVAL '14 days' "
        ") "
        "ORDER BY employee_name"
    )

    # ── Bubble: count only ────────────────────────────────────────────────────
    if not overdue_df.empty:
        st.warning(
            f"\u26a0\ufe0f **{len(overdue_df)} employee(s)** have no completed 1:1 "
            f"in the last 14 days."
        )
    else:
        st.success(
            "\u2713 All active employees have a completed 1:1 within the last 14 days."
        )

    # ── Alert detail table ────────────────────────────────────────────────────
    if not overdue_df.empty:
        overdue_ids = overdue_df["employee_id"].tolist()

        # Manager name + total missed count per overdue employee
        alert_detail_df = query_df(
            "SELECT hs.employee_id, "
            "hs.first_name || ' ' || hs.last_name AS employee_name, "
            "COALESCE(u.full_name, 'Unassigned') AS manager_name, "
            "COALESCE(missed_ct.cnt, 0) AS total_missed "
            "FROM headcount_snapshots hs "
            "LEFT JOIN LATERAL ( "
            "  SELECT o.manager_id FROM one_on_ones o "
            "  WHERE o.employee_id = hs.employee_id "
            "  ORDER BY o.week_start_date DESC LIMIT 1 "
            ") latest ON true "
            "LEFT JOIN users u ON u.id = latest.manager_id "
            "LEFT JOIN LATERAL ( "
            "  SELECT COUNT(*) AS cnt FROM one_on_ones o "
            "  WHERE o.employee_id = hs.employee_id AND o.status = 'MISSED' "
            ") missed_ct ON true "
            "WHERE hs.reporting_period = "
            "  (SELECT MAX(reporting_period) FROM headcount_snapshots) "
            "AND hs.status = 'ACTIVE' "
            "AND hs.employee_id NOT IN ( "
            "  SELECT DISTINCT employee_id FROM one_on_ones "
            "  WHERE status = 'COMPLETED' "
            "  AND week_start_date >= CURRENT_DATE - INTERVAL '14 days' "
            ") "
            "ORDER BY employee_name"
        )

        if not alert_detail_df.empty:
            # Fetch ordered statuses to compute consecutive missed streak in Python
            ph = ",".join(["%s"] * len(overdue_ids))
            streak_df = query_df(
                f"SELECT employee_id, status FROM one_on_ones "
                f"WHERE employee_id IN ({ph}) "
                f"ORDER BY employee_id, week_start_date DESC",
                tuple(overdue_ids),
            )

            def _consecutive_missed(emp_id):
                rows = streak_df[streak_df["employee_id"] == emp_id]["status"].tolist()
                count = 0
                for s in rows:
                    if s == "MISSED":
                        count += 1
                    else:
                        break
                return count

            alert_detail_df["consecutive_missed"] = (
                alert_detail_df["employee_id"].apply(_consecutive_missed)
            )

            display_alert = alert_detail_df[
                ["employee_name", "manager_name", "consecutive_missed", "total_missed"]
            ].rename(columns={
                "employee_name":     "Employee",
                "manager_name":      "Manager",
                "consecutive_missed": "Successive Missed",
                "total_missed":      "Total Missed",
            })

            st.dataframe(display_alert, use_container_width=True, hide_index=True)

    st.divider()

    # ── Missed 1:1 History — by month by manager (stacked bar) ───────────────
    st.subheader("Missed 1:1 History — By Month & Manager")

    missed_hist_df = query_df(
        "SELECT "
        "  TO_CHAR(DATE_TRUNC('month', o.week_start_date), 'Mon YYYY') AS month_label, "
        "  DATE_TRUNC('month', o.week_start_date) AS month_date, "
        "  COALESCE(u.full_name, 'Unknown') AS manager_name, "
        "  COUNT(*) AS missed_count "
        "FROM one_on_ones o "
        "JOIN users u ON u.id = o.manager_id "
        "WHERE o.status = 'MISSED' "
        "GROUP BY DATE_TRUNC('month', o.week_start_date), u.full_name "
        "ORDER BY month_date, manager_name"
    )

    if missed_hist_df.empty:
        st.info("\u2139\ufe0f No missed 1:1 records found to chart.")
    else:
        missed_hist_df["month_date"] = pd.to_datetime(missed_hist_df["month_date"])
        month_order = (
            missed_hist_df.sort_values("month_date")["month_label"].unique().tolist()
        )
        managers = sorted(missed_hist_df["manager_name"].unique().tolist())

        _MANAGER_COLORS = [
            "#4DB6AC", "#FF7043", "#8E44AD", "#F39C12",
            "#2E86C1", "#27AE60", "#E74C3C", "#D4A843",
        ]
        _ST_TEXT = "#FAFAFA"

        fig_missed = go.Figure()
        for i, mgr in enumerate(managers):
            mgr_data = missed_hist_df[missed_hist_df["manager_name"] == mgr]
            mgr_map = dict(zip(mgr_data["month_label"], mgr_data["missed_count"]))
            y_vals = [int(mgr_map.get(m, 0)) for m in month_order]
            fig_missed.add_trace(go.Bar(
                name=mgr,
                x=month_order,
                y=y_vals,
                marker_color=_MANAGER_COLORS[i % len(_MANAGER_COLORS)],
            ))

        fig_missed.update_layout(
            barmode="stack",
            title=dict(
                text="<b>Missed 1:1s by Month & Manager</b>",
                font=dict(size=14, color=_ST_TEXT, family="Arial"),
                x=0.5, xanchor="center", pad=dict(b=10),
            ),
            xaxis=dict(
                title=dict(text="Month", font=dict(color=_ST_TEXT, size=12)),
                tickfont=dict(color=_ST_TEXT, size=11),
                showgrid=False,
                linecolor="rgba(255,255,255,0.35)", linewidth=1,
            ),
            yaxis=dict(
                title=dict(text="Missed 1:1s", font=dict(color=_ST_TEXT, size=12)),
                tickfont=dict(color=_ST_TEXT, size=11),
                gridcolor="rgba(255,255,255,0.08)", gridwidth=1,
                linecolor="rgba(255,255,255,0.35)",
                dtick=1,
            ),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.04,
                xanchor="center", x=0.5,
                font=dict(color=_ST_TEXT, size=11),
                bgcolor="rgba(255,255,255,0.06)",
                bordercolor="rgba(255,255,255,0.15)", borderwidth=1,
            ),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            height=380,
            margin=dict(t=95, b=55, l=65, r=30),
            font=dict(family="Arial, sans-serif", color=_ST_TEXT),
            hoverlabel=dict(
                bgcolor="#1E2530",
                font_color=_ST_TEXT,
                bordercolor="rgba(255,255,255,0.2)",
            ),
        )
        st.plotly_chart(fig_missed, use_container_width=True, key="chart_missed_by_month")

    st.divider()
    st.subheader("Last 8 Weeks — 1:1 Records")

    # ── History table: last 56 days ───────────────────────────────────────────
    history_df = query_df(
        "SELECT "
        "  hs.first_name || ' ' || hs.last_name AS employee_name, "
        "  o.week_start_date AS week_start, "
        "  o.status, "
        # EMPLOYEE ROLE: sentiment_flag excluded at query layer — WF4-FR-004
        "  o.sentiment_flag, "
        "  o.manager_submitted_at AS submitted "
        "FROM one_on_ones o "
        "JOIN headcount_snapshots hs "
        "  ON hs.employee_id = o.employee_id "
        "  AND hs.reporting_period = "
        "    (SELECT MAX(reporting_period) FROM headcount_snapshots) "
        "WHERE o.week_start_date >= CURRENT_DATE - INTERVAL '56 days' "
        "ORDER BY o.week_start_date DESC, hs.last_name, hs.first_name"
    )

    if history_df.empty:
        st.info("\u2139\ufe0f No 1:1 records found in the last 8 weeks.")
    else:
        # Format date columns before renaming
        history_df["week_start"] = pd.to_datetime(
            history_df["week_start"]
        ).dt.strftime("%d %b %Y")
        history_df["submitted"] = pd.to_datetime(
            history_df["submitted"], errors="coerce"
        ).dt.strftime("%d %b %Y %H:%M")

        # Rename for display
        history_df = history_df.rename(
            columns={
                "employee_name": "Employee",
                "week_start":    "Week",
                "status":        "Status",
                "sentiment_flag": "Sentiment",
                "submitted":     "Submitted",
            }
        )

        # Style MISSED rows with red background + white text
        def _style_missed(row):
            if row["Status"] == "MISSED":
                return [
                    "background-color: #E05252; color: #FFFFFF; font-weight: 600;"
                ] * len(row)
            return [""] * len(row)

        styled = history_df.style.apply(_style_missed, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)
