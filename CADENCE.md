# CLAUDE.md — Cadence HR Process Automation Hub
# Project S1 | Hadi Mercer | BA Portfolio 2026
# Last updated: March 2026 — Pre-build setup complete
#
# ─────────────────────────────────────────────────────────────────────────────
# HOW TO USE THIS FILE
# ─────────────────────────────────────────────────────────────────────────────
# This is the project-level CLAUDE.md for Cadence. It lives at the root of
# the cadence_hub repo and is read automatically by every Claude Code session
# and every sub-agent spawned during multi-agent builds.
#
# When writing prompts for Claude Code, you do NOT need to re-explain the
# tech stack, database schema, colour palette, or workflow architecture.
# Everything is here. Reference it by section number in your prompts.
#
# UPDATE TRIGGERS — update this file when:
#   1. A new page is completed → add to Section 9 (Build Status)
#   2. A DB query pattern is established → add to Section 6
#   3. A bug takes >30 min to find → add to Section 12
#   4. A skill/agent pattern produces notably better results → add to Section 8
#   5. Any deployment step causes friction → add to Section 11
# ─────────────────────────────────────────────────────────────────────────────

---

## 1. PROJECT IDENTITY

| Field | Value |
|---|---|
| Project name | Cadence — HR Process Automation Hub |
| Portfolio label | S1 (Small Project 1 of 6) |
| GitHub repo | https://github.com/hadimercer/cadence_hr_hub |
| Streamlit deployment | TBD — Streamlit Community Cloud |
| Supabase project | cadence_hub (free tier) |
| Status | Pre-build — schema complete, seed data loaded, ready to code |

**Portfolio narrative thread:**
S2 (live) identified which roles are below market at the BLS benchmark level.
Cadence WF3 identifies which individual employees in those roles are at highest
attrition risk because of it. S2 operates at role level; Cadence at employee level.
This cross-portfolio connection is surfaced explicitly in WF3's Pay Risk factor tooltip.

---

## 2. THE FOUR WORKFLOWS — ARCHITECTURE OVERVIEW

The workflows are analytically connected, not just thematically grouped.
This hub architecture is the central design principle and the primary portfolio claim.

```
WF1 (Headcount Reporting) ──────────────────────────────► WF3 (Attrition Risk)
      │                                                          ▲
      │ headcount + compa-ratio data                             │
      ▼                                                          │
WF2 (Compensation Review) ──── compa-ratio, pay position ───────┤
      ▲                                                          │
      │ performance ratings + eligibility                        │
      │                                                          │
WF4 (Performance Management) ── check-in frequency, trend ──────┘
```

| Code | Workflow | Type | Core Question |
|---|---|---|---|
| WF1 | Headcount & Workforce Reporting | Descriptive | What is our workforce today? |
| WF4 | Performance Management Cycle | Operational | How are people performing? |
| WF2 | Compensation Review Cycle | Operational | Who is eligible for merit? |
| WF3 | Attrition Risk Scoring Engine | Diagnostic | Who is at risk of leaving? |

**Build order:** WF1 → WF4 → WF2 → WF3
Reason: each workflow produces data consumed by the next. WF3 cannot run
without data from all three preceding workflows.

---

## 3. LOCKED TECH STACK

**Never deviate from this stack without a documented reason.**

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.9+ | |
| Database | PostgreSQL via Supabase (free tier) | Pooler port 6543 on Cloud |
| Dashboard | Streamlit | Community Cloud deployment |
| Charts | Plotly (`plotly.express` + `plotly.graph_objects`) | Never matplotlib |
| DB connector | psycopg2-binary | |
| Env management | python-dotenv (.env file) | Never hardcode credentials |
| Deployment | Streamlit Community Cloud | share.streamlit.io |
| Version control | GitHub | hadimercer/cadence_hr_hub |

### requirements.txt
```
streamlit
plotly
pandas
psycopg2-binary
python-dotenv
requests
```

### .streamlit/config.toml (locked — always commit this)
```toml
[theme]
base = "dark"
primaryColor = "#4DB6AC"
backgroundColor = "#0E1117"
secondaryBackgroundColor = "#262730"
textColor = "#FAFAFA"
```

### Environment variables (.env — never commit)
```
DB_HOST=your-supabase-pooler-host
DB_PORT=6543
DB_NAME=postgres
DB_USER=postgres.your-project-ref
DB_PASSWORD=your-password
```

---

## 4. DATABASE SCHEMA — TABLE INVENTORY

All tables are in the `public` schema on Supabase.
Seed data is loaded: 8 managers (E1001–E1008), 112 ICs (E2001–E2112).

| Table | Workflow | Purpose |
|---|---|---|
| `users` | Cross-cutting | App roles: HR_ADMIN, HR_ANALYST, MANAGER, CHRO, FINANCE |
| `salary_bands` | WF1/WF2/WF3 | Grade bands with min/midpoint/max. Drives compa-ratio. |
| `headcount_snapshots` | WF1 | Monthly employee master. FK target for all other workflows. |
| `pipeline_run_log` | WF1 | Audit trail for every CSV upload and pipeline run. |
| `performance_reviews` | WF4 | Quarterly review lifecycle from self-assessment to HR approval. |
| `one_on_ones` | WF4 | Weekly 1:1 records with sentiment flags. MISSED status feeds WF3. |
| `monthly_checkins` | WF4 | Monthly check-in records with goal progress and acknowledgement. |
| `merit_cycles` | WF2 | Merit cycle definitions — open/closed/draft. |
| `merit_eligibility` | WF2 | 6-gate eligibility determination per employee per cycle. |
| `merit_recommendations` | WF2 | Manager merit recommendations with budget tracking. |
| `risk_factor_config` | WF3 | Configurable scoring factors with weights and thresholds. |
| `attrition_risk_scores` | WF3 | Daily score history per employee. 14 days seeded. |
| `retention_actions` | WF3 | Open retention interventions for RED/AMBER employees. |
| `config_audit_log` | Cross-cutting | Non-deletable audit trail for all config changes. |

### Critical FK chain (know this before writing any query)
```
users ← headcount_snapshots (uploaded_by, soft ref employee_id)
salary_bands ← headcount_snapshots (salary_grade)
headcount_snapshots ← performance_reviews, one_on_ones, monthly_checkins,
                       merit_eligibility, merit_recommendations,
                       attrition_risk_scores, retention_actions (all via employee_id)
merit_cycles ← merit_eligibility, merit_recommendations (cycle_id)
users ← all tables with manager_id, flagged_by, opened_by, approved_by etc.
```

### Key constraint: uq_headcount_employee_id
`employee_id` is unique in `headcount_snapshots`. Current seed has one
reporting_period (2026-03-01). Future monthly uploads must upsert, not insert.
Always filter current state with:
```sql
WHERE reporting_period = (SELECT MAX(reporting_period) FROM headcount_snapshots)
```

### WF3 score column → factor_code mapping
| Column | factor_code | Weight |
|---|---|---|
| score_compa_ratio | COMPA_RATIO | 0.15 |
| score_rating_trend | RATING_TREND | 0.20 |
| score_time_since_merit | TIME_SINCE_MERIT | 0.15 |
| score_time_in_role | TIME_IN_ROLE | 0.10 |
| score_sentiment | SENTIMENT | 0.15 |
| score_checkin_freq | CHECKIN_FREQ | 0.15 |
| score_role_risk | ROLE_RISK | 0.10 |

---

## 5. VISUAL DESIGN STANDARD

**Dark theme only. High contrast. No pastels. No white backgrounds on charts.**

### Colour palette
```python
BG         = "#0E1117"   # Streamlit dark background
SURFACE    = "#262730"   # Cards, sidebar, containers
ACCENT     = "#4DB6AC"   # Primary — teal (Streamlit primaryColor)
GOLD       = "#D4A843"   # Secondary — merit/compensation highlight
RED        = "#E05252"   # Danger / attrition RED
AMBER      = "#E8A838"   # Warning / attrition AMBER
GREEN      = "#2ECC7A"   # Safe / attrition GREEN
TEXT       = "#FAFAFA"   # Primary text
MUTED      = "#8892A4"   # Secondary text / labels
BORDER     = "#1A2535"   # Dividers
```

### Plotly chart standard (apply to every chart)
```python
fig.update_layout(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#FAFAFA"),
    legend=dict(font=dict(color="#FAFAFA")),
)
```

### RAG status colours
```python
RAG_COLORS = {"RED": "#E05252", "AMBER": "#E8A838", "GREEN": "#2ECC7A"}
```

---

## 6. DATABASE CONNECTION PATTERN

**Always use this pattern. Never deviate.**

```python
import psycopg2
import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode="require"
    )

@st.cache_data(ttl=300)
def run_query(sql, params=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)

def run_mutation(sql, params=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    run_query.clear()  # Always clear cache after any write
```

### UUID IN clause pattern (critical — avoids 0 rows bug)
```python
# WRONG — type mismatch causes 0 rows returned
cur.execute("SELECT * FROM users WHERE id = ANY(%s)", (id_list,))

# CORRECT — cast to text array
placeholders = ",".join(["%s"] * len(id_list))
cur.execute(f"SELECT * FROM users WHERE id::text IN ({placeholders})",
            [str(i) for i in id_list])
```
# 2-hop manager resolution pattern (used in WF4, reuse in WF2/WF3)
# headcount_snapshots.manager_id (TEXT) → users.id (UUID)
SELECT u.id FROM headcount_snapshots h
JOIN users u ON u.employee_id = h.manager_id
WHERE h.employee_id = %s
LIMIT 1
# Fallback: _SYSTEM_USER if no match
```

---

## 7. APP STRUCTURE

```
cadence_hub/
├── app.py                    # Entry point — navigation + sidebar
├── pages/
│   ├── 1_WF1_Data_Upload.py
│   ├── 2_WF1_Dashboard.py
│   ├── 3_WF4_Weekly_1on1.py
│   ├── 4_WF4_Monthly_Checkin.py
│   ├── 5_WF4_Quarterly_Review.py
│   ├── 6_WF2_Merit_Cycle.py
│   ├── 7_WF2_Eligibility.py
│   ├── 8_WF3_Risk_Dashboard.py
│   └── 9_WF3_Config.py
├── utils/
│   ├── db.py                 # get_connection(), run_query(), run_mutation()
│   ├── auth.py               # Role checking helpers
│   └── scoring.py            # WF3 scoring engine logic
├── .streamlit/
│   └── config.toml
├── .env                      # Never commit
├── .gitignore
├── requirements.txt
└── CLAUDE.md                 # This file
```

### Sidebar pattern (duplicate in every page — do not abstract)
```python
with st.sidebar:
    st.markdown("### Cadence")
    st.markdown("HR Process Automation Hub")
    st.divider()
    st.markdown("**Workflow**")
    st.page_link("pages/1_WF1_Data_Upload.py", label="WF1 — Data Upload")
    st.page_link("pages/2_WF1_Dashboard.py",   label="WF1 — Dashboard")
    # ... etc
```

---

## 8. SKILLS & AGENTS PLAN

### Which skill to invoke per session

Invoke skills at the START of a Claude Code session, before describing the task.
Syntax: `Use the [skill-name] skill. We are building [task description]...`

| Session | Primary Skill | Secondary Skill | Task |
|---|---|---|---|
| WF1 build | `senior-data-engineer` | `senior-backend` | CSV ingestion, KPI engine, pipeline log |
| WF1 UI | `senior-frontend` | `frontend-design` | Upload page, KPI dashboard |
| WF4 build | `senior-fullstack` | `senior-backend` | 1:1, check-in, quarterly review pages |
| WF2 build | `senior-backend` | `senior-fullstack` | Eligibility engine, merit cycle pages |
| WF3 build | `senior-data-engineer` | `senior-backend` | Scoring engine, risk register |
| WF3 UI | `senior-frontend` | `frontend-design` | Risk dashboard, RAG display, charts |
| Polish pass | `frontend-design` | `code-reviewer` | Visual consistency across all pages |
| Pre-deploy | `code-reviewer` | `senior-secops` | Final review before Streamlit Cloud push |

### Multi-agent pattern for Cadence

Use sub-agents to build pages within a workflow in parallel.
Always launch Claude Code from the cadence_hub project root.

**Example — WF4 multi-agent prompt:**
```
Use the senior-fullstack skill.
Build WF4 using subagents in parallel:
- Agent A: pages/3_WF4_Weekly_1on1.py
- Agent B: pages/4_WF4_Monthly_Checkin.py
- Agent C: pages/5_WF4_Quarterly_Review.py
All agents must use utils/db.py for database access.
Read CLAUDE.md Section 4 for the schema and Section 6 for the DB pattern.
Do not start coding until you have read both sections.
```

**Safe flag for autonomous builds (cadence_hub folder only):**
```powershell
claude --dangerously-skip-permissions
```
Only use this inside cadence_hub. Never run at C:/ root level.

### Agent briefing rule
Every agent prompt must reference:
- Section 4 (schema) for any DB work
- Section 5 (colours) for any UI work
- Section 6 (DB pattern) for any query work
- Section 9 (build status) to know what's already done

---

## 9. BUILD STATUS

Track completed pages here. Update after every session.

| Page | File | Status | Notes |
|---|---|---|---|
| WF1 — Data Upload | pages/1_WF1_Data_Upload.py | ✅ Complete. | |
| WF1 — Dashboard | pages/2_WF1_Dashboard.py | ✅ Complete. | |
| WF4 — Weekly 1:1 | pages/3_WF4_Weekly_1on1.py | ✅ Complete. | |
| WF4 — Monthly Check-in | pages/4_WF4_Monthly_Checkin.py | ✅ Complete. | |
| WF4 — Quarterly Review | pages/5_WF4_Quarterly_Review.py | ✅ Complete. | |
| WF2 — Merit Cycle | pages/6_WF2_Merit_Cycle.py | ⬜ Not started | |
| WF2 — Eligibility Engine | pages/7_WF2_Eligibility.py | ⬜ Not started | |
| WF3 — Risk Dashboard | pages/8_WF3_Risk_Dashboard.py | ⬜ Not started | |
| WF3 — Config | pages/9_WF3_Config.py | ⬜ Not started | |
| app.py | app.py | ⬜ Not started | |
| utils/db.py | utils/db.py | ⬜ Not started | |
| utils/scoring.py | utils/scoring.py | ⬜ Not started | |

---

## 10. USAGE MANAGEMENT

### Claude Code plan limits
- You are on the Max plan (Claude Sonnet 4.6)
- Usage resets on a rolling basis — not daily
- MCP tools consume tokens on every session startup (~17k tokens with current setup)
- Cache hits are cheap — cache misses are expensive

### How to optimise usage per session

**High-token tasks (use sparingly, batch them):**
- Full page builds from scratch
- Multi-agent parallel runs
- Any task requiring reading many files

**Low-token tasks (safe to run freely):**
- Targeted str_replace edits to existing files
- Single function additions
- Bug fixes with a specific error message

### Session discipline rules
1. **Always start with a clear scope** — "build X, nothing else" prevents runaway token use
2. **One workflow per session** — never mix WF1 and WF3 work in the same session
3. **Read before writing** — always tell Claude to read relevant files first
4. **Use Plan mode for complex tasks** — `/plan` before execution on anything >3 files
5. **Commit after every completed page** — small commits, easy rollback

### Monitor usage inside Claude Code
```
/cost        # shows token cost of the current session
/status      # shows current session context usage
```

### MCP token footprint (current setup)
| Server | Tokens | When to disable |
|---|---|---|
| claude.ai Supabase | ~9,280 | Never — always needed |
| github | ~8,320 | Never — needed for commits |
| **Total** | ~17,600 | Well within limits |

---

## 11. DEPLOYMENT CHECKLIST

Run through this before every Streamlit Cloud push:

- [ ] `requirements.txt` is up to date
- [ ] `.env` is in `.gitignore` and NOT committed
- [ ] `CLAUDE.md` is in `.gitignore` and NOT committed
- [ ] `.streamlit/config.toml` IS committed
- [ ] All secrets added to Streamlit Cloud secrets manager (double-quoted values)
- [ ] Supabase pooler URL used (port 6543, not 5432)
- [ ] Tested locally with `python -m streamlit run app.py`
- [ ] `git pull origin main --rebase` before push

### Streamlit Cloud secrets format
```toml
DB_HOST = "your-pooler-host.supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"
DB_USER = "postgres.your-project-ref"
DB_PASSWORD = "your-password"
```

---

## 12. KNOWN MISTAKES — NEVER REPEAT

| Mistake | What Happened | Fix |
|---|---|---|
| White chart background | `plot_bgcolor="#FAFAFA"` | Always `"rgba(0,0,0,0)"` |
| Stale data after write | Forgot `run_query.clear()` | Always clear cache after mutations |
| UUID IN clause 0 rows | Type mismatch in ANY(%s) | Cast to text + dynamic placeholders (Section 6) |
| Sidebar abstracted to helper | Rerun issues in multi-page apps | Duplicate sidebar in every page |
| Pastel table colours | Unreadable on dark theme | Saturated fills + white text only |
| DB connection on Cloud | Used port 5432 | Always port 6543 (pooler) |
| Secrets not working | Missing double quotes | All values must be `"quoted"` in Streamlit secrets |
| `.applymap()` deprecation | Old pandas method | Use `.map()` instead |
| CLAUDE_CODE_MAX_OUTPUT_TOKENS not set → 32k ceiling hit on large pages | set $env:CLAUDE_CODE_MAX_OUTPUT_TOKENS = "64000" before every session |
| Multi-tab pages >400 lines: | build in two passes (Tabs 1–2 first, Tabs 3–4 second) as fallback if token limit still triggers |

---

## 13. COMMIT CONVENTION

```
feat: add WF1 data upload page
feat: add WF3 scoring engine
fix: correct compa-ratio calculation in WF2 eligibility
fix: resolve cache staleness after merit recommendation submit
docs: update CLAUDE.md build status
refactor: extract DB connection to utils/db.py
chore: update requirements.txt
```

---

## 14. PROMPT TEMPLATES FOR CLAUDE CODE

Use these as starting points. Fill in the bracketed sections.

### Single page build
```
Use the [skill] skill.
Read CLAUDE.md Sections 4, 5, 6, and 9 before writing any code.
Build [page filename] for [workflow].
Requirements:
- [list key requirements from FRD]
- Use utils/db.py for all database access
- Follow the colour palette in Section 5
- Do not build anything not listed here
Confirm you have read CLAUDE.md before starting.
```

### Multi-agent workflow build
```
Use the [skill] skill.
Read CLAUDE.md Sections 4, 5, 6, 7, and 9 before writing any code.
Build [workflow name] using subagents in parallel:
- Agent A: [page A filename] — [brief description]
- Agent B: [page B filename] — [brief description]
All agents must:
- Use utils/db.py for database access
- Follow Section 5 colour palette
- Check Section 9 build status before starting
- Not duplicate anything already built
Confirm agents have read CLAUDE.md before any agent starts coding.
```

### Bug fix
```
Read [filename] carefully.
The bug is: [exact error message or description]
Fix only this issue. Do not refactor anything else.
Show me what you're changing before making the change.
```

### Code review pass
```
Use the code-reviewer skill.
Review [filename or all pages].
Check for:
1. DB connection anti-patterns (hardcoded credentials, wrong port)
2. Missing cache clears after mutations
3. Colour palette violations (any non-dark-theme colours)
4. Any deviation from the DB pattern in CLAUDE.md Section 6
Report issues only — do not fix anything yet.
```

---

## 15. .gitignore (always include these)

```
.env
CLAUDE.md
__pycache__/
*.pyc
.DS_Store
*.egg-info/
.streamlit/secrets.toml
```
