import sqlite3
import unittest
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from database import (
    create_task,
    delete_task,
    get_tasks,
    initialize_database,
    update_task_completion,
    update_task_title,
)


class TaskDatabaseTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db_path = Path(directory.name) / "test.db"
        initialize_database(self.db_path)

    def test_new_database_has_no_tasks(self):
        self.assertEqual(get_tasks(self.db_path), [])

    def test_create_and_retrieve_tasks(self):
        first_id = create_task("Read today's notes", self.db_path)
        second_id = create_task("Write a summary", self.db_path)
        initialize_database(self.db_path)

        first, second = get_tasks(self.db_path)
        self.assertNotEqual(first_id, second_id)
        self.assertEqual((first["id"], second["id"]), (first_id, second_id))
        self.assertEqual(first["title"], "Read today's notes")
        self.assertEqual(first["completed"], 0)
        self.assertIsInstance(datetime.fromisoformat(first["created_at"]), datetime)

    def test_mark_task_complete_and_incomplete(self):
        task_id = create_task("Review SQLite", self.db_path)

        update_task_completion(task_id, True, self.db_path)
        self.assertEqual(get_tasks(self.db_path)[0]["completed"], 1)

        update_task_completion(task_id, False, self.db_path)
        self.assertEqual(get_tasks(self.db_path)[0]["completed"], 0)

    def test_delete_one_task(self):
        first_id = create_task("Delete this task", self.db_path)
        second_id = create_task("Keep this task", self.db_path)

        delete_task(first_id, self.db_path)

        self.assertEqual([task["id"] for task in get_tasks(self.db_path)], [second_id])

    def test_update_title_changes_only_the_selected_title(self):
        first_id = create_task("Read notes", self.db_path)
        create_task("Read notes", self.db_path)
        update_task_completion(first_id, True, self.db_path)
        original_tasks = [dict(task) for task in get_tasks(self.db_path)]

        update_task_title(first_id, "  Read today's notes  ", self.db_path)

        original_tasks[0]["title"] = "Read today's notes"
        self.assertEqual([dict(task) for task in get_tasks(self.db_path)], original_tasks)

    def test_update_title_rejects_whitespace(self):
        task_id = create_task("Keep this title", self.db_path)

        with self.assertRaises(ValueError):
            update_task_title(task_id, "  ", self.db_path)

        self.assertEqual(get_tasks(self.db_path)[0]["title"], "Keep this title")

    def test_due_date_can_be_saved_changed_and_cleared(self):
        task_id = create_task("Submit assignment", self.db_path, due_date=date(2027, 1, 15))
        initialize_database(self.db_path)
        self.assertEqual(get_tasks(self.db_path)[0]["due_date"], "2027-01-15")

        update_task_title(task_id, "Submit revised assignment", self.db_path)
        self.assertEqual(get_tasks(self.db_path)[0]["due_date"], "2027-01-15")

        update_task_title(task_id, "Submit assignment", self.db_path, due_date=date(2027, 2, 1))
        self.assertEqual(get_tasks(self.db_path)[0]["due_date"], "2027-02-01")

        update_task_title(task_id, "Submit assignment", self.db_path, due_date=None)
        self.assertIsNone(get_tasks(self.db_path)[0]["due_date"])

    def test_migration_preserves_existing_tasks(self):
        legacy_path = self.db_path.with_name("legacy.db")
        with closing(sqlite3.connect(legacy_path)) as connection, connection:
            connection.execute("""
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """)
            connection.execute("""
                INSERT INTO tasks (id, title, completed, created_at)
                VALUES (7, 'Existing task', 1, '2026-11-23 12:00:00')
                """)

        initialize_database(legacy_path)
        initialize_database(legacy_path)

        self.assertEqual(dict(get_tasks(legacy_path)[0]), {
            "id": 7,
            "title": "Existing task",
            "completed": 1,
            "created_at": "2026-11-23 12:00:00",
            "due_date": None,
            "list_name": "Tasks",
            "priority": "Normal",
            "repeat": "None",
        })
        create_task("Undated task", legacy_path)
        self.assertIsNone(get_tasks(legacy_path)[1]["due_date"])
