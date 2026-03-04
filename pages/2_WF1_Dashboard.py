import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.db import query_df

ACCENT = "#4DB6AC"
RED = "#E05252"
AMBER = "#E8A838"
GREEN = "#2ECC7A"
LEVEL_ORDER = ["L1", "L2", "L3", "L4", "L5", "L6"]


def _dark(fig):
    fig.update_layout(
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="#FAFAFA"),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    fig.update_xaxes(gridcolor="#262730")
    fig.update_yaxes(gridcolor="#262730")
    return fig


def page_header(title, subtitle=""):
    sub = f'<p style="color:rgba(255,255,255,0.82); font-size:0.95rem; margin:0;">{subtitle}</p>' if subtitle else ""
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,#1B4F72 0%,#2E86C1 100%);
                border-radius:0.6rem;padding:1rem 1.4rem 0.9rem;margin-bottom:1.2rem;">
      <h1 style="color:#FFFFFF;font-size:1.8rem;font-weight:700;
                 margin:0 0 0.2rem 0;line-height:1.2;">{title}</h1>
      {sub}
    </div>""", unsafe_allow_html=True)


st.set_page_config(page_title="KPI Dashboard \u2014 Cadence", layout="wide")

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

page_header("Workforce KPI Dashboard", "Live headcount metrics — attrition rate, span of control, headcount vs budget.")

# DATA LOADING

period_df = query_df("SELECT MAX(reporting_period) AS latest_period FROM headcount_snapshots WHERE status = 'ACTIVE'")
latest_period = None
if not period_df.empty and period_df.iloc[0]["latest_period"] is not None:
    latest_period = period_df.iloc[0]["latest_period"]

if latest_period is None:
    st.info("No headcount data loaded yet. Use the Data Upload page to ingest a CSV.")
    st.stop()

active_df = query_df("SELECT * FROM headcount_snapshots WHERE reporting_period = %s AND status = 'ACTIVE'", (str(latest_period),))

leaver_df = query_df("SELECT * FROM headcount_snapshots WHERE reporting_period = %s AND status = 'LEAVER'", (str(latest_period),))

if active_df.empty:
    st.info("No headcount data loaded yet. Use the Data Upload page to ingest a CSV.")
    st.stop()

# DATA FRESHNESS PILL

period_label = pd.Timestamp(latest_period).strftime("%B %Y")
_, col_fresh = st.columns([7, 2])
with col_fresh:
    st.markdown(
        f'<div style="text-align:right; color:#4DB6AC; font-size:0.85rem;">Data as of: {period_label}</div>',
        unsafe_allow_html=True
    )

# COMPUTE KPI VALUES

total_active = len(active_df)
total_leavers = len(leaver_df)
total_budget = float(active_df["budgeted_headcount"].sum())
total_workforce = total_active + total_leavers
hc_delta = int(active_df["headcount_delta"].sum()) if "headcount_delta" in active_df.columns else 0
new_hires = int(active_df["is_new_hire"].sum()) if "is_new_hire" in active_df.columns else 0
pct_of_budget = (total_active / total_budget * 100) if total_budget > 0 else 0.0
budget_delta = pct_of_budget - 100
attrition_rate = (total_leavers / total_workforce * 100) if total_workforce > 0 else 0.0
avg_tenure = float(active_df["tenure_months"].mean()) if not active_df["tenure_months"].isna().all() else 0.0
mgr_ids = active_df["manager_id"].dropna()
mgr_ids = mgr_ids[mgr_ids.str.strip().ne("")]
manager_count = mgr_ids.nunique()
span_of_control = total_active / manager_count if manager_count > 0 else 0.0

# SECTION 1 — KPI CARDS

row1 = st.columns(4)

with row1[0]:
    st.metric("Total Headcount", total_active, delta="—" if hc_delta == 0 else hc_delta)

with row1[1]:
    if abs(budget_delta) <= 2:
        colour = GREEN
        label = "On Budget"
    elif budget_delta > 2:
        colour = RED
        label = f"+{budget_delta:.1f}% over"
    else:
        colour = AMBER
        label = f"{budget_delta:.1f}% under"
    st.markdown("**Headcount vs Budget**")
    st.markdown(
        f'<span style="font-size:1.8rem;font-weight:700;color:{colour};">{pct_of_budget:.0f}%</span> '
        f'<span style="font-size:0.85rem;color:{colour};">{label}</span>',
        unsafe_allow_html=True
    )

with row1[2]:
    st.metric("New Hires This Period", new_hires)

with row1[3]:
    st.metric("Leavers This Period", total_leavers)

st.markdown("")

row2 = st.columns(3)

with row2[0]:
    if attrition_rate > 15:
        colour = RED
    elif attrition_rate > 10:
        colour = AMBER
    else:
        colour = GREEN
    st.markdown("**General Attrition Rate**")
    st.markdown(
        f'<span style="font-size:1.8rem;font-weight:700;color:{colour};">{attrition_rate:.1f}%</span>',
        unsafe_allow_html=True
    )

with row2[1]:
    st.metric("Average Tenure", f"{avg_tenure:.1f} months")

with row2[2]:
    st.metric("Span of Control", f"{span_of_control:.1f} : 1")

st.divider()

# SECTION 2 — CHARTS

chart_row1 = st.columns(2)

with chart_row1[0]:
    dept_counts = active_df.groupby("department").size().reset_index(name="headcount").sort_values("headcount", ascending=True)
    fig1 = px.bar(dept_counts, x="headcount", y="department", orientation="h", title="Headcount by Department", color_discrete_sequence=[ACCENT])
    _dark(fig1)
    st.plotly_chart(fig1, use_container_width=True)

with chart_row1[1]:
    actual_dept = active_df.groupby("department").size().reset_index(name="actual")
    budget_dept = active_df.groupby("department")["budgeted_headcount"].sum().reset_index(name="budget")
    dept_budget = actual_dept.merge(budget_dept, on="department")
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(name="Actual", x=dept_budget["department"], y=dept_budget["actual"], marker_color=ACCENT))
    fig2.add_trace(go.Bar(name="Budget", x=dept_budget["department"], y=dept_budget["budget"], marker_color="#7986CB"))
    fig2.update_layout(barmode="group", title="Actual vs Budget Headcount by Department")
    _dark(fig2)
    st.plotly_chart(fig2, use_container_width=True)

chart_row2 = st.columns(2)

with chart_row2[0]:
    level_counts = active_df.groupby("level").size().reset_index(name="headcount")
    level_counts["level"] = pd.Categorical(level_counts["level"], categories=LEVEL_ORDER, ordered=True)
    level_counts = level_counts.sort_values("level")
    fig3 = px.bar(level_counts, x="headcount", y="level", orientation="h", title="Headcount by Level", color_discrete_sequence=[ACCENT])
    _dark(fig3)
    st.plotly_chart(fig3, use_container_width=True)

with chart_row2[1]:
    emp_type_counts = active_df.groupby("employment_type").size().reset_index(name="count")
    fig4 = px.pie(emp_type_counts, values="count", names="employment_type", hole=0.45, title="Employment Type Distribution")
    fig4.update_layout(paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", font=dict(color="#FAFAFA"), margin=dict(l=20, r=20, t=40, b=20))
    fig4.update_traces(textfont_color="#FAFAFA")
    st.plotly_chart(fig4, use_container_width=True)

st.divider()

# SECTION 3 — EMPLOYEE TABLE

with st.expander("View Full Employee List"):
    display_cols = [c for c in ["employee_id", "first_name", "last_name", "department", "level", "job_title", "employment_type", "tenure_months", "salary_grade"] if c in active_df.columns]
    st.dataframe(active_df[display_cols], use_container_width=True)
