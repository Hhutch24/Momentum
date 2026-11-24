import json
import os
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

import database as db
from api import create_app
from demo import seed_demo


def tool_call(name, **arguments):
    return {"type": "function_call", "name": name, "arguments": json.dumps(arguments)}


class ModelCommandTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "test.db"
        db.initialize_database(self.path)
        self.client = TestClient(create_app(self.path))
        self.addCleanup(self.client.close)
        self.enterContext(patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-value", "MOMENTUM_OPENAI_MODEL": "test-model"}))
        self.post = self.enterContext(patch("model_commands.httpx.post"))

    def preview(self, text, *calls):
        self.post.return_value = httpx.Response(200, request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
                                                json={"status": "completed", "output": list(calls),
                                                      "usage": {"input_tokens": 100, "output_tokens": 25}})
        return self.client.post("/api/commands/preview", json={"mode": "ai", "today": "2024-09-09", "text": text})

    def test_ai_previews_batch_and_keeps_database_out_of_request(self):
        db.create_task("Private fixture title", self.path)
        text = "Add bananas and remind me to shop tomorrow at 9 AM"
        with self.assertLogs("uvicorn.error", level="INFO") as logs:
            response = self.preview(text, tool_call("add_shopping_item", title="bananas"),
                                    tool_call("add_event", title="Shop", day="2024-09-10", event_time="09:00", kind="Reminder", repeat="None"))
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["state"], "preview")
        self.assertEqual(len(result["actions"]), 2)
        self.assertEqual(db.get_schedule(self.path), [])
        self.assertEqual(db.get_tasks(self.path, list_name="Shopping"), [])
        request = self.post.call_args.kwargs["json"]
        self.assertEqual(request["model"], "test-model")
        self.assertEqual(request["input"], text)
        self.assertFalse(request["store"])
        self.assertNotIn("Private fixture title", json.dumps(request))
        self.assertIn("input_tokens=100 output_tokens=25", logs.output[0])
        self.assertNotIn(text, logs.output[0])

        confirm = f"/api/commands/{result['proposal_id']}/confirm"
        for _ in range(2):
            self.assertEqual(self.client.post(confirm).json(), {"state": "applied"})
        self.assertEqual([item["title"] for item in db.get_tasks(self.path, list_name="Shopping")], ["bananas"])
        self.assertEqual([(row["title"], row["time"]) for row in db.get_schedule(self.path)], [("Shop", "09:00")])
        scripted = self.client.post("/api/commands/preview", json={"today": "2024-09-09", "text": "I need bananas"}).json()
        self.assertEqual(scripted["actions"], result["actions"][:1])
        self.post.assert_called_once()

    def test_ai_read_results_come_from_sqlite_and_rename_resolves_task(self):
        day = date(2024, 9, 9)
        task_id = db.create_task("Study", self.path, due_date=day)
        result = self.preview("What is scheduled?", tool_call("show_schedule", first=str(day), last=str(day))).json()
        self.assertEqual(result["items"][0]["title"], "Study")
        db.create_task("Study", self.path)
        ambiguous = self.preview("Rename Study", tool_call("rename_task", task="Study", title="Study Python")).json()
        self.assertEqual(ambiguous["state"], "clarification")
        self.assertIn(f"Task #{task_id}", ambiguous["message"])
        proposal = self.preview("Rename the first task", tool_call("rename_task", task=f"Task #{task_id}", title="Study Python")).json()
        path = f"/api/commands/{proposal['proposal_id']}/confirm"
        self.assertEqual(self.client.post(path).status_code, 200)
        self.assertEqual([row["title"] for row in db.get_tasks(self.path)], ["Study Python", "Study"])

    def test_ai_rejects_unknown_tools_and_uses_local_mode_without_key(self):
        result = self.preview("Delete all tasks", tool_call("delete_everything")).json()
        self.assertEqual(result["state"], "clarification")
        question = self.preview("Remind me to shop", tool_call("ask_clarification", message="Which day should I remind you?")).json()
        self.assertEqual(question["message"], "Which day should I remind you?")
        invalid = self.preview("Add a task", tool_call("add_task", title="Study", due_date=123)).json()
        self.assertEqual(invalid["state"], "clarification")
        self.assertEqual(db.get_tasks(self.path), [])

        self.post.reset_mock()
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assertEqual(self.client.get("/api/commands/config").json(), {"ai_enabled": False})
            request = {"today": "2024-09-09", "text": "I need apples"}
            self.assertEqual(self.client.post("/api/commands/preview", json={**request, "mode": "ai"}).status_code, 503)
            self.assertEqual(self.client.post("/api/commands/preview", json=request).json()["state"], "preview")
        self.post.assert_not_called()

    def test_demo_seed_uses_a_separate_file_and_rejects_overwrite(self):
        demo_path = self.path.with_name("demo.db")
        seed_demo(demo_path, date(2024, 9, 9))
        self.assertEqual(len(db.get_tasks(demo_path)), 3)
        self.assertEqual(db.get_goals(demo_path)[0]["progress"], 10)
        self.assertEqual(db.get_tasks(self.path), [])
        with self.assertRaises(FileExistsError):
            seed_demo(demo_path, date(2024, 9, 9))
        self.assertEqual(len(db.get_tasks(demo_path)), 3)
