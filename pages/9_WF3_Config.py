import streamlit as st
import pandas as pd
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


st.set_page_config(page_title="Scoring Config \u2014 Cadence", layout="wide")

# ── Constants ─────────────────────────────────────────────────────────────────
_SYSTEM_USER = "2ad731c3-80c2-4848-a29d-e14361113cfb"
FACTOR_ORDER = [
    "COMPA_RATIO",
    "RATING_TRAJECTORY",
    "TIME_SINCE_MERIT",
    "TIME_IN_ROLE",
    "SENTIMENT_TREND",
    "CHECKIN_FREQUENCY",
    "FLIGHT_RISK_ROLE",
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

# Data source → (label, badge colour)
FACTOR_SOURCE = {
    "COMPA_RATIO":       ("WF2", GOLD),
    "RATING_TRAJECTORY": ("WF4", GREEN),
    "TIME_SINCE_MERIT":  ("WF2", GOLD),
    "TIME_IN_ROLE":      ("WF1", ACCENT),
    "SENTIMENT_TREND":   ("WF4", GREEN),
    "CHECKIN_FREQUENCY": ("WF4", GREEN),
    "FLIGHT_RISK_ROLE":  ("CONFIG", MUTED),
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


def _source_badge(factor_code: str) -> str:
    label, color = FACTOR_SOURCE.get(factor_code, ("", MUTED))
    if not label:
        return ""
    return (
        f'<span style="background:{color};color:#FFFFFF;'
        f'padding:1px 7px;border-radius:3px;'
        f'font-size:0.72rem;font-weight:600;margin-left:6px;">'
        f"{label}</span>"
    )


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

page_header("Scoring Engine Configuration", "Adjust factor weights, thresholds, and active status. All changes audit-logged.")

tab_cfg, tab_audit = st.tabs(["Factor Configuration", "Audit Log"])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — Factor Configuration
# ═════════════════════════════════════════════════════════════════════════════
with tab_cfg:

    # ── Load current config ordered by FACTOR_ORDER ───────────────────────────
    config_df = query_df(
        "SELECT * FROM risk_factor_config ORDER BY "
        "CASE factor_code "
        "WHEN 'COMPA_RATIO'       THEN 1 "
        "WHEN 'RATING_TRAJECTORY' THEN 2 "
        "WHEN 'TIME_SINCE_MERIT'  THEN 3 "
        "WHEN 'TIME_IN_ROLE'      THEN 4 "
        "WHEN 'SENTIMENT_TREND'   THEN 5 "
        "WHEN 'CHECKIN_FREQUENCY' THEN 6 "
        "WHEN 'FLIGHT_RISK_ROLE'  THEN 7 "
        "ELSE 99 END"
    )

    if config_df.empty:
        st.info(
            "\u2139\ufe0f No scoring factors found in risk_factor_config. "
            "Seed the table before using this panel."
        )
    else:
        # Build lookup dict: factor_code → DataFrame row
        config_dict = {
            str(row["factor_code"]): row
            for _, row in config_df.iterrows()
        }

        # ── Compute current total weight from session state (or DB defaults) ──
        # Reading session state BEFORE rendering widgets is the correct Streamlit
        # pattern for showing a derived metric above the widget grid.
        # First render: keys absent from session state → DB values used as defaults.
        # Subsequent renders: keys present → user's edited values used.
        total_weight = 0.0
        for fc in FACTOR_ORDER:
            if fc not in config_dict:
                continue
            row = config_dict[fc]
            is_active_now = st.session_state.get(
                f"active_{fc}", bool(row.get("is_active", True))
            )
            weight_now = st.session_state.get(
                f"weight_{fc}", _safe_float(row.get("weight", 0.0))
            )
            if is_active_now:
                total_weight += weight_now

        # ── Weight total indicator ────────────────────────────────────────────
        st.metric("Active Factor Weights Total", f"{total_weight:.1f}%")
        weights_ok = abs(total_weight - 100.0) < 0.01
        if weights_ok:
            st.success("\u2713 Weights sum to 100%")
        else:
            st.error(
                "\u26a0\ufe0f Weights must sum to 100%. Save is disabled."
            )

        st.divider()

        # ── Column headers ────────────────────────────────────────────────────
        h = st.columns([2.4, 0.7, 0.9, 1.1, 1.1])
        for col, label in zip(
            h,
            ["Factor", "Active", "Weight %", "Medium Threshold", "High Threshold"],
        ):
            col.markdown(f"**{label}**")

        # ── Factor rows ───────────────────────────────────────────────────────
        for fc in FACTOR_ORDER:
            if fc not in config_dict:
                continue
            row = config_dict[fc]

            factor_name = _safe_str(row.get("factor_name", fc))
            factor_desc = _safe_str(row.get("factor_description", ""))
            badge_html  = _source_badge(fc)

            cols = st.columns([2.4, 0.7, 0.9, 1.1, 1.1])

            with cols[0]:
                st.markdown(
                    f"**{factor_name}**{badge_html}",
                    unsafe_allow_html=True,
                )
                if factor_desc:
                    st.caption(factor_desc)

            with cols[1]:
                is_active_widget = st.checkbox(
                    "Active",
                    value=bool(row.get("is_active", True)),
                    key=f"active_{fc}",
                    label_visibility="collapsed",
                )

            with cols[2]:
                st.number_input(
                    "Weight %",
                    value=_safe_float(row.get("weight", 0.0)),
                    min_value=0.0,
                    max_value=100.0,
                    step=0.5,
                    disabled=not is_active_widget,
                    key=f"weight_{fc}",
                    label_visibility="collapsed",
                )

            with cols[3]:
                st.number_input(
                    "Medium Threshold",
                    value=_safe_float(row.get("threshold_medium", 0.0)),
                    min_value=0.0,
                    max_value=100.0,
                    step=1.0,
                    key=f"tmed_{fc}",
                    label_visibility="collapsed",
                )

            with cols[4]:
                st.number_input(
                    "High Threshold",
                    value=_safe_float(row.get("threshold_high", 0.0)),
                    min_value=0.0,
                    max_value=100.0,
                    step=1.0,
                    key=f"thigh_{fc}",
                    label_visibility="collapsed",
                )

        st.divider()

        # ── Live weight summary ───────────────────────────────────────────────
        _FACTOR_DISPLAY = {
            "COMPA_RATIO":       "Pay Position (Compa-ratio)",
            "RATING_TRAJECTORY": "Performance Trend",
            "TIME_SINCE_MERIT":  "Time Since Merit Increase",
            "TIME_IN_ROLE":      "Time in Role",
            "SENTIMENT_TREND":   "1:1 Sentiment Trend",
            "CHECKIN_FREQUENCY": "Check-in Frequency",
            "FLIGHT_RISK_ROLE":  "Flight Risk Role",
        }
        active_rows = []
        for fc in FACTOR_ORDER:
            if fc not in config_dict:
                continue
            row = config_dict[fc]
            is_active_now = st.session_state.get(
                f"active_{fc}", bool(row.get("is_active", True))
            )
            if is_active_now:
                w = st.session_state.get(
                    f"weight_{fc}", _safe_float(row.get("weight", 0.0))
                )
                active_rows.append({
                    "Factor": _FACTOR_DISPLAY.get(fc, fc),
                    "Weight %": round(w, 1),
                })

        if active_rows:
            st.dataframe(
                pd.DataFrame(active_rows), use_container_width=True, hide_index=True
            )

        if weights_ok:
            st.success("\u2713 Weights sum to 100% \u2014 ready to save.")
        else:
            gap = total_weight - 100.0
            sign = "+" if gap > 0 else ""
            st.error(
                f"\u26a0\ufe0f Weights sum to {total_weight:.1f}% "
                f"({sign}{gap:.1f}% from 100%). Adjust before saving."
            )

        # ── Save button ───────────────────────────────────────────────────────
        if st.button(
            "Save Configuration", type="primary", disabled=not weights_ok
        ):
            changes_made = 0
            try:
                for fc in FACTOR_ORDER:
                    if fc not in config_dict:
                        continue
                    old_row   = config_dict[fc]
                    factor_id = str(old_row["id"])

                    old_active = bool(old_row.get("is_active", True))
                    old_weight = _safe_float(old_row.get("weight", 0.0))
                    old_tmed   = _safe_float(old_row.get("threshold_medium", 0.0))
                    old_thigh  = _safe_float(old_row.get("threshold_high", 0.0))

                    new_active = st.session_state.get(f"active_{fc}", old_active)
                    new_weight = st.session_state.get(f"weight_{fc}", old_weight)
                    new_tmed   = st.session_state.get(f"tmed_{fc}", old_tmed)
                    new_thigh  = st.session_state.get(f"thigh_{fc}", old_thigh)

                    changed_fields = []
                    if new_active != old_active:
                        changed_fields.append(
                            ("is_active", str(old_active), str(new_active))
                        )
                    if abs(new_weight - old_weight) > 0.001:
                        changed_fields.append(
                            ("weight", str(old_weight), str(new_weight))
                        )
                    if abs(new_tmed - old_tmed) > 0.001:
                        changed_fields.append(
                            (
                                "threshold_medium",
                                str(old_tmed),
                                str(new_tmed),
                            )
                        )
                    if abs(new_thigh - old_thigh) > 0.001:
                        changed_fields.append(
                            (
                                "threshold_high",
                                str(old_thigh),
                                str(new_thigh),
                            )
                        )

                    if not changed_fields:
                        continue

                    # UPDATE the factor row
                    run_mutation(
                        "UPDATE risk_factor_config SET "
                        "is_active=%s, weight=%s, "
                        "threshold_medium=%s, threshold_high=%s, "
                        "updated_by=%s::uuid, updated_at=NOW() "
                        "WHERE factor_code=%s",
                        (
                            new_active,
                            new_weight,
                            new_tmed,
                            new_thigh,
                            _SYSTEM_USER,
                            fc,
                        ),
                    )

                    # INSERT one audit row per changed field
                    for field_name, old_val, new_val in changed_fields:
                        run_mutation(
                            "INSERT INTO config_audit_log "
                            "(changed_by, changed_at, table_name, record_id, "
                            "field_name, old_value, new_value, "
                            "action_type, context_note) "
                            "VALUES "
                            "(%s::uuid, NOW(), 'risk_factor_config', %s::uuid, "
                            "%s, %s, %s, 'UPDATE', %s)",
                            (
                                _SYSTEM_USER,
                                factor_id,
                                field_name,
                                old_val,
                                new_val,
                                "Updated via config panel",
                            ),
                        )
                        changes_made += 1

                query_df.clear()
                if changes_made > 0:
                    st.success(
                        f"\u2713 Configuration saved and audit-logged "
                        f"({changes_made} change(s) recorded)."
                    )
                else:
                    st.info("No changes detected — nothing to save.")
                st.rerun()

            except Exception as e:
                st.error(f"Database error: {str(e)}")

        # ── RAG threshold reference ───────────────────────────────────────────
        st.divider()
        st.subheader("RAG Score Thresholds")
        st.caption(
            "These thresholds determine which composite score range "
            "maps to each status."
        )

        rag1, rag2, rag3 = st.columns(3)
        with rag1:
            st.markdown(
                f'<div style="background:{GREEN};border-radius:0.5rem;'
                f'padding:0.85rem 1.1rem;">'
                f'<div style="font-size:1.05rem;font-weight:700;color:#FFFFFF;">'
                f'\U0001f7e2 GREEN</div>'
                f'<div style="color:#FFFFFF;font-size:0.85rem;margin-top:0.2rem;">'
                f'Score &lt; 35</div></div>',
                unsafe_allow_html=True,
            )
        with rag2:
            st.markdown(
                f'<div style="background:{AMBER};border-radius:0.5rem;'
                f'padding:0.85rem 1.1rem;">'
                f'<div style="font-size:1.05rem;font-weight:700;color:#FFFFFF;">'
                f'\U0001f7e1 AMBER</div>'
                f'<div style="color:#FFFFFF;font-size:0.85rem;margin-top:0.2rem;">'
                f'Score 35 \u2013 64</div></div>',
                unsafe_allow_html=True,
            )
        with rag3:
            st.markdown(
                f'<div style="background:{RED};border-radius:0.5rem;'
                f'padding:0.85rem 1.1rem;">'
                f'<div style="font-size:1.05rem;font-weight:700;color:#FFFFFF;">'
                f'\U0001f534 RED</div>'
                f'<div style="color:#FFFFFF;font-size:0.85rem;margin-top:0.2rem;">'
                f'Score \u2265 65</div></div>',
                unsafe_allow_html=True,
            )

        st.caption(
            "RAG thresholds are fixed in v1. Configurable in a future release."
        )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — Audit Log
# ═════════════════════════════════════════════════════════════════════════════
with tab_audit:
    st.subheader("Configuration Audit Log")
    st.caption(
        "This log is permanent and non-deletable. "
        "All changes are retained for audit purposes."
    )

    audit_df = query_df(
        "SELECT cal.changed_at, cal.field_name, cal.old_value, cal.new_value, "
        "cal.context_note, COALESCE(u.full_name, '') AS changed_by_name "
        "FROM config_audit_log cal "
        "LEFT JOIN users u ON u.id = cal.changed_by "
        "WHERE cal.table_name = 'risk_factor_config' "
        "ORDER BY cal.changed_at DESC LIMIT 200"
    )

    st.metric("Total Configuration Changes Logged", len(audit_df))

    if audit_df.empty:
        st.info("\u2139\ufe0f No configuration changes logged yet.")
    else:
        display_audit = audit_df.copy()
        display_audit["changed_at"] = pd.to_datetime(
            display_audit["changed_at"], errors="coerce"
        ).dt.strftime("%d %b %Y %H:%M")

        display_audit = display_audit.rename(
            columns={
                "changed_at":      "Changed At",
                "changed_by_name": "Changed By",
                "field_name":      "Field",
                "old_value":       "Old Value",
                "new_value":       "New Value",
                "context_note":    "Note",
            }
        )

        st.dataframe(display_audit, use_container_width=True, hide_index=True)
