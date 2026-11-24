# Momentum

Momentum is a personal planner that brings tasks, calendar entries, shopping, and goals into one workspace. The React app runs locally with a Python FastAPI backend and SQLite. The original Streamlit app is available in the same repository.

## Run the portfolio demo

Use Python 3.14 and Node 24. These commands are for PowerShell at the project root. If `.venv` already exists, use it in place of creating a new one.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
npm.cmd --prefix frontend ci
.\.venv\Scripts\python.exe -m demo
```

The seed command creates `momentum-demo.db` with fictional data dated relative to the day you run it. It refuses to overwrite an existing file. Use `--path another-demo.db` to make a fresh copy with a different name.

In one terminal, start the backend with the sample database.

```powershell
$env:MOMENTUM_DB_PATH = (Resolve-Path .\momentum-demo.db).Path
.\.venv\Scripts\python.exe -m uvicorn api:app --reload
```

In a second terminal, start React and open `http://localhost:5173`.

```powershell
npm.cmd --prefix frontend run dev
```

### Demo walkthrough

1. On **Today**, show the sample appointment, completed task, and Reading goal. Open **Planner** to see the same appointment in the calendar.
2. From any screen, enter `I need bananas; Remind me to shop tomorrow`. Run the command and cancel the preview. Shopping still contains only the seeded item. Run it again and confirm. Bananas appears once in Shopping, and the reminder appears in Planner tomorrow.
3. Enter `Log 5 toward Reading` and confirm. **Today** and **Goals** should both show 15 of 100 pages and the first milestone reached.

## Optional AI mode

Local commands are the default and work without an API key. To enable **AI** in the command mode selector, set `OPENAI_API_KEY` in the backend terminal before starting or restarting FastAPI. The command below prompts for the key without putting it in your command history.

```powershell
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'OpenAI API key' -AsSecureString)).Password
```

Refresh the app, switch to **AI**, and try `Add bananas and remind me to shop tomorrow`. You should see a shopping item and a dated reminder in the preview. The app sends the command text and the current date to the Responses API. The model proposes structured actions. FastAPI validates the fields and resolves existing tasks and goals locally. Schedule answers are read from SQLite, and confirmation applies the stored batch in one transaction.

Live AI requests use your OpenAI API account. Momentum defaults to `gpt-5.4-mini`, with `MOMENTUM_OPENAI_MODEL` available as a backend override for a compatible function-calling model. Each preview makes one bounded Responses request. The backend logs input and output token counts so you can compare them with your account’s usage and the model’s published rates. [OpenAI setup](https://developers.openai.com/api/docs/quickstart) · [Function calling](https://developers.openai.com/api/docs/guides/function-calling) · [Model and pricing](https://developers.openai.com/api/docs/models/gpt-5.4-mini)

## Verify the project

The full Python suite includes compatibility tests for the original Streamlit app. Install Streamlit once if it is missing from the virtual environment. AI tests mock the Responses API and use temporary databases.

```powershell
.\.venv\Scripts\python.exe -m pip install streamlit==1.67.0
.\.venv\Scripts\python.exe -m unittest -v
npm.cmd --prefix frontend run build
```
