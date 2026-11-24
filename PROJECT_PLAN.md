# Momentum project plan

## Vision

Momentum is an AI-powered personal planner and accountability application. Keep everyday actions easy to find and use automation to reduce the work of organizing tasks, schedules, and goals. The interface should be clean, intuitive, and responsive.

## Technology choices

- **Python** for application logic and database access.
- **Streamlit** for building the interface directly in Python.
- **SQLite** for durable local storage using Python's built-in `sqlite3` module and a single database file.
- **`unittest`** for automated tests. Database tests use temporary files.
- **Git and GitHub** for version history and hosting the source repository.

## Run Momentum locally

From the project folder in PowerShell, use the existing workspace environment.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

For a fresh checkout, create `.venv` with `python -m venv .venv` and install the tested Streamlit version with `.\.venv\Scripts\python.exe -m pip install streamlit==1.67.0`. To run the automated tests, use `.\.venv\Scripts\python.exe -m unittest -v`.

## Completed work and current status

Verified locally on November 23, 2026. VS Code and Git are available. The workspace virtual environment has Python 3.14.4 and Streamlit 1.67.0.

- The initial Streamlit prototype added and displayed tasks in session memory. Its commit `426c52b` is on `main` and matches the local `origin/main` tracking reference.
- **SQLite foundation.** Tasks persist in `momentum.db`, which Git ignores. On November 24, 2026, the project owner confirmed that a saved task stayed checked after restarting Streamlit. Later migrations add optional due dates, priorities, recurrence, and lists while preserving existing tasks.
- **Home and planner.** Home shows today's agenda, the next seven days of scheduled events and reminders, and goal progress. Planner provides day, week, and month views and supports appointments, events, birthdays, deadlines, and reminders with optional recurrence.
- **Tasks and shopping.** Add, edit, complete, reopen, and delete items. Tasks support due dates, priorities, and daily or weekly recurrence. Completing a recurring task adds its next occurrence once. Shopping has its own checklist.
- **Goals.** Set measurable targets, log check-ins, track milestones, schedule recurring check-in reminders, and see weekly and monthly progress totals.
- **Local command bar.** Recognizes supported phrases for shopping, tasks, schedule questions, reminders, and goal progress. It asks for a date or goal when needed and previews writes for confirmation. It uses built-in parsing rules. Reminders appear in the app.
- **Verification.** Thirteen automated tests pass, including a Streamlit workflow using a temporary database. The full build is pending browser review and commit.

## Future expansion

Potential follow-up work includes browser notifications, calendar integrations, mobile-specific refinements, hosted deployment, user accounts, and broader language understanding.
