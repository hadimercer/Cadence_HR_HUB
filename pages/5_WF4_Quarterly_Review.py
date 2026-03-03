import datetime
import json
import streamlit as st
import pandas as pd
import plotly.express as px
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


st.set_page_config(page_title="Quarterly Reviews \u2014 Cadence", layout="wide")

# ── Constants — CADENCE.md Section 5 ─────────────────────────────────────────
_SYSTEM_USER = "2ad731c3-80c2-4848-a29d-e14361113cfb"

ACCENT  = "#4DB6AC"
GOLD    = "#D4A843"
RED     = "#E05252"
AMBER   = "#E8A838"
GREEN   = "#2ECC7A"
TEXT    = "#FAFAFA"
SURFACE = "#262730"
MUTED   = "#8892A4"

RATINGS_ALL = ["EXCEEDS", "MEETS", "BELOW", "NEW_TO_ROLE"]
RATING_COLORS = {"EXCEEDS": GREEN, "MEETS": ACCENT, "BELOW": RED, "NEW_TO_ROLE": GOLD}


# ── Quarter helpers ───────────────────────────────────────────────────────────
def current_quarter() -> str:
    today = datetime.date.today()
    q = (today.month - 1) // 3 + 1
    return f"{today.year}-Q{q}"


def quarter_date_range(q_str: str):
    year, q = int(q_str.split("-Q")[0]), int(q_str.split("-Q")[1])
    starts = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
    ends   = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    return datetime.date(year, *starts[q]), datetime.date(year, *ends[q])


# ── Page-level helpers ────────────────────────────────────────────────────────
def _safe_str(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val)


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


def _rating_badge(rating: str) -> str:
    color = RATING_COLORS.get(rating, MUTED)
    return (
        f'<span style="background:{color};color:#FFFFFF;'
        f'padding:2px 10px;border-radius:4px;font-weight:600;font-size:0.85rem;">'
        f"{rating}</span>"
    )


def _resolve_manager_id(employee_id: str) -> str:
    """employee TEXT id → manager users.id UUID. Fallback: system user."""
    mgr_df = query_df(
        "SELECT u.id FROM users u "
        "JOIN headcount_snapshots h ON h.manager_id = u.employee_id "
        "WHERE h.employee_id = %s "
        "AND h.reporting_period = (SELECT MAX(reporting_period) FROM headcount_snapshots)",
        (employee_id,),
    )
    if not mgr_df.empty:
        return str(mgr_df["id"].iloc[0])
    return _SYSTEM_USER


def _load_employees():
    return query_df(
        "SELECT employee_id, first_name || ' ' || last_name AS full_name "
        "FROM headcount_snapshots "
        "WHERE reporting_period = (SELECT MAX(reporting_period) FROM headcount_snapshots) "
        "AND status = 'ACTIVE' ORDER BY last_name, first_name"
    )


def _fetch_review(employee_id: str, quarter: str):
    return query_df(
        "SELECT id, status, self_assessment_text, self_assessment_submitted_at, "
        "rating_overall, rating_delivery, rating_behaviour, rating_development, "
        "narrative_overall, manager_submitted_at, return_note "
        "FROM performance_reviews "
        "WHERE employee_id = %s AND review_quarter = %s AND review_type = 'QUARTERLY'",
        (employee_id, quarter),
    )


def _pf(df, col, opts):
    """Pre-fill selectbox index: find existing value in opts, default 0."""
    val = _safe_str(df[col].iloc[0]) if col in df.columns else ""
    return opts.index(val) if val in opts else 0


def _fmt_ts(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    try:
        return pd.Timestamp(val).strftime("%d %b %Y %H:%M")
    except Exception:
        return ""


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Cadence")
    st.markdown("HR Process Automation Hub")
    st.divider()
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

page_header("Quarterly Reviews", "Self-assessment to HR approval. Ratings produced here drive merit eligibility.")

CQ = current_quarter()
Q_START, Q_END = quarter_date_range(CQ)

tab_sa, tab_mgr, tab_hr, tab_hist = st.tabs(
    ["Self-Assessment", "Manager Review", "HR Approval Queue", "Review History"]
)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — Self-Assessment
# ═════════════════════════════════════════════════════════════════════════════
with tab_sa:
    st.subheader("Employee Self-Assessment")
    st.caption(
        f"Quarter: **{CQ}** \u00b7 "
        f"{Q_START.strftime('%d %b')} \u2013 {Q_END.strftime('%d %b %Y')}"
    )

    emp_df = _load_employees()

    if emp_df.empty:
        st.info(
            "\u2139\ufe0f No active employees found. "
            "Upload headcount data via WF1 \u2014 Data Upload."
        )
    else:
        emp_labels = ["— Select employee —"] + emp_df["full_name"].tolist()
        emp_id_map = dict(zip(emp_df["full_name"], emp_df["employee_id"]))

        selected_sa = st.selectbox("Employee", options=emp_labels, key="sa_emp_select")

        if selected_sa == "— Select employee —":
            st.info("Select an employee to manage their self-assessment.")
        else:
            emp_id_sa = emp_id_map[selected_sa]
            rev_df = _fetch_review(emp_id_sa, CQ)

            if rev_df.empty:
                # ── Case A: No record — INSERT form ──────────────────────────
                st.caption(
                    "No review record for this quarter. "
                    "Submit self-assessment to begin the review cycle."
                )
                with st.form("sa_form_new"):
                    sa_text = st.text_area(
                        "Self-assessment",
                        height=200,
                        placeholder=(
                            "Reflect on your performance this quarter: "
                            "achievements, challenges, development..."
                        ),
                    )
                    submit_sa_new = st.form_submit_button(
                        "Submit Self-Assessment", type="primary"
                    )

                if submit_sa_new:
                    if not sa_text.strip():
                        st.error("Self-assessment text cannot be empty.")
                    else:
                        mgr_uuid = _resolve_manager_id(emp_id_sa)
                        try:
                            run_mutation(
                                "INSERT INTO performance_reviews "
                                "(id, employee_id, manager_id, review_quarter, "
                                "review_type, status, self_assessment_text, "
                                "self_assessment_submitted_at) "
                                "VALUES (gen_random_uuid(), %s, %s::uuid, %s, "
                                "'QUARTERLY', 'MANAGER_REVIEW_PENDING', %s, NOW())",
                                (emp_id_sa, mgr_uuid, CQ, sa_text),
                            )
                            query_df.clear()
                            st.success(
                                f"\u2713 Self-assessment submitted for **{selected_sa}**."
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database error: {str(e)}")

            else:
                status_sa = _safe_str(rev_df["status"].iloc[0])
                existing_sa_text = _safe_str(rev_df["self_assessment_text"].iloc[0])
                submitted_at_raw = rev_df["self_assessment_submitted_at"].iloc[0]

                if status_sa == "SELF_ASSESSMENT_PENDING":
                    # ── Case C: Draft exists — UPDATE form ───────────────────
                    record_id_sa = str(rev_df["id"].iloc[0])
                    st.caption("Draft review exists. Update and submit below.")
                    with st.form("sa_form_update"):
                        sa_text_upd = st.text_area(
                            "Self-assessment",
                            value=existing_sa_text,
                            height=200,
                            placeholder=(
                                "Reflect on your performance this quarter: "
                                "achievements, challenges, development..."
                            ),
                        )
                        submit_sa_upd = st.form_submit_button(
                            "Submit Self-Assessment", type="primary"
                        )

                    if submit_sa_upd:
                        if not sa_text_upd.strip():
                            st.error("Self-assessment text cannot be empty.")
                        else:
                            try:
                                run_mutation(
                                    "UPDATE performance_reviews "
                                    "SET self_assessment_text=%s, "
                                    "self_assessment_submitted_at=NOW(), "
                                    "status='MANAGER_REVIEW_PENDING' "
                                    "WHERE id=%s::uuid",
                                    (sa_text_upd, record_id_sa),
                                )
                                query_df.clear()
                                st.success(
                                    f"\u2713 Self-assessment submitted for **{selected_sa}**."
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"Database error: {str(e)}")

                else:
                    # ── Case B: Already submitted — read-only ─────────────────
                    ts_label = _fmt_ts(submitted_at_raw)
                    st.success(
                        "\u2713 Self-assessment submitted"
                        + (f" \u2014 {ts_label}" if ts_label else "")
                    )
                    if existing_sa_text:
                        st.info(existing_sa_text)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — Manager Review
# ═════════════════════════════════════════════════════════════════════════════
with tab_mgr:
    st.subheader("Manager Review")
    st.caption(
        f"Quarter: **{CQ}** \u00b7 "
        "Complete after employee has submitted self-assessment"
    )

    emp_df_mgr = _load_employees()

    if emp_df_mgr.empty:
        st.info("\u2139\ufe0f No active employees found.")
    else:
        emp_labels_mgr = ["— Select employee —"] + emp_df_mgr["full_name"].tolist()
        emp_id_map_mgr = dict(zip(emp_df_mgr["full_name"], emp_df_mgr["employee_id"]))

        selected_mgr = st.selectbox(
            "Employee", options=emp_labels_mgr, key="mgr_emp_select"
        )

        if selected_mgr == "— Select employee —":
            st.info("Select an employee to complete manager review.")
        else:
            emp_id_mgr = emp_id_map_mgr[selected_mgr]
            rev_mgr_df = _fetch_review(emp_id_mgr, CQ)

            if rev_mgr_df.empty:
                st.info(
                    "No review record found for this employee this quarter. "
                    "The employee must submit their self-assessment first "
                    "(Tab: Self-Assessment)."
                )
            else:
                status_mgr = _safe_str(rev_mgr_df["status"].iloc[0])

                if status_mgr == "SELF_ASSESSMENT_PENDING":
                    st.info(
                        "Waiting for employee self-assessment. "
                        "Manager review unlocks once the employee submits."
                    )

                elif status_mgr not in ("MANAGER_REVIEW_PENDING", "RETURNED"):
                    # Review submitted or approved — read-only summary
                    st.success(
                        f"\u2713 Manager review submitted \u2014 status: **{status_mgr}**"
                    )
                    r_o = _safe_str(rev_mgr_df["rating_overall"].iloc[0])
                    r_d = _safe_str(rev_mgr_df["rating_delivery"].iloc[0])
                    r_b = _safe_str(rev_mgr_df["rating_behaviour"].iloc[0])
                    r_dv = _safe_str(rev_mgr_df["rating_development"].iloc[0])
                    if r_o:
                        rc1, rc2 = st.columns(2)
                        with rc1:
                            st.markdown(
                                f"**Overall:** {_rating_badge(r_o)}", unsafe_allow_html=True
                            )
                            st.markdown(
                                f"**Delivery:** {_rating_badge(r_d)}", unsafe_allow_html=True
                            )
                        with rc2:
                            st.markdown(
                                f"**Behaviour & Values:** {_rating_badge(r_b)}",
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                f"**Development:** {_rating_badge(r_dv)}",
                                unsafe_allow_html=True,
                            )

                else:
                    # MANAGER_REVIEW_PENDING or RETURNED — show full review form
                    record_id_mgr = str(rev_mgr_df["id"].iloc[0])
                    sa_text_mgr = _safe_str(rev_mgr_df["self_assessment_text"].iloc[0])
                    return_note_mgr = _safe_str(rev_mgr_df["return_note"].iloc[0])

                    if (
                        status_mgr == "RETURNED"
                        and return_note_mgr
                        and return_note_mgr != "CHECKIN_EXCEPTION_PENDING"
                    ):
                        st.warning(
                            f"\u21a9 Review returned by HR: {return_note_mgr}"
                        )

                    # ── SECTION A — Quarter Summary ───────────────────────────
                    st.markdown("### Quarter Summary")

                    # 1:1 Summary
                    oon_df = query_df(
                        "SELECT status, sentiment_flag FROM one_on_ones "
                        "WHERE employee_id = %s "
                        "AND week_start_date BETWEEN %s AND %s",
                        (emp_id_mgr, str(Q_START), str(Q_END)),
                    )

                    completed_oons = (
                        int((oon_df["status"] == "COMPLETED").sum())
                        if not oon_df.empty
                        else 0
                    )
                    missed_oons = (
                        int((oon_df["status"] == "MISSED").sum())
                        if not oon_df.empty
                        else 0
                    )

                    sent_map = {"POSITIVE": 2, "NEUTRAL": 1, "CONCERNING": 0}
                    sent_counts = {k: 0 for k in sent_map}
                    avg_sentiment_label = "No data"

                    if not oon_df.empty and completed_oons > 0:
                        comp_only = oon_df[oon_df["status"] == "COMPLETED"]["sentiment_flag"]
                        for s in sent_map:
                            sent_counts[s] = int((comp_only == s).sum())
                        valid_scores = [
                            sent_map[s] for s in comp_only if s in sent_map
                        ]
                        if valid_scores:
                            avg = sum(valid_scores) / len(valid_scores)
                            if avg >= 1.5:
                                avg_sentiment_label = "Mostly Positive"
                            elif avg >= 0.8:
                                avg_sentiment_label = "Mixed"
                            else:
                                avg_sentiment_label = "Concerning"

                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.metric("Completed 1:1s", completed_oons, delta=f"/13 expected")
                    mc2.metric("Missed 1:1s", missed_oons)
                    mc3.metric("Avg Sentiment", avg_sentiment_label)
                    mc4.metric(
                        "Sentiment P / N / C",
                        f"{sent_counts['POSITIVE']} / "
                        f"{sent_counts['NEUTRAL']} / "
                        f"{sent_counts['CONCERNING']}",
                    )

                    # Check-in summary
                    checkin_df = query_df(
                        "SELECT checkin_period, status, goal_progress "
                        "FROM monthly_checkins "
                        "WHERE employee_id = %s "
                        "AND checkin_period BETWEEN %s AND %s "
                        "AND status IN ('ACKED', 'PENDING_ACK') "
                        "ORDER BY checkin_period DESC",
                        (emp_id_mgr, str(Q_START), str(Q_END)),
                    )

                    completed_checkins = len(checkin_df)
                    checkin_flag = completed_checkins < 2
                    checkin_color = GREEN if completed_checkins >= 3 else AMBER

                    st.markdown(
                        f"**Check-ins this quarter:** "
                        f'<span style="color:{checkin_color};font-weight:700;">'
                        f"{completed_checkins} / 3 target</span>",
                        unsafe_allow_html=True,
                    )

                    # Goal progress
                    st.markdown("#### Goal Progress")
                    if not checkin_df.empty:
                        raw_goals = _safe_str(checkin_df["goal_progress"].iloc[0])
                        if raw_goals:
                            try:
                                goals = (
                                    json.loads(raw_goals)
                                    if isinstance(raw_goals, str)
                                    else raw_goals
                                )
                                if goals:
                                    st.caption(
                                        "Goal progress as of most recent check-in"
                                    )
                                    for g in goals:
                                        g_name = g.get("goal", g.get("name", "Goal"))
                                        g_pct = min(
                                            max(float(g.get("progress", 0)), 0), 100
                                        )
                                        st.progress(
                                            g_pct / 100,
                                            text=f"{g_name}: {g_pct:.0f}%",
                                        )
                                else:
                                    st.info(
                                        "No check-in goal data available for this quarter."
                                    )
                            except (json.JSONDecodeError, TypeError, AttributeError):
                                st.info(
                                    "No check-in goal data available for this quarter."
                                )
                        else:
                            st.info(
                                "No check-in goal data available for this quarter."
                            )
                    else:
                        st.info(
                            "No check-in goal data available for this quarter."
                        )

                    if sa_text_mgr:
                        with st.expander("View Employee Self-Assessment"):
                            st.write(sa_text_mgr)

                    # Governance check — WF4-FR-014
                    if checkin_flag:
                        st.warning(
                            "\u26a0\ufe0f Fewer than 2 completed check-ins on file "
                            "for this quarter. This review will be flagged for HR "
                            "exception review on submission."
                        )

                    st.divider()

                    # ── SECTION B — Manager Rating Form ──────────────────────
                    st.markdown("### Manager Rating")

                    # Tenure gate for NEW_TO_ROLE — WF4-FR-011
                    tenure_df = query_df(
                        "SELECT tenure_in_role_months FROM headcount_snapshots "
                        "WHERE employee_id = %s "
                        "AND reporting_period = "
                        "(SELECT MAX(reporting_period) FROM headcount_snapshots)",
                        (emp_id_mgr,),
                    )
                    tenure_in_role = 99.0
                    if not tenure_df.empty:
                        raw_t = tenure_df["tenure_in_role_months"].iloc[0]
                        if raw_t is not None and not (
                            isinstance(raw_t, float) and pd.isna(raw_t)
                        ):
                            tenure_in_role = float(raw_t)

                    RATINGS = (
                        RATINGS_ALL
                        if tenure_in_role <= 3
                        else [r for r in RATINGS_ALL if r != "NEW_TO_ROLE"]
                    )

                    with st.form("manager_review_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            r_overall = st.selectbox(
                                "Overall Performance",
                                options=RATINGS,
                                index=_pf(rev_mgr_df, "rating_overall", RATINGS),
                            )
                            r_delivery = st.selectbox(
                                "Delivery",
                                options=RATINGS,
                                index=_pf(rev_mgr_df, "rating_delivery", RATINGS),
                            )
                        with col2:
                            r_behaviour = st.selectbox(
                                "Behaviour & Values",
                                options=RATINGS,
                                index=_pf(rev_mgr_df, "rating_behaviour", RATINGS),
                            )
                            r_development = st.selectbox(
                                "Development",
                                options=RATINGS,
                                index=_pf(rev_mgr_df, "rating_development", RATINGS),
                            )

                        st.caption(
                            "'New to Role' is only available for employees with "
                            "\u22643 months in their current role. Selecting it "
                            "prevents the review from contributing a Below Expectations "
                            "signal to merit eligibility or attrition risk scoring. "
                            "\u2014 WF4-FR-011"
                        )

                        narrative_existing = (
                            _safe_str(rev_mgr_df["narrative_overall"].iloc[0])
                            if "narrative_overall" in rev_mgr_df.columns
                            else ""
                        )
                        narrative = st.text_area(
                            "Manager Narrative (Overall)",
                            value=narrative_existing,
                            height=180,
                            placeholder=(
                                "Summarise this employee's performance "
                                "for the quarter..."
                            ),
                        )

                        submit_mgr = st.form_submit_button(
                            "Submit Review", type="primary"
                        )

                    if submit_mgr:
                        exception_note = (
                            "CHECKIN_EXCEPTION_PENDING" if checkin_flag else None
                        )
                        try:
                            run_mutation(
                                "UPDATE performance_reviews "
                                "SET rating_overall=%s, rating_delivery=%s, "
                                "rating_behaviour=%s, rating_development=%s, "
                                "narrative_overall=%s, manager_submitted_at=NOW(), "
                                "status='PENDING_HR_APPROVAL', return_note=%s "
                                "WHERE id=%s::uuid",
                                (
                                    r_overall,
                                    r_delivery,
                                    r_behaviour,
                                    r_development,
                                    narrative,
                                    exception_note,
                                    record_id_mgr,
                                ),
                            )
                            query_df.clear()
                            st.success(
                                f"\u2713 Review submitted for **{selected_mgr}** "
                                "\u2014 awaiting HR approval."
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database error: {str(e)}")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — HR Approval Queue
# ═════════════════════════════════════════════════════════════════════════════
with tab_hr:
    st.subheader("HR Approval Queue")

    queue_df = query_df(
        "SELECT pr.id, pr.employee_id, pr.status, "
        "pr.rating_overall, pr.rating_delivery, pr.rating_behaviour, "
        "pr.rating_development, pr.narrative_overall, "
        "pr.self_assessment_text, pr.manager_submitted_at, pr.return_note, "
        "hs.first_name || ' ' || hs.last_name AS employee_name, hs.department "
        "FROM performance_reviews pr "
        "LEFT JOIN headcount_snapshots hs "
        "  ON hs.employee_id = pr.employee_id "
        "  AND hs.reporting_period = "
        "    (SELECT MAX(reporting_period) FROM headcount_snapshots) "
        "WHERE pr.status IN ('PENDING_HR_APPROVAL', 'RETURNED') "
        "AND pr.review_type = 'QUARTERLY' "
        "ORDER BY pr.manager_submitted_at ASC NULLS LAST"
    )

    approved_ct_df = query_df(
        "SELECT COUNT(*) AS cnt FROM performance_reviews "
        "WHERE status = 'APPROVED' AND review_quarter = %s AND review_type = 'QUARTERLY'",
        (CQ,),
    )
    approved_ct = (
        int(approved_ct_df["cnt"].iloc[0]) if not approved_ct_df.empty else 0
    )

    pending_ct = (
        int((queue_df["status"] == "PENDING_HR_APPROVAL").sum())
        if not queue_df.empty
        else 0
    )
    returned_ct = (
        int((queue_df["status"] == "RETURNED").sum())
        if not queue_df.empty
        else 0
    )

    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Pending Approval", pending_ct)
    sc2.metric("Returned to Manager", returned_ct)
    sc3.metric("Approved This Quarter", approved_ct)

    st.divider()

    # ── Pending Approval ──────────────────────────────────────────────────────
    pending_df = (
        queue_df[queue_df["status"] == "PENDING_HR_APPROVAL"].copy()
        if not queue_df.empty
        else pd.DataFrame()
    )

    if pending_df.empty:
        st.info("\u2139\ufe0f No reviews pending approval.")
    else:
        st.markdown("#### Pending Approval")
        for _, row in pending_df.iterrows():
            record_id = str(row["id"])
            emp_name  = _safe_str(row["employee_name"]) or _safe_str(row["employee_id"])
            dept      = _safe_str(row["department"])
            sub_label = _fmt_ts(row["manager_submitted_at"])

            with st.expander(
                f"{emp_name} \u2014 {dept} \u2014 Submitted {sub_label}"
            ):
                sa_hr = _safe_str(row["self_assessment_text"])
                if sa_hr:
                    st.info(f"**Self-Assessment:** {sa_hr}")

                # Checkin exception flag
                ret_note = _safe_str(row["return_note"])
                if ret_note == "CHECKIN_EXCEPTION_PENDING":
                    st.warning(
                        "\u26a0\ufe0f Flagged: fewer than 2 check-ins completed "
                        "this quarter. Exception decision required."
                    )

                # Rating grid
                rc1, rc2 = st.columns(2)
                with rc1:
                    st.markdown(
                        f"**Overall:** {_rating_badge(_safe_str(row['rating_overall']))}",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"**Delivery:** {_rating_badge(_safe_str(row['rating_delivery']))}",
                        unsafe_allow_html=True,
                    )
                with rc2:
                    st.markdown(
                        f"**Behaviour & Values:** "
                        f"{_rating_badge(_safe_str(row['rating_behaviour']))}",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"**Development:** "
                        f"{_rating_badge(_safe_str(row['rating_development']))}",
                        unsafe_allow_html=True,
                    )

                narrative_hr = _safe_str(row["narrative_overall"])
                if narrative_hr:
                    st.markdown("**Manager Narrative:**")
                    st.text(narrative_hr)

                # Action buttons
                col_approve, col_return = st.columns(2)

                with col_approve:
                    if st.button(
                        "\u2713 Approve",
                        key=f"approve_{record_id}",
                        type="primary",
                    ):
                        try:
                            run_mutation(
                                "UPDATE performance_reviews "
                                "SET status='APPROVED', hr_approved_by=%s::uuid, "
                                "hr_approved_at=NOW(), return_note=NULL "
                                "WHERE id=%s::uuid",
                                (_SYSTEM_USER, record_id),
                            )
                            query_df.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database error: {str(e)}")

                with col_return:
                    if st.button(
                        "\u21a9 Return to Manager", key=f"return_btn_{record_id}"
                    ):
                        st.session_state[f"show_return_{record_id}"] = True

                    if st.session_state.get(f"show_return_{record_id}", False):
                        note_input = st.text_input(
                            "Return note",
                            key=f"return_note_input_{record_id}",
                        )
                        if st.button(
                            "Confirm Return", key=f"confirm_return_{record_id}"
                        ):
                            if not note_input.strip():
                                st.warning(
                                    "Enter a return note before confirming."
                                )
                            else:
                                try:
                                    run_mutation(
                                        "UPDATE performance_reviews "
                                        "SET status='RETURNED', return_note=%s "
                                        "WHERE id=%s::uuid",
                                        (note_input, record_id),
                                    )
                                    query_df.clear()
                                    st.session_state[
                                        f"show_return_{record_id}"
                                    ] = False
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Database error: {str(e)}")

    # ── Returned records ──────────────────────────────────────────────────────
    returned_df = (
        queue_df[queue_df["status"] == "RETURNED"].copy()
        if not queue_df.empty
        else pd.DataFrame()
    )

    if not returned_df.empty:
        st.divider()
        st.markdown("#### Returned to Manager")
        for _, row in returned_df.iterrows():
            emp_name_r = _safe_str(row["employee_name"]) or _safe_str(row["employee_id"])
            dept_r     = _safe_str(row["department"])
            ret_note_r = _safe_str(row["return_note"])
            with st.expander(f"{emp_name_r} \u2014 {dept_r} \u2014 RETURNED"):
                if ret_note_r and ret_note_r != "CHECKIN_EXCEPTION_PENDING":
                    st.warning(f"\u21a9 HR Return Note: {ret_note_r}")
                else:
                    st.caption("No return note provided.")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — Review History
# ═════════════════════════════════════════════════════════════════════════════
with tab_hist:
    st.subheader("Review History")
    st.caption("All approved quarterly reviews across all periods")

    hist_df = query_df(
        "SELECT pr.review_quarter, "
        "COALESCE(hs.first_name || ' ' || hs.last_name, pr.employee_id) AS employee_name, "
        "hs.department, hs.job_title, "
        "pr.rating_overall, pr.rating_delivery, pr.rating_behaviour, "
        "pr.rating_development, pr.hr_approved_at, "
        "COALESCE(mhs.first_name || ' ' || mhs.last_name, '') AS manager_name "
        "FROM performance_reviews pr "
        "LEFT JOIN headcount_snapshots hs "
        "  ON hs.employee_id = pr.employee_id "
        "  AND hs.reporting_period = "
        "    (SELECT MAX(reporting_period) FROM headcount_snapshots) "
        "LEFT JOIN users u ON u.id = pr.manager_id "
        "LEFT JOIN headcount_snapshots mhs "
        "  ON mhs.employee_id = u.employee_id "
        "  AND mhs.reporting_period = "
        "    (SELECT MAX(reporting_period) FROM headcount_snapshots) "
        "WHERE pr.status = 'APPROVED' AND pr.review_type = 'QUARTERLY' "
        "ORDER BY pr.review_quarter DESC, hs.last_name, hs.first_name"
    )

    if hist_df.empty:
        st.info("\u2139\ufe0f No approved reviews yet.")
    else:
        display_df = hist_df.copy()
        display_df["hr_approved_at"] = pd.to_datetime(
            display_df["hr_approved_at"], errors="coerce"
        ).dt.strftime("%d %b %Y")

        display_df = display_df.rename(
            columns={
                "review_quarter":    "Quarter",
                "employee_name":     "Employee",
                "department":        "Department",
                "job_title":         "Job Title",
                "rating_overall":    "Overall",
                "rating_delivery":   "Delivery",
                "rating_behaviour":  "Behaviour",
                "rating_development": "Development",
                "manager_name":      "Manager",
                "hr_approved_at":    "Approved",
            }
        )

        rating_cols = ["Overall", "Delivery", "Behaviour", "Development"]

        def _style_rating(val):
            mapping = {
                "EXCEEDS":     f"background-color: {GREEN}; color: #FFFFFF; font-weight: 600;",
                "MEETS":       f"background-color: {ACCENT}; color: #FFFFFF; font-weight: 600;",
                "BELOW":       f"background-color: {RED}; color: #FFFFFF; font-weight: 600;",
                "NEW_TO_ROLE": f"background-color: {GOLD}; color: #FFFFFF; font-weight: 600;",
            }
            return mapping.get(str(val), "")

        styled = display_df.style.map(_style_rating, subset=rating_cols)
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.divider()

        # Stacked bar chart — reviews by quarter, coloured by overall rating
        chart_df = (
            hist_df.groupby(["review_quarter", "rating_overall"])
            .size()
            .reset_index(name="count")
        )

        if not chart_df.empty:
            fig = px.bar(
                chart_df,
                x="review_quarter",
                y="count",
                color="rating_overall",
                title="Approved Reviews by Quarter",
                color_discrete_map=RATING_COLORS,
                barmode="stack",
                labels={
                    "review_quarter":  "Quarter",
                    "count":           "Number of Reviews",
                    "rating_overall":  "Overall Rating",
                },
            )
            _dark(fig)
            st.plotly_chart(fig, use_container_width=True)
