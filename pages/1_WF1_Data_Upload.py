import streamlit as st
import pandas as pd
import json
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


st.set_page_config(page_title="Data Upload & Pipeline \u2014 Cadence", layout="wide")

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

page_header("Data Upload & Pipeline", "Upload monthly HRIS exports. Validates schema, ingests records, and logs every run.")

if st.session_state.get("upload_complete"):
    st.session_state["upload_complete"] = False
    st.success("Ingest complete. You can upload another file or view the KPI Dashboard.")
    log_df = query_df(
        "SELECT run_timestamp, reporting_period, status, records_processed, "
        "records_rejected, is_overwrite FROM pipeline_run_log "
        "ORDER BY run_timestamp DESC LIMIT 10"
    )
    st.subheader("Recent Pipeline Runs")
    if log_df.empty:
        st.info("No pipeline runs yet.")
    else:
        st.dataframe(log_df, use_container_width=True)
    st.stop()

_SYSTEM_USER = "2ad731c3-80c2-4848-a29d-e14361113cfb"
REQUIRED_COLS = {
    "employee_id", "first_name", "last_name", "department", "cost_centre",
    "location", "job_title", "job_family", "level", "employment_type",
    "manager_id", "hire_date", "role_start_date", "salary", "salary_grade",
    "budgeted_headcount", "status", "reporting_period",
}

# SECTION 1 — Upload Widget
st.subheader("Upload Headcount CSV")
uploaded_file = st.file_uploader("Upload Headcount CSV", type=["csv"])
st.caption(
    "Required columns: employee_id, first_name, last_name, department, "
    "cost_centre, location, job_title, job_family, level, employment_type, "
    "manager_id, hire_date, role_start_date, salary, salary_grade, "
    "budgeted_headcount, status, reporting_period"
)

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df.columns = [c.lower().strip() for c in df.columns]

    can_proceed = True

    # Step 1 — Schema check
    missing_cols = REQUIRED_COLS - set(df.columns)
    if missing_cols:
        st.error(f"Missing required columns: {', '.join(sorted(missing_cols))}")
        can_proceed = False

    # Step 2 — reporting_period check
    reporting_period = None
    if can_proceed:
        try:
            parsed_periods = pd.to_datetime(df["reporting_period"]).dt.date
            unique_periods = list(parsed_periods.unique())
            if len(unique_periods) > 1:
                st.error(f"Multiple reporting periods found: {unique_periods}. File must contain exactly one reporting period.")
                can_proceed = False
            else:
                reporting_period = unique_periods[0]
        except Exception:
            st.error("Could not parse 'reporting_period' column as dates. Ensure all values are valid date strings.")
            can_proceed = False

    # Step 3 — Duplicate check
    is_overwrite = False
    show_ingest = True
    if can_proceed:
        dup_result = query_df(
            "SELECT COUNT(*) AS cnt FROM headcount_snapshots WHERE reporting_period = %s",
            (str(reporting_period),)
        )
        existing_count = int(dup_result["cnt"].iloc[0]) if not dup_result.empty else 0
        if existing_count > 0:
            st.warning(f"{existing_count} rows already exist for period {reporting_period}.")
            is_overwrite = st.checkbox("Overwrite existing data for this period?")
            if not is_overwrite:
                st.info("Check the box above to proceed with overwrite, or upload a CSV for a different period.")
                show_ingest = False

    # Step 4 — Row-level validation
    valid_indices = []
    rejected_rows = []
    for idx, row in df.iterrows():
        reasons = []

        # employee_id check
        eid = row.get("employee_id", None)
        if eid is None or (isinstance(eid, float) and pd.isna(eid)) or str(eid).strip() == "":
            reasons.append("employee_id is null or empty")

        # salary check
        try:
            sal = float(row["salary"])
            if sal <= 0:
                reasons.append("salary must be > 0")
        except (ValueError, TypeError):
            reasons.append("salary is not a valid number")

        # status check
        try:
            status_val = str(row["status"]).upper().strip()
            if status_val not in ("ACTIVE", "LEAVER"):
                reasons.append(f"status '{row['status']}' is not ACTIVE or LEAVER")
            else:
                df.at[idx, "status"] = status_val
        except Exception:
            reasons.append("status could not be parsed")

        # hire_date check
        try:
            pd.to_datetime(row["hire_date"])
        except Exception:
            reasons.append(f"hire_date '{row.get('hire_date')}' is not a valid date")

        if reasons:
            rejected_rows.append({
                "row": int(idx),
                "employee_id": str(row.get("employee_id", "")),
                "reasons": reasons,
            })
        else:
            valid_indices.append(idx)

    valid_df = df.loc[valid_indices].copy()

    # Validation summary
    col_v1, col_v2 = st.columns(2)
    col_v1.metric("Valid rows", len(valid_df))
    col_v2.metric("Rejected rows", len(rejected_rows))
    if rejected_rows:
        with st.expander("Rejected row details (first 10)"):
            st.json(rejected_rows[:10])

    if show_ingest:
        st.info(
            f"Ready to ingest: {len(valid_df)} records for {reporting_period}\n"
            f"{len(valid_df)} rows passed validation \u00b7 {len(rejected_rows)} rows will be rejected"
        )

    # SECTION 3 — INGESTION
    if show_ingest and st.button("Confirm and Ingest", type="primary", disabled=len(valid_df) == 0):
        with st.spinner("Inserting records..."):

            # Pre-compute derived columns
            rp_ts = pd.Timestamp(reporting_period)
            valid_df["hire_date"] = pd.to_datetime(valid_df["hire_date"]).dt.date
            valid_df["role_start_date"] = pd.to_datetime(valid_df["role_start_date"]).dt.date
            if "termination_date" in valid_df.columns:
                valid_df["termination_date"] = pd.to_datetime(valid_df["termination_date"], errors="coerce").dt.date
            else:
                valid_df["termination_date"] = None
            if "termination_type" not in valid_df.columns:
                valid_df["termination_type"] = None

            tenure_months = ((rp_ts - pd.to_datetime(valid_df["hire_date"])).dt.days / 30.44).round(1)
            tenure_in_role_months = ((rp_ts - pd.to_datetime(valid_df["role_start_date"])).dt.days / 30.44).round(1)
            is_new_hire = tenure_months <= 3
            headcount_delta = 0

            valid_df["tenure_months"] = tenure_months.values
            valid_df["tenure_in_role_months"] = tenure_in_role_months.values
            valid_df["is_new_hire"] = is_new_hire.values

            if is_overwrite:
                run_mutation(
                    "DELETE FROM headcount_snapshots WHERE reporting_period = %s",
                    (str(reporting_period),)
                )

            # Build batch INSERT
            row_ph = "(" + ", ".join(["%s"] * 25) + ", NOW())"

            params_list = []
            for idx, row in valid_df.iterrows():
                term_date = row["termination_date"]
                if term_date is not None and pd.isna(term_date):
                    term_date = None

                term_type = row["termination_type"]
                if term_type is not None and (isinstance(term_type, float) and pd.isna(term_type)):
                    term_type = None

                row_tuple = (
                    str(reporting_period),
                    str(row["employee_id"]),
                    str(row["first_name"]),
                    str(row["last_name"]),
                    str(row["department"]),
                    str(row["cost_centre"]),
                    str(row["location"]),
                    str(row["job_title"]),
                    str(row["job_family"]),
                    str(row["level"]),
                    str(row["employment_type"]),
                    str(row["manager_id"]),
                    row["hire_date"],
                    row["role_start_date"],
                    term_date,
                    term_type,
                    float(row["salary"]),
                    str(row["salary_grade"]),
                    float(row["budgeted_headcount"]),
                    str(row["status"]),
                    float(row["tenure_months"]),
                    float(row["tenure_in_role_months"]),
                    bool(row["is_new_hire"]),
                    headcount_delta,
                    _SYSTEM_USER,
                )
                params_list.append(row_tuple)

            all_row_phs = ", ".join([row_ph] * len(params_list))
            insert_sql = (
                f"INSERT INTO headcount_snapshots ("
                f"reporting_period, employee_id, first_name, last_name, department, "
                f"cost_centre, location, job_title, job_family, level, employment_type, "
                f"manager_id, hire_date, role_start_date, termination_date, termination_type, "
                f"salary, salary_grade, budgeted_headcount, status, tenure_months, "
                f"tenure_in_role_months, is_new_hire, headcount_delta, uploaded_by, uploaded_at"
                f") VALUES {all_row_phs}"
            )
            flat_params = tuple(v for row_p in params_list for v in row_p)

            ingest_ok = False
            try:
                run_mutation(insert_sql, flat_params)
                ingest_ok = True
            except Exception as e:
                st.error(f"Database error during insert: {str(e)}")

            if ingest_ok:
                records_processed = len(valid_df)
                records_rejected = len(rejected_rows)

                if records_rejected == 0:
                    run_status = "SUCCESS"
                elif records_processed > 0:
                    run_status = "PARTIAL"
                else:
                    run_status = "FAILED"

                validation_warnings = (
                    json.dumps([r["reasons"] for r in rejected_rows[:10]])
                    if rejected_rows else None
                )
                rejection_detail = (
                    json.dumps(rejected_rows[:10])
                    if rejected_rows else None
                )
                new_hire_count = int(valid_df["is_new_hire"].sum())
                leaver_count = int((valid_df["status"] == "LEAVER").sum())

                log_sql = (
                    "INSERT INTO pipeline_run_log ("
                    "id, run_timestamp, triggered_by, reporting_period, total_records, "
                    "records_processed, records_rejected, new_hire_count, leaver_count, "
                    "threshold_flags_raised, validation_warnings, rejection_detail, status, is_overwrite"
                    ") VALUES (gen_random_uuid(), NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                )
                run_mutation(
                    log_sql,
                    (
                        _SYSTEM_USER,
                        str(reporting_period),
                        len(df),
                        records_processed,
                        records_rejected,
                        new_hire_count,
                        leaver_count,
                        0,
                        validation_warnings,
                        rejection_detail,
                        run_status,
                        is_overwrite,
                    )
                )

                query_df.clear()
                st.success(f"Ingest complete. {records_processed} records loaded for {reporting_period}.")
                st.balloons()
                st.session_state["upload_complete"] = True
                st.rerun()

# SECTION 4 — PIPELINE RUN LOG (always visible)
st.divider()
st.subheader("Recent Pipeline Runs")
log_df = query_df(
    "SELECT run_timestamp, reporting_period, status, records_processed, records_rejected, is_overwrite "
    "FROM pipeline_run_log ORDER BY run_timestamp DESC LIMIT 10"
)
if log_df.empty:
    st.info("No pipeline runs yet.")
else:
    def _color_status(val):
        colors = {"SUCCESS": "#2ECC7A", "PARTIAL": "#E8A838", "FAILED": "#E05252"}
        c = colors.get(val, "")
        return f"color: {c}" if c else ""

    styled = log_df.style.map(_color_status, subset=["status"])
    st.dataframe(styled, use_container_width=True)
