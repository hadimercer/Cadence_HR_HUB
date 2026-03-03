import streamlit as st

st.set_page_config(
    page_title="Cadence \u2014 HR Process Automation Hub",
    page_icon="\u2699\ufe0f",
    layout="wide",
)


def page_header(title, subtitle=""):
    sub = f'<p style="color:rgba(255,255,255,0.82); font-size:0.95rem; margin:0;">{subtitle}</p>' if subtitle else ""
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,#1B4F72 0%,#2E86C1 100%);
                border-radius:0.6rem;padding:1rem 1.4rem 0.9rem;margin-bottom:1.2rem;">
      <h1 style="color:#FFFFFF;font-size:1.8rem;font-weight:700;
                 margin:0 0 0.2rem 0;line-height:1.2;">{title}</h1>
      {sub}
    </div>""", unsafe_allow_html=True)


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

page_header(
    "Cadence \u2014 HR Process Automation Hub",
    "End-to-end HR workflow automation \u2014 from headcount upload to attrition risk scoring.",
)

# \u2500\u2500 Workflow cards \u2014 2\xd72 grid \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
col_a, col_b = st.columns(2, gap="medium")

with col_a:
    st.markdown(
        '<div style="background:#262730;border-radius:0.75rem;padding:1.2rem 1.4rem;'
        'margin-bottom:0.8rem;border-left:4px solid #4DB6AC;">'
        '<div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.6rem;">'
        '<span style="font-size:1.35rem;">\U0001f4ca</span>'
        '<span style="font-size:1.1rem;font-weight:700;color:#FAFAFA;">Workforce Intelligence</span>'
        '<span style="background:#4DB6AC;color:#0E1117;font-size:0.7rem;font-weight:700;'
        'padding:2px 8px;border-radius:999px;margin-left:auto;">01</span></div>'
        '<p style="color:rgba(255,255,255,0.68);font-size:0.875rem;margin:0;line-height:1.55;">'
        'Upload monthly HRIS exports and validate headcount data. Live KPI dashboard '
        'tracks attrition rate, span of control, and headcount versus budget.'
        '</p></div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/1_WF1_Data_Upload.py", label="\u2192  Data Upload & Pipeline", use_container_width=True)

with col_b:
    st.markdown(
        '<div style="background:#262730;border-radius:0.75rem;padding:1.2rem 1.4rem;'
        'margin-bottom:0.8rem;border-left:4px solid #8E44AD;">'
        '<div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.6rem;">'
        '<span style="font-size:1.35rem;">\U0001f5d3\ufe0f</span>'
        '<span style="font-size:1.1rem;font-weight:700;color:#FAFAFA;">Performance Management</span>'
        '<span style="background:#8E44AD;color:#FFFFFF;font-size:0.7rem;font-weight:700;'
        'padding:2px 8px;border-radius:999px;margin-left:auto;">02</span></div>'
        '<p style="color:rgba(255,255,255,0.68);font-size:0.875rem;margin:0;line-height:1.55;">'
        'Structured weekly 1:1 capture, monthly goal check-ins, and quarterly review cycles. '
        'Ratings produced here drive merit eligibility in the compensation workflow.'
        '</p></div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/3_WF4_Weekly_1on1.py", label="\u2192  Weekly 1:1s", use_container_width=True)

col_c, col_d = st.columns(2, gap="medium")

with col_c:
    st.markdown(
        '<div style="background:#262730;border-radius:0.75rem;padding:1.2rem 1.4rem;'
        'margin-bottom:0.8rem;border-left:4px solid #F39C12;">'
        '<div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.6rem;">'
        '<span style="font-size:1.35rem;">\U0001f4b0</span>'
        '<span style="font-size:1.1rem;font-weight:700;color:#FAFAFA;">Compensation Review</span>'
        '<span style="background:#F39C12;color:#0E1117;font-size:0.7rem;font-weight:700;'
        'padding:2px 8px;border-radius:999px;margin-left:auto;">03</span></div>'
        '<p style="color:rgba(255,255,255,0.68);font-size:0.875rem;margin:0;line-height:1.55;">'
        'Six-gate eligibility engine and manager recommendation workflow for merit cycles. '
        'Budget utilisation tracked in real time against approved headcount.'
        '</p></div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/6_WF2_Merit_Cycle.py", label="\u2192  Merit Cycle", use_container_width=True)

with col_d:
    st.markdown(
        '<div style="background:#262730;border-radius:0.75rem;padding:1.2rem 1.4rem;'
        'margin-bottom:0.8rem;border-left:4px solid #E74C3C;">'
        '<div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.6rem;">'
        '<span style="font-size:1.35rem;">\U0001f3af</span>'
        '<span style="font-size:1.1rem;font-weight:700;color:#FAFAFA;">Attrition Risk</span>'
        '<span style="background:#E74C3C;color:#FFFFFF;font-size:0.7rem;font-weight:700;'
        'padding:2px 8px;border-radius:999px;margin-left:auto;">04</span></div>'
        '<p style="color:rgba(255,255,255,0.68);font-size:0.875rem;margin:0;line-height:1.55;">'
        'Seven-factor rules-based risk scoring. Ranked register with configurable factor '
        'weights and retention action logging.'
        '</p></div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/8_WF3_Risk_Dashboard.py", label="\u2192  Risk Dashboard", use_container_width=True)

# \u2500\u2500 Data flow banner \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
st.markdown(
    '<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);'
    'border-radius:0.6rem;padding:0.85rem 1.4rem;margin-top:0.2rem;'
    'display:flex;align-items:center;gap:1rem;flex-wrap:wrap;">'
    '<span style="color:rgba(255,255,255,0.45);font-size:0.78rem;font-weight:700;'
    'letter-spacing:0.07em;">DATA FLOW</span>'
    '<span style="color:#4DB6AC;font-size:0.875rem;font-weight:600;">Headcount</span>'
    '<span style="color:rgba(255,255,255,0.3);font-size:0.9rem;">\u2192</span>'
    '<span style="color:#8E44AD;font-size:0.875rem;font-weight:600;">Performance</span>'
    '<span style="color:rgba(255,255,255,0.3);font-size:0.9rem;">\u2192</span>'
    '<span style="color:#F39C12;font-size:0.875rem;font-weight:600;">Compensation</span>'
    '<span style="color:rgba(255,255,255,0.3);font-size:0.9rem;">\u2192</span>'
    '<span style="color:#E74C3C;font-size:0.875rem;font-weight:600;">Risk Score</span>'
    '</div>',
    unsafe_allow_html=True,
)
