import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from utils.db import query_df, run_mutation
from utils.scoring import run_scoring_engine, get_latest_scores, get_score_history

def page_header(title, subtitle=""):
    sub = f'<p style="color:rgba(255,255,255,0.82); font-size:0.95rem; margin:0;">{subtitle}</p>' if subtitle else ""
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,#1B4F72 0%,#2E86C1 100%);
                border-radius:0.6rem;padding:1rem 1.4rem 0.9rem;margin-bottom:1.2rem;">
      <h1 style="color:#FFFFFF;font-size:1.8rem;font-weight:700;
                 margin:0 0 0.2rem 0;line-height:1.2;">{title}</h1>
      {sub}
    </div>""", unsafe_allow_html=True)


st.set_page_config(page_title="Risk Dashboard \u2014 Cadence", layout="wide")

# ── Sidebar ────────────────────────────────────────────────────────────────────
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

# ── Constants ──────────────────────────────────────────────────────────────────
_SYSTEM_USER = "2ad731c3-80c2-4848-a29d-e14361113cfb"
RAG_COLORS   = {"RED": "#E05252", "AMBER": "#E8A838", "GREEN": "#2ECC7A"}
RAG_ORDER    = ["RED", "AMBER", "GREEN"]

ACCENT  = "#4DB6AC"
GOLD    = "#D4A843"
RED     = "#E05252"
AMBER   = "#E8A838"
GREEN   = "#2ECC7A"
TEXT    = "#FAFAFA"
SURFACE = "#262730"
MUTED   = "#8892A4"

# factor_code / score column → human-readable label
FACTOR_LABELS = {
    "score_compa_ratio":      "Pay Position (Compa-ratio)",
    "score_rating_trend":     "Performance Trend",
    "score_time_since_merit": "Time Since Merit Increase",
    "score_time_in_role":     "Time in Role",
    "score_sentiment":        "1:1 Sentiment Trend",
    "score_checkin_freq":     "Check-in Frequency",
    "score_role_risk":        "Flight Risk Role",
}


# ── Helpers ────────────────────────────────────────────────────────────────────
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


def _rag_emoji(rag: str) -> str:
    return {"RED": "\U0001f534", "AMBER": "\U0001f7e1", "GREEN": "\U0001f7e2"}.get(rag, "\u26aa")


# ── Page Header ────────────────────────────────────────────────────────────────
page_header(
    "Attrition Risk Register",
    "Seven-factor rules-based scoring. Ranked register with retention action logging.",
)
_c_btn, _ = st.columns([1, 5])
with _c_btn:
    recalc_clicked = st.button(
        "\U0001f504 Recalculate Scores", use_container_width=True, type="primary"
    )

if recalc_clicked:
    with st.spinner("Running scoring engine..."):
        result = run_scoring_engine()
    st.success(
        f"Complete \u2014 {result['scored']} employees scored.  "
        f"RED: {result['rag_summary'].get('RED', 0)},  "
        f"AMBER: {result['rag_summary'].get('AMBER', 0)},  "
        f"GREEN: {result['rag_summary'].get('GREEN', 0)}"
    )
    if result["errors"]:
        st.warning(f"{len(result['errors'])} error(s) during scoring. Check application logs.")
    query_df.clear()
    st.rerun()

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
TAB1, TAB2, TAB3 = st.tabs(["Risk Register", "Retention Actions", "Score History"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Risk Register
# ══════════════════════════════════════════════════════════════════════════════
with TAB1:
    df = get_latest_scores()

    if df.empty:
        st.info(
            "\u2139\ufe0f No scores calculated yet. Click **\U0001f504 Recalculate Scores** above."
        )
    else:
        # ── Section A: KPI row ─────────────────────────────────────────────
        total       = len(df)
        red_count   = int((df["rag_status"] == "RED").sum())
        amber_count = int((df["rag_status"] == "AMBER").sum())
        green_count = int((df["rag_status"] == "GREEN").sum())

        # Prior day RED (for delta — only if prior data exists)
        prior_df = query_df("""
            SELECT COUNT(*) AS cnt
            FROM (
                SELECT DISTINCT ON (employee_id) employee_id, rag_status
                FROM attrition_risk_scores
                WHERE calculation_date < CURRENT_DATE
                ORDER BY employee_id, calculation_date DESC
            ) sub
            WHERE rag_status = 'RED'
        """)
        prior_red = int(prior_df["cnt"].iloc[0]) if not prior_df.empty else None
        red_delta = (red_count - prior_red) if prior_red is not None else None

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Employees Scored", total)
        k2.metric(
            "\U0001f534 High Risk",
            red_count,
            delta=f"{red_delta:+d}" if red_delta is not None else None,
            delta_color="inverse",
        )
        k3.metric("\U0001f7e1 At Risk", amber_count)
        k4.metric("\U0001f7e2 Low Risk", green_count)

        st.divider()

        # ── Section B: Donut + Department bar ─────────────────────────────
        bc1, bc2 = st.columns(2)

        with bc1:
            fig_donut = go.Figure(data=[go.Pie(
                labels=["HIGH RISK", "AT RISK", "LOW RISK"],
                values=[red_count, amber_count, green_count],
                hole=0.5,
                marker_colors=[RED, AMBER, GREEN],
                textfont_color=TEXT,
            )])
            fig_donut.update_layout(title="Risk Distribution", height=300)
            _dark(fig_donut)
            st.plotly_chart(fig_donut, use_container_width=True, key="chart_donut")

        with bc2:
            dept_avg = (
                df.groupby("department")["composite_score"]
                .mean()
                .sort_values(ascending=False)
                .head(5)
                .reset_index()
            )
            dept_avg.columns = ["Department", "Avg Score"]
            fig_dept = px.bar(
                dept_avg, x="Avg Score", y="Department",
                orientation="h",
                color_discrete_sequence=[AMBER],
            )
            fig_dept.update_layout(
                title="Highest Risk Departments (avg score)",
                xaxis=dict(range=[0, 100], title="Avg Score"),
                yaxis=dict(autorange="reversed"),
                height=300,
                showlegend=False,
            )
            _dark(fig_dept)
            st.plotly_chart(fig_dept, use_container_width=True, key="chart_dept")

        st.divider()

        # ── Section C: Filters ─────────────────────────────────────────────
        fc1, fc2, fc3 = st.columns([1.5, 2, 2])
        with fc1:
            filter_rag = st.multiselect(
                "RAG Status",
                ["RED", "AMBER", "GREEN"],
                default=["RED", "AMBER"],
                key="wf3_filter_rag",
            )
        with fc2:
            dept_options = ["All"] + sorted(df["department"].dropna().unique().tolist())
            filter_dept = st.selectbox(
                "Department", dept_options, key="wf3_filter_dept"
            )
        with fc3:
            filter_name = st.text_input("Search name", key="wf3_filter_name")

        # Apply filters
        filtered = df.copy()
        if filter_rag:
            filtered = filtered[filtered["rag_status"].isin(filter_rag)]
        if filter_dept != "All":
            filtered = filtered[filtered["department"] == filter_dept]
        if filter_name.strip():
            filtered = filtered[
                filtered["full_name"].str.contains(
                    filter_name.strip(), case=False, na=False
                )
            ]
        filtered = filtered.sort_values("composite_score", ascending=False)

        st.caption(f"Showing **{len(filtered)}** of {total} employees")

        # Bulk-load 14-day sparkline data once (single cached query)
        cutoff_14 = str(date.today() - timedelta(days=14))
        spark_df = query_df(
            """
            SELECT employee_id, calculation_date, composite_score
            FROM attrition_risk_scores
            WHERE calculation_date >= %s
            ORDER BY employee_id, calculation_date ASC
            """,
            (cutoff_14,),
        )

        # ── Section D: Risk register expanders ────────────────────────────
        if filtered.empty:
            st.info("\u2139\ufe0f No employees match the selected filters.")
        else:
            for _, row in filtered.iterrows():
                emp_id         = str(row["employee_id"])
                full_name      = _safe_str(row.get("full_name"))
                rag_status     = _safe_str(row.get("rag_status"))
                composite      = _safe_float(row.get("composite_score"))
                department     = _safe_str(row.get("department"))
                job_title      = _safe_str(row.get("job_title"))
                manager_id     = _safe_str(row.get("manager_id"))
                calc_date      = _safe_str(row.get("calculation_date"))
                rag_e          = _rag_emoji(rag_status)

                with st.expander(
                    f"{rag_e} {full_name} \u2014 {department} \u2014 Score: {composite:.0f}"
                ):
                    # Row 1: context fields
                    rc1, rc2, rc3 = st.columns(3)
                    rc1.markdown(f"**Job Title**  \n{job_title or '—'}")
                    rc2.markdown(f"**Manager ID**  \n{manager_id or '—'}")
                    rc3.markdown(f"**Calculated**  \n{calc_date or '—'}")

                    # Factor breakdown bar chart
                    factor_labels = []
                    factor_scores = []
                    factor_colors = []
                    for col, label in FACTOR_LABELS.items():
                        score = _safe_float(row.get(col))
                        factor_labels.append(label)
                        factor_scores.append(score)
                        factor_colors.append(
                            RED if score >= 100 else AMBER if score >= 50 else GREEN
                        )

                    fig_factors = go.Figure(go.Bar(
                        x=factor_scores,
                        y=factor_labels,
                        orientation="h",
                        marker_color=factor_colors,
                        hovertemplate="%{y}: %{x:.0f}<extra></extra>",
                    ))
                    fig_factors.update_layout(
                        xaxis=dict(range=[0, 100], title="Factor Sub-Scores"),
                        height=280,
                        showlegend=False,
                        margin=dict(l=10, r=20, t=20, b=30),
                    )
                    _dark(fig_factors)
                    st.plotly_chart(fig_factors, use_container_width=True, key=f"chart_factors_{emp_id}")

                    # WF3-FR-008: Cross-portfolio pay context
                    st.caption(
                        "\U0001f4a1 Pay Position data sourced from WF1 salary data vs band midpoints. "
                        "For market benchmarking context, see the S2 Compensation Dashboard."
                    )

                    # Retention action flag flow
                    flag_key = f"flag_open_{emp_id}"
                    col_flag, _ = st.columns([2, 3])
                    with col_flag:
                        if st.button(
                            "\U0001f6a9 Flag for Retention Action",
                            key=f"flag_{emp_id}",
                        ):
                            st.session_state[flag_key] = not st.session_state.get(
                                flag_key, False
                            )

                    if st.session_state.get(flag_key):
                        action_desc = st.text_area(
                            "Describe the retention action",
                            key=f"action_desc_{emp_id}",
                            placeholder=(
                                "E.g. Schedule compensation review, discuss promotion "
                                "pathway, connect with L&D team..."
                            ),
                        )
                        col_log, col_cancel_flag = st.columns(2)
                        with col_log:
                            if st.button(
                                "Log Action",
                                key=f"log_action_{emp_id}",
                                type="primary",
                            ):
                                if action_desc.strip():
                                    try:
                                        run_mutation(
                                            """
                                            INSERT INTO retention_actions
                                                (employee_id, flagged_by,
                                                 risk_score_at_flag, rag_at_flag,
                                                 action_description, status)
                                            VALUES (%s, %s::uuid, %s, %s, %s, 'OPEN')
                                            """,
                                            (
                                                emp_id,
                                                _SYSTEM_USER,
                                                composite,
                                                rag_status,
                                                action_desc.strip(),
                                            ),
                                        )
                                        st.success("Retention action logged.")
                                        st.session_state[flag_key] = False
                                        query_df.clear()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Failed to log action: {e}")
                                else:
                                    st.warning("Enter an action description before logging.")
                        with col_cancel_flag:
                            if st.button("Cancel", key=f"cancel_flag_{emp_id}"):
                                st.session_state[flag_key] = False
                                st.rerun()

                    # Score history sparkline (bulk data, no per-employee query)
                    if not spark_df.empty and "employee_id" in spark_df.columns:
                        emp_spark = spark_df[spark_df["employee_id"] == emp_id]
                        if len(emp_spark) > 1:
                            fig_spark = px.line(
                                emp_spark,
                                x="calculation_date",
                                y="composite_score",
                            )
                            fig_spark.update_traces(
                                line_color=RAG_COLORS.get(rag_status, ACCENT),
                                line_width=2,
                            )
                            fig_spark.update_layout(
                                height=120,
                                showlegend=False,
                                margin=dict(l=5, r=5, t=5, b=5),
                                xaxis=dict(showticklabels=False, title=None),
                                yaxis=dict(showticklabels=False, title=None),
                            )
                            _dark(fig_spark)
                            st.plotly_chart(fig_spark, use_container_width=True, key=f"chart_spark_{emp_id}")
                            st.caption("14-day score history")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Retention Actions
# ══════════════════════════════════════════════════════════════════════════════
with TAB2:
    actions_df = query_df("""
        SELECT
            ra.id,
            ra.employee_id,
            ra.flagged_by,
            ra.risk_score_at_flag,
            ra.rag_at_flag,
            ra.action_description,
            ra.status,
            ra.flagged_at,
            ra.resolved_at,
            ra.outcome,
            h.first_name || ' ' || h.last_name  AS full_name,
            h.department,
            h.job_title,
            ars.composite_score AS current_score,
            ars.rag_status      AS current_rag
        FROM retention_actions ra
        JOIN headcount_snapshots h
          ON h.employee_id = ra.employee_id
         AND h.reporting_period = (
             SELECT MAX(reporting_period) FROM headcount_snapshots
         )
        LEFT JOIN LATERAL (
            SELECT composite_score, rag_status
            FROM attrition_risk_scores
            WHERE employee_id = ra.employee_id
            ORDER BY calculation_date DESC
            LIMIT 1
        ) ars ON true
        ORDER BY ra.flagged_at DESC
    """)

    open_df     = actions_df[actions_df["status"] == "OPEN"].copy()     if not actions_df.empty else pd.DataFrame()
    resolved_df = actions_df[actions_df["status"] == "RESOLVED"].copy() if not actions_df.empty else pd.DataFrame()

    # Summary cards
    open_count = len(open_df)

    resolved_this_month = 0
    if not resolved_df.empty and "resolved_at" in resolved_df.columns:
        month_start = date.today().replace(day=1)
        for _, r in resolved_df.iterrows():
            ra = r.get("resolved_at")
            if ra is not None and not (isinstance(ra, float) and pd.isna(ra)):
                try:
                    if pd.Timestamp(ra).date() >= month_start:
                        resolved_this_month += 1
                except Exception:
                    pass

    avg_score_at_flag = "N/A"
    if not open_df.empty and "risk_score_at_flag" in open_df.columns:
        avg_val = open_df["risk_score_at_flag"].mean()
        if not pd.isna(avg_val):
            avg_score_at_flag = f"{avg_val:.1f}"

    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Open Actions", open_count)
    sc2.metric("Resolved This Month", resolved_this_month)
    sc3.metric("Avg Score at Flag", avg_score_at_flag)

    st.divider()

    # ── Open actions ───────────────────────────────────────────────────────
    if open_df.empty:
        st.info(
            "\u2139\ufe0f No open retention actions. Flag employees from the Risk Register tab."
        )
    else:
        st.subheader("Open Actions")
        for _, row in open_df.iterrows():
            ra_id      = str(row["id"])
            full_name  = _safe_str(row.get("full_name"))
            dept       = _safe_str(row.get("department"))
            flagged_at = row.get("flagged_at")
            try:
                flagged_str = pd.Timestamp(flagged_at).strftime("%d %b %Y")
            except Exception:
                flagged_str = _safe_str(flagged_at)

            rag_at_flag   = _safe_str(row.get("rag_at_flag"))
            score_at_flag = _safe_float(row.get("risk_score_at_flag"))
            current_score = row.get("current_score")
            current_rag   = _safe_str(row.get("current_rag"))
            action_text   = _safe_str(row.get("action_description"))

            with st.expander(
                f"{_rag_emoji(rag_at_flag)} {full_name} \u2014 {dept} \u2014 Flagged {flagged_str}"
            ):
                d1, d2, d3 = st.columns(3)
                d1.metric("Score at Flag", f"{score_at_flag:.0f}")

                if current_score is not None and not (
                    isinstance(current_score, float) and pd.isna(current_score)
                ):
                    cs    = float(current_score)
                    delta = cs - score_at_flag
                    d2.metric(
                        "Current Score",
                        f"{cs:.0f}",
                        delta=f"{delta:+.0f}",
                        delta_color="inverse",
                    )
                else:
                    d2.metric("Current Score", "N/A")

                d3.metric("RAG at Flag", f"{_rag_emoji(rag_at_flag)} {rag_at_flag}")

                st.info(f"**Action:** {action_text}")

                # Resolve flow
                resolve_key = f"resolve_open_{ra_id}"
                col_resolve, _ = st.columns([2, 3])
                with col_resolve:
                    if st.button(
                        "\u2705 Mark Resolved", key=f"btn_resolve_{ra_id}"
                    ):
                        st.session_state[resolve_key] = True

                if st.session_state.get(resolve_key):
                    outcome_text = st.text_input(
                        "Outcome note",
                        key=f"outcome_{ra_id}",
                        placeholder="Describe the resolution...",
                    )
                    col_confirm, col_cancel_res = st.columns(2)
                    with col_confirm:
                        if st.button(
                            "Confirm Resolution",
                            key=f"confirm_{ra_id}",
                            type="primary",
                        ):
                            try:
                                run_mutation(
                                    """
                                    UPDATE retention_actions
                                       SET status = 'RESOLVED',
                                           outcome = %s,
                                           resolved_at = NOW()
                                     WHERE id::text = %s
                                    """,
                                    (outcome_text.strip() or None, ra_id),
                                )
                                st.success("Action marked as resolved.")
                                st.session_state[resolve_key] = False
                                query_df.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error resolving action: {e}")
                    with col_cancel_res:
                        if st.button("Cancel", key=f"cancel_resolve_{ra_id}"):
                            st.session_state[resolve_key] = False
                            st.rerun()

    # ── Resolved actions (collapsed) ──────────────────────────────────────
    if not resolved_df.empty:
        st.divider()
        with st.expander(f"Resolved Actions ({len(resolved_df)})"):
            display_cols = [
                c for c in [
                    "full_name", "department", "rag_at_flag",
                    "risk_score_at_flag", "action_description",
                    "outcome", "resolved_at",
                ]
                if c in resolved_df.columns
            ]
            col_rename = {
                "full_name":          "Employee",
                "department":         "Department",
                "rag_at_flag":        "RAG at Flag",
                "risk_score_at_flag": "Score at Flag",
                "action_description": "Action",
                "outcome":            "Outcome",
                "resolved_at":        "Resolved At",
            }
            st.dataframe(
                resolved_df[display_cols].rename(columns=col_rename),
                use_container_width=True,
                hide_index=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Score History
# ══════════════════════════════════════════════════════════════════════════════
with TAB3:
    scores_df = get_latest_scores()

    if scores_df.empty:
        st.info(
            "\u2139\ufe0f No scores available. Run the scoring engine to populate history."
        )
    else:
        # Employee selector (ordered by risk descending so high-risk first)
        emp_options = scores_df["full_name"].tolist()
        sel_name    = st.selectbox("Select Employee", emp_options, key="hist_emp_select")

        sel_id  = scores_df.loc[
            scores_df["full_name"] == sel_name, "employee_id"
        ].iloc[0]
        sel_row = scores_df[scores_df["employee_id"] == sel_id].iloc[0]

        hist = get_score_history(str(sel_id), days=30)

        if hist.empty:
            st.info("\u2139\ufe0f No score history available for this employee.")
        else:
            full_name = _safe_str(sel_row.get("full_name", sel_name))

            # 30-day composite trend
            fig_hist = px.line(
                hist, x="calculation_date", y="composite_score",
                markers=True,
            )
            fig_hist.update_traces(
                line_color=ACCENT, line_width=2,
                marker_color=ACCENT,
            )
            fig_hist.add_hline(
                y=35, line_dash="dash", line_color=GREEN, line_width=1,
                annotation_text="Green threshold",
                annotation_font_color=GREEN,
                annotation_position="bottom right",
            )
            fig_hist.add_hline(
                y=65, line_dash="dash", line_color=RED, line_width=1,
                annotation_text="Red threshold",
                annotation_font_color=RED,
                annotation_position="top right",
            )
            fig_hist.update_layout(
                title=f"{full_name} \u2014 30-Day Risk Score History",
                yaxis=dict(range=[0, 105], title="Composite Score"),
                xaxis=dict(title="Date"),
                height=380,
            )
            _dark(fig_hist)
            st.plotly_chart(fig_hist, use_container_width=True, key="chart_hist")

            # Date selector for factor breakdown
            hist["calc_date_str"] = hist["calculation_date"].astype(str)
            date_options          = hist["calc_date_str"].tolist()[::-1]  # newest first

            sel_date_str = st.selectbox(
                "View factor breakdown for date:",
                date_options,
                key="hist_date_select",
            )

            date_row = hist[hist["calc_date_str"] == sel_date_str].iloc[0]

            st.subheader("Factor Sub-Scores")
            factor_rows = []
            for col, label in FACTOR_LABELS.items():
                score = int(_safe_float(date_row.get(col)))
                factor_rows.append({"Factor": label, "Score": score})

            factor_table_df = pd.DataFrame(factor_rows)

            def _color_score_cell(val):
                try:
                    v = int(val)
                    if v >= 100:
                        return f"background-color:{RED}; color:#FFFFFF; font-weight:600;"
                    elif v >= 50:
                        return f"background-color:{AMBER}; color:#FFFFFF; font-weight:600;"
                    else:
                        return f"background-color:{GREEN}; color:#FFFFFF; font-weight:600;"
                except Exception:
                    return ""

            styled_factors = factor_table_df.style.map(
                _color_score_cell, subset=["Score"]
            )
            st.dataframe(styled_factors, use_container_width=True, hide_index=True)
