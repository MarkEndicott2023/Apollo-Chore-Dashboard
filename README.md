# Apollo Chore Dashboard

A Streamlit dashboard visualizing chore tracking at Apollo Cooperative, a cooperative house. Data is consolidated from monthly tracking workbooks covering Aug 2025 onward.

**Live:** _deploy URL goes here_

## What's in it

- **Leaderboard** — completion percentage per resident (`done / (done + missed)`).
- **Status mix over time — by person** — weekly stacked-area of `done | missed | gone | na` shares for one resident (or all aggregated).
- **Status mix over time — by chore** — same view, sliced by chore instead of person.
- **Bounty escalation traces** — how a chore's point value grows when it goes uncompleted, per constitution §3.a.ii.1 (each missed week adds 5 points; claiming a bounty resets to 15 the following week).

## Data

`chores_centralized.xlsx` is a normalized star-schema workbook with seven sheets: `people`, `chores`, `assignments`, `completions`, `chore_values`, `discord_reports`, `monthly_summary`. Built from four monthly source workbooks (Oct 2025, Nov 2025, Feb 2026, Apr 2026).

Completion statuses:

- `done` — chore completed
- `missed` — chore not completed (incurs a fine)
- `gone` — resident away from the house that period
- `na` — chore not applicable that period

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Then open http://localhost:8501.
