from datetime import date

import database as db
from planner import scheduled_occurrences


def get_agenda(first, last, **database_options):
    items = []
    for day, entry in scheduled_occurrences(db.get_schedule(**database_options), first, last):
        items.append({
            "id": entry["id"], "source": "schedule", "date": day,
            "title": entry["title"], "kind": entry["kind"], "time": entry["time"],
            "completed": None, "priority": None,
            "series_start": entry["day"], "repeat": entry["repeat"],
        })
    for task in db.get_tasks(**database_options):
        if task["list_name"] != "Tasks" or not task["due_date"]:
            continue
        day = date.fromisoformat(task["due_date"])
        if first <= day <= last:
            items.append({
                "id": task["id"], "source": "task", "date": day,
                "title": task["title"], "kind": "Task", "time": None,
                "completed": bool(task["completed"]), "priority": task["priority"],
            })
    return sorted(items, key=lambda item: item["date"])
