# Cadence — HR Process Automation Hub

Four connected HR workflows. One platform. From headcount reporting to attrition risk.

---

## Live Demo

> **Deployment in progress** — this project is being prepared for Streamlit Community Cloud.
> Live URL will be published here after deployment.

**Demo credentials:** Not applicable — single-user demo deployment.

---

## Screenshots

| Screen | File |
|---|---|
| Home — workflow overview | `docs/screenshots/01_home.png` |
| Data Upload & Pipeline | `docs/screenshots/02_data_upload.png` |
| Workforce KPI Dashboard | `docs/screenshots/03_kpi_dashboard.png` |
| Weekly 1:1s | `docs/screenshots/04_weekly_1on1.png` |
| Monthly Check-ins | `docs/screenshots/05_monthly_checkin.png` |
| Quarterly Reviews | `docs/screenshots/06_quarterly_review.png` |
| Merit Cycle | `docs/screenshots/07_merit_cycle.png` |
| Eligibility & Recommendations | `docs/screenshots/08_eligibility.png` |
| Attrition Risk Register | `docs/screenshots/09_risk_register.png` |
| Scoring Configuration | `docs/screenshots/10_scoring_config.png` |

---

## What This Project Demonstrates

| Capability | Evidence |
|---|---|
| End-to-end business analysis — problem through deployed solution | Four workflows, each with a defined business problem, requirements document, and working implementation |
| Data pipeline design | CSV ingestion → schema validation → computed KPIs → database persistence with audit trail |
| Rules-based decision engine | Six-gate merit eligibility logic and seven-factor attrition risk scoring with configurable weights |
| Cross-workflow data integration | Performance ratings feed merit eligibility; headcount and pay data feed attrition risk scoring |
| Database design with analytical intent | Thirteen tables with FK chains that enforce the analytical dependencies between workflows |
| Requirements traceability | 45 functional requirements across four workflows, each traceable from FRD to code |
| Portfolio narrative continuity | Risk scoring engine is analytically connected to the companion compensation benchmarking project (S2) |

---

## The Business Problem

HR teams running manual workflows carry a hidden tax. A monthly headcount report takes hours of spreadsheet work. Merit reviews require someone to manually check six eligibility rules per employee. Performance conversations go undocumented and have to be reconstructed from memory at review time. And attrition risk — the signal that someone is about to leave — is only ever identified after they have already gone.

None of these problems is hard in isolation. What makes them costly is that they are solved separately, in different tools, by different people, with no shared data layer. Performance ratings that should influence merit eligibility live in one spreadsheet. Pay position data that should inform attrition risk lives in another. The result is that the same data gets re-entered, re-calculated, and re-interpreted across every cycle — and the analytical connections between these workflows are never exploited.

Cadence addresses this by treating the four HR workflows as a single connected system, built on a shared data foundation. Each workflow produces outputs that become inputs for the next. The result is not four tools — it is one platform where the work of each workflow compounds into better decisions in the next.

---

## BA Process

### Problem discovery

The starting point was not "build an HR system." It was observing that most HR operational work fails at the data handoff — not at the task itself. A performance rating is completed correctly but never makes it into the merit eligibility calculation. A headcount figure is accurate in the HRIS but has to be re-extracted manually for every reporting cycle. The analytical question driving this project was: what is the minimum data architecture that would allow these four workflows to talk to each other?

### Personas

Three personas shaped the requirements:

**The HR Analyst** needs to run reporting cycles without manual rework. They own the headcount upload, the KPI dashboard, and the merit eligibility engine. Their core frustration is data that arrives in one format and needs to be transformed into another before it can be used.

**The Manager** needs a lightweight, structured way to record 1:1 conversations, check-in progress against goals, and submit merit recommendations. Their core frustration is that HR asks for documentation that no tool makes easy to produce.

**The HR Business Partner** needs a risk view that surfaces who is at risk of leaving before the resignation arrives. Their core frustration is that by the time the signal is visible, it is too late.

### Scope decisions

The most significant scoping decision was the choice of a rules-based scoring engine over a predictive model for attrition risk. The rationale is documented in the Workflow Decisions artefact. In summary: a rules-based engine is auditable, configurable by the HR team without engineering support, and produces explainable outputs. A predictive model would require historical resignation data that a small or mid-size organisation rarely has in structured form. The rules engine is the right tool for the problem as stated; upgrading to ML is a Phase 2 decision, not a Phase 1 assumption.

A second scoping decision was the choice not to build role-scoped views (managers seeing only their direct reports) in version 1. This was deliberately deferred. The analytical architecture supports it — every record carries an employee ID and a manager ID — but building authentication and authorisation into a portfolio project before the core workflows are validated adds risk without proportionate value.

### Design decisions

The most important architectural decision was building the workflows in dependency order: headcount first, then performance management, then compensation review, then attrition risk. This was not a convenience decision. It reflects the actual data dependency chain. Attrition risk scoring cannot produce meaningful output without headcount data, performance ratings, and pay position — all of which must exist and be structured before the scoring engine can run. Building in this order kept the data model honest and prevented shortcuts that would have required later refactoring.

The second significant design decision was the use of a configurable weight table for the attrition risk scoring engine, rather than hardcoding factor weights. HR teams have different views on which risk signals matter most. Making the weights configurable via a UI page — rather than a config file or a code change — means the tool can be tuned to an organisation's context without a developer.

---

## Technology Decision

The full stack — Python, PostgreSQL via Supabase, Streamlit, and Plotly — is the established portfolio standard, documented in the master portfolio working file.

One decision worth noting: Streamlit Community Cloud rather than a hosted BI tool. Power BI Service and Tableau Online require paid licences for external sharing, which makes them unsuitable for a publicly accessible portfolio project. Streamlit Community Cloud is free, requires no account from the viewer, and supports all the chart types and interactivity this project needs. The tradeoff is a ~30-second cold start on the free tier, which is documented in the setup section below.

The database is PostgreSQL on Supabase's free tier, accessed via the connection pooler on port 6543. Direct connections on port 5432 are unreliable in Streamlit Cloud's serverless environment. All queries use psycopg2-binary with a `RealDictCursor` to return named columns, which prevents positional index errors when columns are added or reordered.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Data Sources                               │
│                                                                     │
│   Monthly headcount CSV export from HRIS                            │
│   (employee, grade, manager, salary, status, hire/term dates)       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ Upload & validate
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Workflow 1 — Workforce Intelligence                                │
│                                                                     │
│  Schema validation → KPI calculation → headcount_snapshots table    │
│  Outputs: active count, attrition rate, span of control,            │
│  compa-ratio by grade, headcount vs budget variance                 │
└──────────┬──────────────────────────────────────────┬───────────────┘
           │ headcount + pay data                     │ headcount data
           ▼                                          │
┌──────────────────────────────────────┐              │
│  Workflow 2 — Performance Management │              │
│                                      │              │
│  Weekly 1:1 capture → monthly        │              │
│  check-in tracking → quarterly       │              │
│  review aggregation → formal rating  │              │
│                                      │              │
│  Outputs: performance ratings,       │              │
│  check-in compliance, 1:1 frequency  │              │
└──────────┬───────────────────────────┘              │
           │ ratings + eligibility triggers           │
           ▼                                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Workflow 3 — Compensation Review                                   │
│                                                                     │
│  6-gate eligibility engine → budget pool calculation →              │
│  manager recommendation forms → HR approval workflow               │
│                                                                     │
│  Outputs: eligible employees, recommended increases,                │
│  budget utilisation, compa-ratio post-increase                      │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ pay position + merit recency
                                   │
           ┌───────────────────────┘
           │ + ratings trend + check-in frequency + tenure + sentiment
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Workflow 4 — Attrition Risk                                        │
│                                                                     │
│  7-factor scoring engine (configurable weights) → RAG status        │
│  → ranked risk register → retention action logging                  │
│                                                                     │
│  Factors: compa-ratio, rating trend, time since merit,              │
│  time in role, sentiment, check-in frequency, role risk             │
└─────────────────────────────────────────────────────────────────────┘

         PostgreSQL / Supabase  (13 tables, port 6543 pooler)
                    ↑  psycopg2-binary
         Streamlit + Plotly  →  Streamlit Community Cloud
```

---

## Repository Structure

```
cadence_hub/
├── app.py                          # Entry point — page config, sidebar, home render
├── utils/
│   ├── db.py                       # DB connection, query_df(), run_mutation()
│   ├── scoring.py                  # Attrition risk scoring engine logic
│   └── home.py                     # Home page queries, helpers, render_home()
├── pages/
│   ├── 1_WF1_Data_Upload.py        # Data Upload & Pipeline
│   ├── 2_WF1_Dashboard.py          # Workforce KPI Dashboard
│   ├── 3_WF4_Weekly_1on1.py        # Weekly 1:1s
│   ├── 4_WF4_Monthly_Checkin.py    # Monthly Check-ins
│   ├── 5_WF4_Quarterly_Review.py   # Quarterly Reviews
│   ├── 6_WF2_Merit_Cycle.py        # Merit Cycle
│   ├── 7_WF2_Eligibility.py        # Eligibility & Recommendations
│   ├── 8_WF3_Risk_Dashboard.py     # Attrition Risk Register
│   └── 9_WF3_Config.py             # Scoring Engine Configuration
├── docs/
│   ├── artifacts/                  # FRD, Data Dictionary, BPMN, UML diagrams
│   └── screenshots/                # App screenshots for this README
├── .streamlit/
│   └── config.toml                 # Dark theme, primary colour, font settings
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

---

## Page Descriptions

**Home**
The landing page renders a live platform snapshot the moment the app loads. Four workflow cards show the current state of each area — active employee count, attrition rate, check-in compliance, cycle deadline, and RAG risk counts — drawn from the database on each page load. A data flow banner at the base of the page makes the analytical connection between the four workflows visible to any reviewer using the app.

**Data Upload & Pipeline**
Accepts a monthly headcount CSV export, validates the schema against the required column specification, and runs the ingestion pipeline. The page reports row counts, validation errors, and skipped records in real time. Every upload is logged to a pipeline run log with a timestamp, row count, and the ID of the user who ran it — creating a permanent audit trail for the headcount data. After ingestion, computed columns (compa-ratio, headcount delta, new hire flag) are calculated and stored alongside the raw data.

**Workforce KPI Dashboard**
Displays the current headcount picture across five KPI tiles — active employees, attrition rate, new hires, span of control, and headcount vs budget variance — with period-over-period delta arrows. A grade distribution chart shows the workforce by salary band. Department filters allow the view to be scoped to a subset of the organisation. All figures are drawn from the most recently uploaded reporting period.

**Weekly 1:1s**
A structured capture form for weekly manager–employee conversations. Each record stores the week start date, discussion topics, any flagged concerns, agreed actions, and a completion status. The form is designed to take less than three minutes to complete, reducing the barrier to consistent documentation. Completed records feed into the monthly check-in summary so nothing needs to be re-entered at month end.

**Monthly Check-ins**
Displays check-in completion rates for the current month across all manager–employee pairs. Managers record goal progress against the targets set at the start of the period; employees acknowledge the check-in once reviewed. The compliance metric — percentage of pairs with an acknowledged check-in — feeds directly into the attrition risk score as a proxy for engagement. Late or missing check-ins are flagged in amber.

**Quarterly Reviews**
Aggregates the weekly 1:1 notes and monthly check-in records from the preceding quarter into a structured review summary. The manager reviews the auto-generated summary, edits the narrative as needed, assigns a formal performance rating, and submits for HR approval. The rating produced here is the primary input to the merit eligibility engine and contributes to the rating trend factor in attrition risk scoring.

**Merit Cycle**
Manages the lifecycle of a merit review cycle from open to closed. The cycle definition sets the budget envelope, the submission deadline, and the eligible population. The page shows budget utilisation in real time as manager recommendations are submitted — total recommended increase versus available budget, broken down by department. HR can close the cycle once all recommendations are approved.

**Eligibility & Recommendations**
Runs the six-gate eligibility engine against the active merit cycle and displays the results. The six gates are: active employment status, minimum tenure, no active performance improvement plan, rating threshold met, time elapsed since last merit increase, and headcount budget confirmed. An employee must pass all six to be eligible. Managers enter their recommended increase percentage for each eligible direct report; the form enforces the budget cap and shows the resulting compa-ratio post-increase.

**Attrition Risk Register**
Displays the ranked attrition risk register for the most recent scoring run. Each employee is assigned a RAG status (Red, Amber, Green) based on their composite risk score across seven factors. The register can be filtered by RAG status, department, and manager. Clicking through to an employee record shows the per-factor score breakdown and any open retention actions. HR can log a retention action directly from this page.

**Scoring Engine Configuration**
Allows HR administrators to adjust the weight assigned to each of the seven risk factors without a code change. The seven factors are: compa-ratio position, rating trend, time since last merit increase, time in current role, sentiment signal from 1:1 notes, check-in frequency, and role market risk. Weights must sum to 1.0; the page enforces this constraint and prevents saving an invalid configuration. Every configuration change is written to an audit log with a timestamp and the previous values.

---

## Setup Instructions

### Prerequisites

- Python 3.9 or later
- A Supabase project with the Cadence schema applied (SQL in `docs/artifacts/`)
- Git

### Clone the repository

```powershell
git clone https://github.com/hadimercer/cadence_hr_hub.git
cd cadence_hr_hub
```

### Install dependencies

```powershell
pip install -r requirements.txt
```

### Configure environment variables

Create a `.env` file in the project root:

```
DB_HOST=your-supabase-pooler-host.supabase.com
DB_PORT=6543
DB_NAME=postgres
DB_USER=postgres.your-project-ref
DB_PASSWORD=your-password
```

Use the **Transaction mode pooler** connection string from Supabase → Project Settings → Database → Connection Pooling. Port must be 6543, not 5432.

### Run locally

```powershell
python -m streamlit run app.py
```

The app will be available at `http://localhost:8501`.

### Deploy to Streamlit Community Cloud

1. Push the repository to GitHub. Confirm `.env` and `CLAUDE.md` are listed in `.gitignore` and are not committed.
2. Connect the repository at [share.streamlit.io](https://share.streamlit.io).
3. Add each environment variable under **Secrets** in the app settings, using the same key names as `.env`. Values must be quoted: `DB_HOST = "your-host.supabase.com"`.
4. Click **Deploy**. First load takes up to 30 seconds on the free tier while the container initialises.

---

## Portfolio Artifacts

| Artifact | File | Traces To |
|---|---|---|
| Functional Requirements Document | `docs/artifacts/Cadence_FRD_001.docx` | All FR IDs in Section 13 below |
| Data Dictionary | `docs/artifacts/Cadence_Data_Dictionary_v0_2.docx` | All 13 database tables |
| Workflow Decisions | `docs/artifacts/S1_Workflow_Decisions_Final.docx` | BA Process section above |
| BPMN Process Diagrams | `docs/artifacts/cadence_bpmn_all.html` | All four workflow descriptions |
| UML Diagram | `docs/artifacts/cadence_uml.html` | Repository structure and DB schema |
| Live Application | Streamlit Community Cloud — URL TBA | All functional requirements |
| Source Code | [github.com/hadimercer/cadence_hr_hub](https://github.com/hadimercer/cadence_hr_hub) | All FR IDs |

---

## Functional Requirements Coverage

All 45 functional requirements are implemented in version 1.

### Workflow 1 — Workforce Intelligence

| FR ID | Requirement | Status |
|---|---|---|
| WF1-FR-001 | Accept CSV upload of monthly headcount export | ✅ Implemented |
| WF1-FR-002 | Validate uploaded file against required column schema | ✅ Implemented |
| WF1-FR-003 | Report validation errors with row-level detail | ✅ Implemented |
| WF1-FR-004 | Persist validated headcount records to database | ✅ Implemented |
| WF1-FR-005 | Calculate attrition rate for the reporting period | ✅ Implemented |
| WF1-FR-006 | Calculate compa-ratio for each employee against grade band | ✅ Implemented |
| WF1-FR-007 | Display KPI dashboard with period-over-period delta | ✅ Implemented |
| WF1-FR-008 | Write a pipeline run log entry for every upload | ✅ Implemented |

### Workflow 2 — Performance Management

| FR ID | Requirement | Status |
|---|---|---|
| WF4-FR-001 | Capture weekly 1:1 record with structured fields | ✅ Implemented |
| WF4-FR-002 | Record discussion topics, flagged concerns, and agreed actions | ✅ Implemented |
| WF4-FR-003 | Track completion status for each 1:1 record | ✅ Implemented |
| WF4-FR-004 | Display weekly 1:1 completion rate for the current period | ✅ Implemented |
| WF4-FR-005 | Capture monthly check-in with goal progress | ✅ Implemented |
| WF4-FR-006 | Record employee acknowledgement of check-in | ✅ Implemented |
| WF4-FR-007 | Display check-in compliance rate for current month | ✅ Implemented |
| WF4-FR-008 | Flag late or missing check-ins | ✅ Implemented |
| WF4-FR-009 | Auto-aggregate 1:1 and check-in data into quarterly review summary | ✅ Implemented |
| WF4-FR-010 | Allow manager to edit quarterly review narrative | ✅ Implemented |
| WF4-FR-011 | Capture formal performance rating on quarterly review | ✅ Implemented |
| WF4-FR-012 | Submit quarterly review for HR approval | ✅ Implemented |
| WF4-FR-013 | Display pending HR approvals | ✅ Implemented |
| WF4-FR-014 | Pass approved rating to merit eligibility engine | ✅ Implemented |

### Workflow 3 — Compensation Review

| FR ID | Requirement | Status |
|---|---|---|
| WF2-FR-001 | Create and open a merit cycle with budget and deadline | ✅ Implemented |
| WF2-FR-002 | Run six-gate eligibility check for all employees in scope | ✅ Implemented |
| WF2-FR-003 | Display per-gate eligibility result for each employee | ✅ Implemented |
| WF2-FR-004 | Gate 1 — Active employment status | ✅ Implemented |
| WF2-FR-005 | Gate 2 — Minimum tenure requirement | ✅ Implemented |
| WF2-FR-006 | Gate 3 — No active performance improvement plan | ✅ Implemented |
| WF2-FR-007 | Gate 4 — Performance rating at or above threshold | ✅ Implemented |
| WF2-FR-008 | Gate 5 — Minimum elapsed time since last merit increase | ✅ Implemented |
| WF2-FR-009 | Gate 6 — Headcount budget confirmed for role | ✅ Implemented |
| WF2-FR-010 | Allow manager to enter recommended increase for eligible employees | ✅ Implemented |
| WF2-FR-011 | Enforce budget cap and display real-time utilisation | ✅ Implemented |
| WF2-FR-012 | Close merit cycle once all recommendations are approved | ✅ Implemented |

### Workflow 4 — Attrition Risk

| FR ID | Requirement | Status |
|---|---|---|
| WF3-FR-001 | Calculate composite attrition risk score for each active employee | ✅ Implemented |
| WF3-FR-002 | Score Factor 1 — compa-ratio position against grade band | ✅ Implemented |
| WF3-FR-003 | Score Factor 2 — performance rating trend over rolling window | ✅ Implemented |
| WF3-FR-004 | Score Factor 3 — time elapsed since last merit increase | ✅ Implemented |
| WF3-FR-005 | Score Factor 4 — time in current role | ✅ Implemented |
| WF3-FR-006 | Score Factor 5 — sentiment signal from 1:1 notes | ✅ Implemented |
| WF3-FR-007 | Score Factor 6 — check-in frequency and compliance | ✅ Implemented |
| WF3-FR-008 | Score Factor 7 — role market risk flag | ✅ Implemented |
| WF3-FR-009 | Assign RAG status based on composite score thresholds | ✅ Implemented |
| WF3-FR-010 | Display ranked risk register with per-factor breakdown | ✅ Implemented |
| WF3-FR-011 | Allow HR to log and track retention actions per employee | ✅ Implemented |

---

## Continuous Improvement Roadmap

| Phase | Enhancement | Rationale |
|---|---|---|
| **Phase 1 — Polish** | Multi-period headcount uploads with trend analysis | Single-period comparison is useful; trend lines across 6–12 months are where patterns become actionable |
| **Phase 1 — Polish** | Email notifications for merit outcomes and check-in reminders | Removes the need for HR to chase managers; notifications are the last mile of process adoption |
| **Phase 1 — Polish** | Manager-scoped views (direct reports only) | The data architecture already supports this; the remaining work is authentication and row-level filtering |
| **Phase 2 — Intelligence** | Predictive attrition modelling as an ML upgrade to the rules engine | Once organisations have 12+ months of structured data, a classification model can replace or supplement the rules engine |
| **Phase 2 — Intelligence** | Compensation band refresh automation | Connect to BLS or market survey data to flag when a band is falling behind market without manual analysis |
| **Phase 2 — Intelligence** | Cross-portfolio API link to S2 BLS benchmark data | The analytical connection between Cadence and TechNova (S2) currently exists in the portfolio narrative; making it a live data link would close the loop at the platform level |
| **Phase 3 — Scale** | Multi-tenancy with organisation isolation | Allows Cadence to serve multiple clients, each with their own data boundary, without separate deployments |
| **Phase 3 — Scale** | HRIS direct integration to replace CSV upload | Removes the manual extraction step; data arrives on a schedule rather than requiring a human trigger |
| **Phase 3 — Scale** | Mobile-responsive layout | Managers completing 1:1 records immediately after a conversation need a mobile-friendly form |

---

## Portfolio Context

| # | Project | Label | Status | Connection |
|---|---|---|---|---|
| **S1** | **Cadence — HR Process Automation Hub** | Small 1 | **This project** | Attrition risk scoring draws on pay position data from S2 |
| S2 | TechNova — Compensation Intelligence Dashboard | Small 2 | ✅ Live | Identifies roles below market; Cadence identifies which employees in those roles are at highest risk |
| S3 | Meridian — Portfolio Health Dashboard | Small 3 | ✅ Live | — |
| S4 | Sentiment & Text Analytics Tool | Small 4 | In development | — |
| F1 | Operational Process Intelligence Platform | Flagship 1 | Planned | — |
| F2 | Business Analysis Co-Pilot | Flagship 2 | Planned | — |

**Cross-portfolio note:** TechNova (S2) and Cadence (S1) are analytically connected. TechNova operates at role level, identifying which job families are below the BLS market benchmark. Cadence operates at employee level, identifying which individuals in those underpaid roles score highest on attrition risk. Together they answer the question a CHRO actually asks: *which people are we most likely to lose, and is compensation the reason?*

---

## Contact

**Hadi Mercer** — Business Analyst Portfolio 2026
[github.com/hadimercer](https://github.com/hadimercer)
