import json
import re
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from pydantic import ValidationError

import database as db
from agenda import get_agenda
from commands import parse_command, parse_day
from goal_api import CheckinInput, GoalInput, MilestoneInput
from planner import period_bounds, repeat_date
from schedule_api import ScheduleEntry
from task_api import NewTask


def resolve_goal(name, db_path):
    goals = db.get_goals(db_path)
    identifier = re.fullmatch(r"goal #(\d+)", name.strip(), re.I)
    if identifier:
        matches = [goal for goal in goals if goal["id"] == int(identifier[1])]
    else:
        matches = [goal for goal in goals if goal["title"].casefold() == name.strip().casefold()]
    if len(matches) > 1:
        choices = ", ".join(f"Goal #{goal['id']}" for goal in matches)
        raise ValueError(f"Which goal did you mean? Replace the name with one of these IDs: {choices}.")
    if not matches:
        raise ValueError(f"Which goal did you mean? No goal matched “{name}”. Try its exact name or Goal #ID.")
    return matches[0]


def action(kind, values, summary, **extra):
    return {"kind": kind, "values": values.model_dump(mode="json"), "summary": summary, **extra}


def task_action(title, day=None, shopping=False):
    values = NewTask(title=title, due_date=day, list_name="Shopping" if shopping else "Tasks")
    label = "shopping item" if shopping else "task"
    return action("task", values, f"Add {label} “{values.title}”" + (f" due {day}" if day else ""))


def schedule_action(title, kind, day):
    values = ScheduleEntry(title=title, kind=kind, day=day)
    return action("schedule", values, f"Add {kind.lower()} “{values.title}” on {day}")


def parse_action(text, today, db_path):
    event = re.fullmatch(r"add event (.+) on (.+)", text, re.I)
    if event:
        return schedule_action(event[1], "Event", parse_day(event[2], today))
    if text.lower().startswith("add event "):
        raise ValueError("What date should the event be on? Try “Add event Book club on tomorrow”.")

    goal = re.fullmatch(r"add goal (.+?) target (\d+(?:\.\d+)?)(?: (.+))?", text, re.I)
    if goal:
        values = GoalInput(title=goal[1], target=float(goal[2]), unit=goal[3] or "")
        unit = f" {values.unit}" if values.unit else ""
        return action("goal", values, f"Add goal “{values.title}” with a target of {values.target:g}{unit}")
    if text.lower().startswith("add goal "):
        raise ValueError("What is the target for that goal? Try “Add goal Reading target 100 pages”.")

    milestone = re.fullmatch(r"add milestone (.+?) at (\d+(?:\.\d+)?) for (.+)", text, re.I)
    if milestone:
        goal = resolve_goal(milestone[3], db_path)
        values = MilestoneInput(title=milestone[1], threshold=float(milestone[2]))
        return action("milestone", values,
                      f"Add milestone “{values.title}” at {values.threshold:g} for “{goal['title']}” (Goal #{goal['id']})",
                      goal_id=goal["id"])
    if text.lower().startswith("add milestone "):
        raise ValueError("What milestone threshold and goal should I use? Try “Add milestone First chapter at 15 for Reading”.")

    command = parse_command(text, today)
    match command["action"]:
        case "task":
            return task_action(command["title"], command["day"])
        case "shopping":
            return task_action(command["title"], shopping=True)
        case "reminder":
            return schedule_action(command["title"], "Reminder", command["day"])
        case "goal":
            goal = resolve_goal(command["title"], db_path)
            if today > date.today():
                raise ValueError("Which day are you logging? Goal check-ins need today’s date or an earlier date.")
            values = CheckinInput(amount=command["amount"], day=today)
            return action("checkin", values,
                          f"Log {values.amount:g} toward “{goal['title']}” (Goal #{goal['id']}) on {today}",
                          goal_id=goal["id"])
        case "agenda":
            return command
    raise ValueError("This command is unavailable.")


def preview_command(text, today, db_path):
    parts = [part.strip() for part in re.split(r"[;\n]+", text) if part.strip()]
    if not 1 <= len(parts) <= 5:
        return {"state": "clarification", "message": "Enter one to five commands separated by semicolons."}
    try:
        actions = [parse_action(part, today, db_path) for part in parts]
    except ValidationError:
        return {"state": "clarification", "message": "Check the title, date, and numeric values in your command."}
    except (ValueError, OverflowError) as error:
        return {"state": "clarification", "message": str(error)}

    queries = [item for item in actions if item.get("action") == "agenda"]
    if queries:
        if len(actions) != 1:
            return {"state": "clarification", "message": "Could you ask the schedule question separately?"}
        first, last = today, today
        if queries[0]["period"] == "this week":
            _, last = period_bounds(today, "Week")
        elif queries[0]["period"] == "next month":
            if today.year == date.max.year and today.month == date.max.month:
                return {"state": "clarification", "message": "Which earlier month would you like to view?"}
            first, last = period_bounds(repeat_date(today.replace(day=1), "Monthly", 1), "Month")
        return {"state": "agenda", "first": first, "last": last, "items": get_agenda(first, last, db_path=db_path)}

    proposal_id = uuid4().hex
    expires = datetime.now(timezone.utc) + timedelta(minutes=30)
    with db._connect(db_path) as connection:
        ensure_proposals(connection)
        connection.execute(
            "INSERT INTO command_proposals (id, actions, expires_at) VALUES (?, ?, ?)",
            (proposal_id, json.dumps(actions), expires.isoformat()),
        )
    return {"state": "preview", "proposal_id": proposal_id, "actions": [item["summary"] for item in actions]}


def ensure_proposals(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS command_proposals (
            id TEXT PRIMARY KEY,
            actions TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'applied', 'cancelled'))
        )
    """)


class ProposalError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def apply_action(item, connection):
    values = item["values"]
    match item["kind"]:
        case "task":
            db.insert_task(connection, **NewTask.model_validate(values).model_dump())
        case "schedule":
            db.insert_schedule(connection, **ScheduleEntry.model_validate(values).model_dump())
        case "goal":
            db.insert_goal(connection, **GoalInput.model_validate(values).model_dump())
        case "checkin" | "milestone":
            if item["kind"] == "checkin":
                saved = db.insert_checkin(connection, item["goal_id"], **CheckinInput.model_validate(values).model_dump())
            else:
                saved = db.insert_milestone(connection, item["goal_id"], **MilestoneInput.model_validate(values).model_dump())
            if not saved:
                raise ProposalError("A goal in this proposal no longer exists. Run the command again.", 409)
        case _:
            raise ProposalError("This proposal contains an unsupported action.", 409)


def finish_proposal(proposal_id, confirm, db_path):
    with db._connect(db_path) as connection:
        # Lock before reading the status so concurrent confirmations cannot both apply it.
        connection.execute("BEGIN IMMEDIATE")
        ensure_proposals(connection)
        proposal = connection.execute("SELECT * FROM command_proposals WHERE id = ?", (proposal_id,)).fetchone()
        if proposal is None:
            raise ProposalError("This proposal could not be found.", 404)

        status = "applied" if confirm else "cancelled"
        if proposal["status"] == status:
            return {"state": status}
        if proposal["status"] != "pending":
            raise ProposalError(f"This proposal was already {proposal['status']}.", 409)
        if datetime.fromisoformat(proposal["expires_at"]) <= datetime.now(timezone.utc):
            raise ProposalError("This proposal expired. Run the command again.", 410)

        if confirm:
            for item in json.loads(proposal["actions"]):
                apply_action(item, connection)
        # Status and domain writes commit or roll back together.
        connection.execute("UPDATE command_proposals SET status = ? WHERE id = ?", (status, proposal_id))
        return {"state": status}
