import streamlit as st

st.set_page_config(
    page_title="Cadence \u2014 HR Process Automation Hub",
    page_icon="\u2699\ufe0f",
    layout="wide",
    initial_sidebar_state="expanded",
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

from utils.home import render_home
render_home()
