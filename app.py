import streamlit as st

st.set_page_config(page_title="Cadence", layout="wide")

st.title("Cadence \u2014 HR Process Automation Hub")
st.caption("Select a workflow from the sidebar to begin.")

with st.sidebar:
    st.markdown("### Cadence")
    st.markdown("HR Process Automation Hub")
    st.divider()
    st.markdown("**Workflow Navigation**")
    st.page_link("pages/1_WF1_Data_Upload.py",      label="WF1 \u2014 Data Upload")
    st.page_link("pages/2_WF1_Dashboard.py",         label="WF1 \u2014 KPI Dashboard")
    st.page_link("pages/3_WF4_Weekly_1on1.py",       label="WF4 \u2014 Weekly 1:1")
    st.page_link("pages/4_WF4_Monthly_Checkin.py",   label="WF4 \u2014 Monthly Check-in")
    st.page_link("pages/5_WF4_Quarterly_Review.py",  label="WF4 \u2014 Quarterly Review")
    st.page_link("pages/6_WF2_Merit_Cycle.py",       label="WF2 \u2014 Merit Cycle")
    st.page_link("pages/7_WF2_Eligibility.py",       label="WF2 \u2014 Eligibility Engine")
    st.page_link("pages/8_WF3_Risk_Dashboard.py",    label="WF3 \u2014 Risk Dashboard")
    st.page_link("pages/9_WF3_Config.py",            label="WF3 \u2014 Config")
