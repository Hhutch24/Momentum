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

For a fresh checkout, create `.venv` with `python -m venv .venv` and install the tested Streamlit version with `.\.venv\Scripts\python.exe -m pip install streamlit==1.67.0`.

### React app

From the project root, install the API and frontend dependencies. Node 24 was used for this milestone.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
npm.cmd --prefix frontend ci
```

Start FastAPI in one terminal and React in a second terminal.

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --reload
```

```powershell
npm.cmd --prefix frontend run dev
```

Open `http://localhost:5173` or the local URL Vite prints. The React and Streamlit apps use the root `momentum.db` by default. Today reads it, while Tasks and Shopping can save changes. On a fresh checkout, start Streamlit once to create the database. To use a separate SQLite fixture, set `MOMENTUM_DB_PATH` to its path in the FastAPI terminal before starting the server.

If port 8000 is in use, start Uvicorn with `--port 8001` and set `$env:MOMENTUM_API_URL = 'http://127.0.0.1:8001'` in the React terminal before starting Vite.

For a manual check, add a due-today task and a timed appointment in Streamlit, then compare the two Today screens. Use the previous and next day controls, switch themes, and narrow the browser window. Stop FastAPI to check the error state, restart it, and use **Try again** to reload the agenda.

To check Tasks, create a weekly task due today and mark it High priority. Use the priority and date filters, rename it, then complete, reopen, and complete it again. Clear the filters and check that exactly one task was added for next week. In Shopping, add and check off an item, then reload the page and reopen Shopping to check that the state persisted.

To check Planner, create a monthly reminder dated January 31, 2027. Open February in Month view and select its February 28 occurrence. The editor should show January 31 as the series start. Change that start to January 30, save, and navigate to March. The reminder should appear on March 30. Narrow the browser to see the month agenda, then try opening and closing the editor with Enter and Escape.

With both sets of Python dependencies installed, run `.\.venv\Scripts\python.exe -m unittest -v` for the full suite. Run `npm.cmd --prefix frontend run build` to type-check and build the frontend.

## Completed work and current status

Verified locally on November 23, 2026. VS Code and Git are available. The workspace virtual environment has Python 3.14.4 and Streamlit 1.67.0.

- The initial Streamlit prototype added and displayed tasks in session memory. Its commit `426c52b` is on `main` and matches the local `origin/main` tracking reference.
- **SQLite foundation.** Tasks persist in `momentum.db`, which Git ignores. On November 24, 2026, the project owner confirmed that a saved task stayed checked after restarting Streamlit. Later migrations add optional due dates, priorities, recurrence, and lists while preserving existing tasks.
- **Home and planner.** Home shows today's agenda, the next seven days of scheduled events and reminders, and goal progress. Planner provides day, week, and month views and supports appointments, events, birthdays, deadlines, and reminders with optional recurrence.
- **Tasks and shopping.** Add, edit, complete, reopen, and delete items. Tasks support due dates, priorities, and daily or weekly recurrence. Completing a recurring task adds its next occurrence once. Shopping has its own checklist.
- **Goals.** Set measurable targets, log check-ins, track milestones, schedule recurring check-in reminders, and see weekly and monthly progress totals.
- **Local command bar.** Recognizes supported phrases for shopping, tasks, schedule questions, reminders, and goal progress. It asks for a date or goal when needed and previews writes for confirmation. It uses built-in parsing rules. Reminders appear in the app.
- **Today migration milestone.** The React, TypeScript, and Tailwind preview has a responsive agenda, date navigation, light and dark themes, summaries, and loading, empty, and retry states. FastAPI exposes a read-only `GET /api/agenda?date=YYYY-MM-DD` endpoint. Both interfaces use the shared Python agenda function. The endpoint reads the existing SQLite schema.
- **Tasks and Shopping migration milestone.** React adds inline editing, completion and reopening, confirmed deletion, and filters for status, priority, and due date. The dedicated Shopping checklist shares task storage. FastAPI validates task writes and reuses SQLite's recurring-task transaction.
- **Planner migration milestone.** React has day, week, and month views with date navigation, a monthly agenda on narrow screens, and a keyboard-accessible event dialog. The calendar combines dated tasks with appointments, events, deadlines, birthdays, and reminders. Opening a recurring entry edits the entire series using its original start date. FastAPI validates and stores entries in the existing SQLite tables.
- **Verification.** Nineteen automated Python tests pass, including the original Streamlit workflow and API tests for recurring series edits across months. The frontend type-check and production build pass. Headless Chrome checks used an isolated SQLite fixture to exercise Today, Tasks, Shopping, and the Planner, including keyboard focus, month navigation, series editing and deletion, and the mobile month agenda.

## Next migration milestone

Migrate Goals and check-ins. Share weekly and monthly progress calculations across the dashboard and goal detail, and verify that both agree after a check-in crosses a milestone.

## Future expansion

Potential follow-up work includes browser notifications, calendar integrations, mobile-specific refinements, hosted deployment, user accounts, and broader language understanding.
