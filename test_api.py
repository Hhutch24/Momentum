import unittest
from datetime import date, time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

import database as db
from api import create_app
from app import agenda as streamlit_agenda


class AgendaApiTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "agenda fixture.db"
        db.initialize_database(self.path)
        self.day = date(2026, 11, 24)
        self.client = TestClient(create_app(self.path))
        self.addCleanup(self.client.close)

    def test_agenda_preserves_dates_identity_and_completion(self):
        task = db.create_task("Study", self.path, due_date=self.day, priority="High")
        db.update_task_completion(task, True, self.path)
        db.create_task("Study", self.path, due_date=self.day)
        db.create_task("Bananas", self.path, due_date=self.day, list_name="Shopping")
        db.save_schedule("Study", "Appointment", self.day, time(9, 30), "None", self.path)
        db.save_schedule("Stretch", "Reminder", date(2026, 11, 17), None, "Weekly", self.path)

        before = self.path.read_bytes()
        response = self.client.get("/api/agenda", params={"date": self.day.isoformat()})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["date"], self.day.isoformat())
        self.assertTrue(all(item["date"] == data["date"] for item in data["items"]))
        self.assertEqual([(item["source"], item["id"]) for item in data["items"]],
                         [("schedule", 2), ("schedule", 1), ("task", 1), ("task", 2)])
        self.assertEqual([item["completed"] for item in data["items"]], [None, None, True, False])
        self.assertEqual(data["items"][1]["time"], "09:30")
        self.assertEqual(data["items"][2]["priority"], "High")
        self.assertEqual(self.path.read_bytes(), before)

        tasks = db.get_tasks(self.path)
        schedule = db.get_schedule(self.path)
        with (patch.object(db, "get_tasks", return_value=tasks),
              patch.object(db, "get_schedule", return_value=schedule)):
            self.assertEqual(streamlit_agenda(self.day, self.day), [
                (self.day, "Reminder · Stretch"), (self.day, "09:30 · Appointment · Study"),
                (self.day, "Completed task · Study"), (self.day, "Task due · Study"),
            ])

    def test_empty_day_invalid_date_and_missing_database(self):
        response = self.client.get("/api/agenda", params={"date": self.day.isoformat()})
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(self.client.get("/api/agenda?date=not-a-date").status_code, 422)
        missing = self.path.with_name("missing.db")
        with TestClient(create_app(missing)) as client:
            self.assertEqual(client.get("/api/agenda?date=2026-11-24").status_code, 503)
        self.assertFalse(missing.exists())

    def test_task_edit_and_recurring_completion(self):
        first = self.client.post("/api/tasks", json={
            "title": "Study", "due_date": str(self.day), "priority": "High", "repeat": "Weekly",
        })
        second = self.client.post("/api/tasks", json={"title": "Study"})
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        first_id = first.json()["id"]
        self.assertEqual(self.client.patch(f"/api/tasks/{first_id}", json={"title": " Study Python "}).status_code, 204)
        for completed in (True, False, True):
            result = self.client.patch(f"/api/tasks/{first_id}/completion", json={"completed": completed})
            self.assertEqual(result.status_code, 204)
        tasks = self.client.get("/api/tasks").json()
        self.assertEqual([task["title"] for task in tasks], ["Study Python", "Study", "Study Python"])
        self.assertEqual([task["completed"] for task in tasks], [True, False, False])
        self.assertEqual(tasks[2]["due_date"], "2026-12-01")
        self.assertEqual(tasks[2]["priority"], "High")

    def test_shopping_crud_and_validation(self):
        created = self.client.post("/api/tasks", json={"title": "Bananas", "list_name": "Shopping"})
        self.assertEqual(created.status_code, 201)
        path = f"/api/tasks/{created.json()['id']}"
        self.assertEqual(self.client.get("/api/tasks").json(), [])
        self.assertEqual(self.client.patch(path, json={"title": "Apples"}).status_code, 204)
        self.assertEqual(self.client.patch(path + "/completion", json={"completed": True}).status_code, 204)
        items = self.client.get("/api/tasks?list_name=Shopping").json()
        self.assertEqual([(item["title"], item["completed"]) for item in items], [("Apples", True)])
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.get("/api/tasks?list_name=Shopping").json(), [])
        self.assertEqual(self.client.delete(path).status_code, 404)
        for invalid in ({"title": "  "}, {"title": "Repeat", "repeat": "Daily"}, {"title": "Invalid", "priority": "Urgent"}):
            self.assertEqual(self.client.post("/api/tasks", json=invalid).status_code, 422)

    def test_planner_edits_the_series_anchor_across_months(self):
        entry = {"title": "Pay rent", "kind": "Reminder", "day": "2027-01-31",
                 "event_time": "09:30", "repeat": "Monthly"}
        created = self.client.post("/api/schedule", json=entry)
        self.assertEqual(created.status_code, 201)
        entry_id = created.json()["id"]
        path = f"/api/schedule/{entry_id}"

        february = self.client.get("/api/planner?date=2027-02-01&view=Month").json()
        self.assertEqual((february["first"], february["last"]), ("2027-02-01", "2027-02-28"))
        occurrence = february["items"][0]
        self.assertEqual((occurrence["id"], occurrence["series_start"], occurrence["date"], occurrence["time"]),
                         (entry_id, "2027-01-31", "2027-02-28", "09:30"))

        entry.update(day="2027-01-30", title="Rent reminder")
        self.assertEqual(self.client.put(path, json=entry).status_code, 204)
        week = self.client.get("/api/planner?date=2027-03-31&view=Week").json()
        self.assertEqual((week["first"], week["last"]), ("2027-03-29", "2027-04-04"))
        self.assertEqual([(item["id"], item["date"], item["title"]) for item in week["items"]],
                         [(entry_id, "2027-03-30", "Rent reminder")])
        self.assertEqual(self.client.get("/api/planner?date=2027-03-31&view=Day").json()["items"], [])
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.get("/api/planner?date=2027-03-30&view=Day").json()["items"], [])
        self.assertEqual(self.client.put(path, json=entry).status_code, 404)

    def test_planner_keeps_tasks_distinct_and_rejects_invalid_schedule(self):
        db.create_task("Study", self.path, due_date=self.day)
        db.save_schedule("Study", "Appointment", self.day, None, "None", self.path)
        response = self.client.get(f"/api/planner?date={self.day}&view=Day")
        self.assertEqual([(item["source"], item["id"]) for item in response.json()["items"]],
                         [("schedule", 1), ("task", 1)])
        self.assertEqual(self.client.get(f"/api/planner?date={self.day}&view=Year").status_code, 422)
        self.assertEqual(self.client.post("/api/schedule", json={
            "title": "Meeting", "kind": "Appointment", "day": str(self.day), "event_time": "09:00:00Z",
        }).status_code, 422)

    def test_goal_summary_and_detail_agree_after_crossing_a_milestone(self):
        created = self.client.post("/api/goals", json={"title": "Read more", "target": 100, "unit": "pages"})
        self.assertEqual(created.status_code, 201)
        path = f"/api/goals/{created.json()['id']}"
        self.assertEqual(self.client.post(path + "/milestones", json={"title": "First chapter", "threshold": 15}).status_code, 204)

        for day, amount in (("2024-08-31", 5), ("2024-09-08", 6), ("2024-09-09", 4)):
            result = self.client.post(path + "/checkins", json={"day": day, "amount": amount, "note": "Read"})
            self.assertEqual(result.status_code, 204)

        query = "?day=2024-09-09"
        dashboard = self.client.get("/api/goals" + query).json()[0]
        detail = self.client.get(path + query).json()
        self.assertEqual((dashboard["progress"], dashboard["week_progress"], dashboard["month_progress"]), (15, 4, 10))
        self.assertEqual(dashboard["milestones_reached"], 1)
        self.assertEqual({field: detail[field] for field in dashboard}, dashboard)
        self.assertTrue(detail["milestones"][0]["reached"])
        self.assertEqual([row["amount"] for row in detail["checkins"]], [4, 6, 5])
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.get(path + query).status_code, 404)
        self.assertEqual(db.get_checkins(created.json()["id"], self.path), [])

    def test_goal_input_validation(self):
        self.assertEqual(self.client.post("/api/goals", json={"title": "   ", "target": 1}).status_code, 422)
        self.assertEqual(self.client.post("/api/goals", json={"title": "Read", "target": 0}).status_code, 422)
        path = "/api/goals/999/checkins"
        self.assertEqual(self.client.post(path, json={"day": "2024-09-09", "amount": -1}).status_code, 422)
        self.assertEqual(self.client.post(path, json={"day": "9999-12-31", "amount": 1}).status_code, 422)
        self.assertEqual(self.client.post(path, json={"day": "2024-09-09", "amount": 1}).status_code, 404)
