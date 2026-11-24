import sqlite3
from contextlib import closing, contextmanager
from datetime import date, timedelta
from pathlib import Path

from planner import period_bounds


DATABASE_PATH = Path(__file__).with_name("momentum.db")
_KEEP_DUE_DATE = object()
PRIORITIES = ("Normal", "High", "Low")
TASK_REPEAT = ("None", "Daily", "Weekly")


@contextmanager
def _connect(db_path):
    with closing(sqlite3.connect(db_path, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        # Commit writes on success or roll them back if an error occurs.
        with connection:
            yield connection


def initialize_database(db_path=DATABASE_PATH):
    with _connect(db_path) as connection:
        # Keep the column check and migration together if two sessions start at once.
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                due_date TEXT
            )
            """
        )
        columns = {column["name"] for column in connection.execute("PRAGMA table_info(tasks)")}
        for name, definition in (
            ("due_date", "TEXT"),
            ("list_name", "TEXT NOT NULL DEFAULT 'Tasks'"),
            ("priority", "TEXT NOT NULL DEFAULT 'Normal'"),
            ("repeat", "TEXT NOT NULL DEFAULT 'None'"),
            ("repeat_created", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if name not in columns:
                connection.execute(f"ALTER TABLE tasks ADD COLUMN {name} {definition}")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, kind TEXT NOT NULL, day TEXT NOT NULL,
                time TEXT, repeat TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, target REAL NOT NULL CHECK (target > 0),
                unit TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS goal_checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
                day TEXT NOT NULL, amount REAL NOT NULL CHECK (amount >= 0), note TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS goal_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
                title TEXT NOT NULL, threshold REAL NOT NULL CHECK (threshold > 0)
            )
        """)


def create_task(title, db_path=DATABASE_PATH, *, due_date=None, list_name="Tasks",
                priority="Normal", repeat="None"):
    if repeat != "None" and due_date is None:
        raise ValueError("Choose a due date for a repeating task.")
    with _connect(db_path) as connection:
        return insert_task(connection, title, due_date, list_name, priority, repeat)


def insert_task(connection, title, due_date=None, list_name="Tasks", priority="Normal", repeat="None"):
    return connection.execute(
        "INSERT INTO tasks (title, due_date, list_name, priority, repeat) VALUES (?, ?, ?, ?, ?)",
        (title, due_date.isoformat() if due_date else None, list_name, priority, repeat),
    ).lastrowid


def get_tasks(db_path=DATABASE_PATH, *, list_name=None):
    query = "SELECT id, title, completed, created_at, due_date, list_name, priority, repeat FROM tasks"
    params = ()
    if list_name is not None:
        query += " WHERE list_name = ?"
        params = (list_name,)
    with _connect(db_path) as connection:
        return connection.execute(query + " ORDER BY id", params).fetchall()


def update_task_title(task_id, title, db_path=DATABASE_PATH, *, due_date=_KEEP_DUE_DATE,
                      priority=None, repeat=None):
    title = title.strip()
    if not title:
        raise ValueError("Enter a task title.")

    with _connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        task = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if task is None:
            return False
        saved_date = task["due_date"]
        if due_date is not _KEEP_DUE_DATE:
            saved_date = due_date.isoformat() if due_date else None
        repeat = task["repeat"] if repeat is None else repeat
        if repeat != "None" and saved_date is None:
            raise ValueError("Choose a due date for a repeating task.")
        connection.execute(
            "UPDATE tasks SET title = ?, due_date = ?, priority = ?, repeat = ? WHERE id = ?",
            (title, saved_date, priority or task["priority"], repeat, task_id),
        )
        return True


def update_task_completion(task_id, completed, db_path=DATABASE_PATH):
    with _connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        task = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if task is None:
            return False
        connection.execute(
            "UPDATE tasks SET completed = ? WHERE id = ?",
            (int(completed), task_id),
        )
        if completed and not task["completed"] and not task["repeat_created"] and task["repeat"] != "None":
            interval = 7 if task["repeat"] == "Weekly" else 1
            next_date = date.fromisoformat(task["due_date"]) + timedelta(days=interval)
            connection.execute(
                "INSERT INTO tasks (title, due_date, list_name, priority, repeat) VALUES (?, ?, ?, ?, ?)",
                (task["title"], next_date.isoformat(), task["list_name"], task["priority"], task["repeat"]),
            )
            connection.execute("UPDATE tasks SET repeat_created = 1 WHERE id = ?", (task_id,))
        return True


def delete_task(task_id, db_path=DATABASE_PATH):
    with _connect(db_path) as connection:
        return connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,)).rowcount == 1


def save_schedule(title, kind, day, event_time, repeat, db_path=DATABASE_PATH, *, entry_id=None):
    with _connect(db_path) as connection:
        if entry_id is None:
            return insert_schedule(connection, title, kind, day, event_time, repeat)
        event_clock = event_time.isoformat(timespec="minutes") if event_time else None
        return connection.execute(
            "UPDATE schedule SET title = ?, kind = ?, day = ?, time = ?, repeat = ? WHERE id = ?",
            (title, kind, day.isoformat(), event_clock, repeat, entry_id),
        ).rowcount == 1


def insert_schedule(connection, title, kind, day, event_time, repeat):
    return connection.execute(
        "INSERT INTO schedule (title, kind, day, time, repeat) VALUES (?, ?, ?, ?, ?)",
        (title, kind, day.isoformat(), event_time.isoformat(timespec="minutes") if event_time else None, repeat),
    ).lastrowid


def get_schedule(db_path=DATABASE_PATH):
    with _connect(db_path) as connection:
        return connection.execute("SELECT * FROM schedule ORDER BY day, time, id").fetchall()


def delete_schedule(entry_id, db_path=DATABASE_PATH):
    with _connect(db_path) as connection:
        return connection.execute("DELETE FROM schedule WHERE id = ?", (entry_id,)).rowcount == 1


def create_goal(title, target, unit, db_path=DATABASE_PATH):
    with _connect(db_path) as connection:
        return insert_goal(connection, title, target, unit)


def insert_goal(connection, title, target, unit):
    return connection.execute(
        "INSERT INTO goals (title, target, unit) VALUES (?, ?, ?)", (title, target, unit)
    ).lastrowid


def get_goals(db_path=DATABASE_PATH):
    with _connect(db_path) as connection:
        return connection.execute("""
            SELECT goals.*, COALESCE(SUM(goal_checkins.amount), 0) AS progress
            FROM goals LEFT JOIN goal_checkins ON goals.id = goal_checkins.goal_id
            GROUP BY goals.id ORDER BY goals.id
        """).fetchall()


def get_goal_summaries(day, db_path=DATABASE_PATH, *, goal_id=None):
    week_start, _ = period_bounds(day, "Week")
    month_start, _ = period_bounds(day, "Month")
    with _connect(db_path) as connection:
        return connection.execute("""
            WITH progress AS (
                SELECT goal_id, SUM(amount) AS total,
                       SUM(CASE WHEN day BETWEEN :week AND :today THEN amount ELSE 0 END) AS week,
                       SUM(CASE WHEN day BETWEEN :month AND :today THEN amount ELSE 0 END) AS month
                FROM goal_checkins GROUP BY goal_id
            )
            SELECT goals.*, COALESCE(progress.total, 0) AS progress,
                   COALESCE(progress.week, 0) AS week_progress,
                   COALESCE(progress.month, 0) AS month_progress,
                   (SELECT COUNT(*) FROM goal_milestones WHERE goal_id = goals.id) AS milestone_count,
                   (SELECT COUNT(*) FROM goal_milestones
                    WHERE goal_id = goals.id AND threshold <= COALESCE(progress.total, 0)) AS milestones_reached
            FROM goals LEFT JOIN progress ON progress.goal_id = goals.id
            WHERE :goal_id IS NULL OR goals.id = :goal_id
            ORDER BY goals.id
        """, {"week": week_start.isoformat(), "month": month_start.isoformat(),
              "today": day.isoformat(), "goal_id": goal_id}).fetchall()


def add_checkin(goal_id, day, amount, note, db_path=DATABASE_PATH):
    with _connect(db_path) as connection:
        return insert_checkin(connection, goal_id, day, amount, note)


def insert_checkin(connection, goal_id, day, amount, note):
    return connection.execute(
        "INSERT INTO goal_checkins (goal_id, day, amount, note) SELECT id, ?, ?, ? FROM goals WHERE id = ?",
        (day.isoformat(), amount, note, goal_id),
    ).rowcount == 1


def get_checkins(goal_id, db_path=DATABASE_PATH):
    with _connect(db_path) as connection:
        return connection.execute(
            "SELECT * FROM goal_checkins WHERE goal_id = ? ORDER BY day DESC, id DESC", (goal_id,)
        ).fetchall()


def add_milestone(goal_id, title, threshold, db_path=DATABASE_PATH):
    with _connect(db_path) as connection:
        return insert_milestone(connection, goal_id, title, threshold)


def insert_milestone(connection, goal_id, title, threshold):
    return connection.execute(
        "INSERT INTO goal_milestones (goal_id, title, threshold) SELECT id, ?, ? FROM goals WHERE id = ?",
        (title, threshold, goal_id),
    ).rowcount == 1


def get_milestones(goal_id, db_path=DATABASE_PATH):
    with _connect(db_path) as connection:
        return connection.execute(
            "SELECT * FROM goal_milestones WHERE goal_id = ? ORDER BY threshold, id", (goal_id,)
        ).fetchall()


def delete_goal(goal_id, db_path=DATABASE_PATH):
    with _connect(db_path) as connection:
        return connection.execute("DELETE FROM goals WHERE id = ?", (goal_id,)).rowcount == 1
