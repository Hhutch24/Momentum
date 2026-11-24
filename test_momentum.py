import unittest
from contextlib import ExitStack
from datetime import date, time, timedelta
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import database as db
from commands import parse_command
from planner import period_bounds, scheduled_occurrences


class LocalMomentumTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "momentum.db"
        db.initialize_database(self.path)

    def test_recurring_task_creates_only_one_successor(self):
        due = date(2026, 11, 24)
        task_id = db.create_task("Review notes", self.path, due_date=due, priority="High", repeat="Weekly")
        for completed in (True, False, True):
            db.update_task_completion(task_id, completed, self.path)
        first, second = db.get_tasks(self.path)
        self.assertTrue(first["completed"])
        self.assertFalse(second["completed"])
        self.assertEqual(second["due_date"], "2026-12-01")
        self.assertEqual(second["priority"], "High")

    def test_calendar_uses_original_day_for_monthly_recurrence(self):
        db.save_schedule("Rent", "Reminder", date(2026, 1, 31), time(9), "Monthly", self.path)
        entries = db.get_schedule(self.path)
        first, last = period_bounds(date(2026, 2, 7), "Week")
        self.assertEqual((first, last), (date(2026, 2, 2), date(2026, 2, 8)))
        occurrences = scheduled_occurrences(entries, date(2026, 2, 1), date(2026, 3, 31))
        self.assertEqual([day for day, _ in occurrences], [date(2026, 2, 28), date(2026, 3, 31)])

    def test_goal_progress_sums_checkins(self):
        goal = db.create_goal("Read", 100, "pages", self.path)
        day = date(2026, 11, 24)
        db.add_checkin(goal, day, 15, "Chapter one", self.path)
        db.add_checkin(goal, day, 10, "Chapter two", self.path)
        db.add_milestone(goal, "Quarter done", 25, self.path)
        self.assertEqual(db.get_goals(self.path)[0]["progress"], 25)
        self.assertEqual(db.get_milestones(goal, self.path)[0]["threshold"], 25)
        db.delete_goal(goal, self.path)
        self.assertEqual(db.get_checkins(goal, self.path), [])
        self.assertEqual(db.get_milestones(goal, self.path), [])

    def test_command_dates_and_clarification(self):
        today = date(2026, 11, 24)
        command = parse_command("Remind me to call Sam tomorrow", today)
        self.assertEqual(command["day"], today + timedelta(days=1))
        self.assertEqual(parse_command("What's coming up this week?", today)["period"], "this week")
        with self.assertRaisesRegex(ValueError, "Which date"):
            parse_command("Add task study due Friday", today)

    def test_streamlit_local_workflow(self):
        def click(label):
            next(button for button in app.button if button.label == label).click().run()
            self.assertFalse(app.exception)

        def navigate(page):
            app.sidebar.radio[0].set_value(page).run()
            self.assertFalse(app.exception)

        with ExitStack() as stack:
            data_functions = (
                "initialize_database", "create_task", "get_tasks", "update_task_title",
                "update_task_completion", "delete_task", "save_schedule", "get_schedule",
                "delete_schedule", "create_goal", "get_goals", "add_checkin", "get_checkins",
                "add_milestone", "get_milestones", "delete_goal",
            )
            for name in data_functions:
                stack.enter_context(patch.object(db, name, partial(getattr(db, name), db_path=self.path)))
            app = AppTest.from_file(str(Path(__file__).with_name("app.py"))).run()
            self.assertFalse(app.exception)
            app.text_input[0].set_value("I need bananas")
            click("Run command")
            self.assertEqual(db.get_tasks(), [])
            click("Confirm")
            navigate("Shopping")
            self.assertEqual(app.checkbox[0].label, "bananas")
            app.checkbox[0].check().run()
            self.assertTrue(db.get_tasks()[0]["completed"])

            navigate("Tasks")
            app.text_input[0].set_value("Study")
            app.date_input[0].set_value(date.today())
            click("Add task")
            app.radio(key="task_filter").set_value("Due today").run()
            self.assertEqual([checkbox.label for checkbox in app.checkbox], ["Study"])

            navigate("Planner")
            app.text_input[0].set_value("Call Sam")
            app.selectbox[0].set_value("Reminder")
            click("Add entry")
            app.radio(key="calendar_view").set_value("Month").run()
            self.assertFalse(app.exception)
            self.assertTrue(any("Call Sam" in element.value for element in app.text))

            navigate("Goals")
            app.text_input[0].set_value("Reading")
            app.number_input[0].set_value(100.0)
            click("Add goal")
            app.number_input[1].set_value(10.0)
            click("Log check-in")
            self.assertEqual(db.get_goals()[0]["progress"], 10)
            click("Schedule check-in reminder")
            self.assertTrue(any(entry["title"] == "Check in on Reading" for entry in db.get_schedule()))

            navigate("Home")
            app.text_input[0].set_value("Log 5 toward Reading")
            click("Run command")
            self.assertEqual(db.get_goals()[0]["progress"], 10)
            click("Confirm")
            self.assertEqual(db.get_goals()[0]["progress"], 15)

            app.text_input[0].set_value("Remind me to buy stamps tomorrow")
            click("Run command")
            click("Cancel command")
            self.assertFalse(any(entry["title"] == "buy stamps" for entry in db.get_schedule()))

            fresh = AppTest.from_file(str(Path(__file__).with_name("app.py"))).run()
            self.assertFalse(fresh.exception)
            self.assertTrue(any("Study" in element.value for element in fresh.text))
            self.assertTrue(any("15 / 100" in element.value for element in fresh.caption))
