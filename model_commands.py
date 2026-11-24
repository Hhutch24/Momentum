import json
import logging
import os
import re
from datetime import date

import httpx
from pydantic import ValidationError

import database as db
from command_service import action, agenda_result, resolve_goal, store_proposal, task_action
from goal_api import CheckinInput, GoalInput, MilestoneInput
from schedule_api import ScheduleEntry
from task_api import TaskDetails


# A strict tool describes a proposal. Momentum resolves records and performs writes.
TEXT = {"type": "string"}
OPTIONAL_TEXT = {"type": ["string", "null"]}
AMOUNT = {"type": "number"}
LOGGER = logging.getLogger("uvicorn.error")


def tool(name, description, **properties):
    return {"type": "function", "name": name, "description": description, "strict": True,
            "parameters": {"type": "object", "properties": properties,
                           "required": list(properties), "additionalProperties": False}}


TOOLS = [
    tool("add_task", "Create a task. Use an ISO date or null for no due date.", title=TEXT, due_date=OPTIONAL_TEXT),
    tool("rename_task", "Rename a task specified by exact title or Task #ID.", task=TEXT, title=TEXT),
    tool("add_shopping_item", "Add one item to Shopping.", title=TEXT),
    tool("add_event", "Add a calendar entry on an ISO date. Use local HH:MM or null for time.",
         title=TEXT, day=TEXT, event_time=OPTIONAL_TEXT,
         kind={"type": "string", "enum": ["Appointment", "Event", "Deadline", "Birthday", "Reminder"]},
         repeat={"type": "string", "enum": ["None", "Daily", "Weekly", "Monthly", "Yearly"]}),
    tool("add_goal", "Create a goal with its numeric target and unit (empty if unspecified).", title=TEXT, target=AMOUNT, unit=TEXT),
    tool("add_milestone", "Add a milestone to an existing goal specified by exact name or Goal #ID.", goal=TEXT, title=TEXT, threshold=AMOUNT),
    tool("log_progress", "Log progress toward an existing goal by exact name or Goal #ID. Use ISO date or null for today.",
         goal=TEXT, amount=AMOUNT, day=OPTIONAL_TEXT, note=TEXT),
    tool("show_schedule", "Show schedule for an inclusive period of at most 31 days. Use ISO dates.", first=TEXT, last=TEXT),
    tool("ask_clarification", "Ask one short question when details are missing or the request is unsupported.", message=TEXT),
]
TOOL_FIELDS = {item["name"]: item["parameters"]["properties"] for item in TOOLS}
INSTRUCTIONS = (
    "Interpret the user's Momentum productivity request by calling the provided tools. "
    "Use at most five calls, in request order, and one call per requested change. "
    "Use ask_clarification alone when a required title, date, target, or other meaningful detail is missing. "
    "For schedule-only requests use show_schedule alone. Do not combine questions or reads with changes. "
    "Resolve relative dates using the date given in these instructions, use Monday through Sunday for weeks, "
    "and preserve user-provided titles without making up IDs, times, or missing details. "
    "For reminders without a date ask which day. Use repeat None unless the user asks for recurrence. "
    "Tools describe proposed changes for a preview; never claim that anything was saved."
)


class ModelUnavailable(Exception):
    pass


def model_enabled():
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def model_calls(text, today):
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ModelUnavailable("AI mode requires an OpenAI API key on the server.")
    model = os.environ.get("MOMENTUM_OPENAI_MODEL", "").strip() or "gpt-5.4-mini"
    try:
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "store": False, "max_output_tokens": 1200,
                  "instructions": f"{INSTRUCTIONS} Today is {today.isoformat()}.",
                  "input": text, "tools": TOOLS, "tool_choice": "required"},
            timeout=20.0,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ModelUnavailable("The AI service is unavailable. Try again or switch to local commands.") from error

    if not isinstance(data, dict) or data.get("status") != "completed" or not isinstance(data.get("output"), list):
        raise ModelUnavailable("The AI service did not complete the request. Try a shorter command.")
    usage = data.get("usage")
    if isinstance(usage, dict):
        LOGGER.info("Momentum AI usage: input_tokens=%s output_tokens=%s",
                    usage.get("input_tokens"), usage.get("output_tokens"))
    return [item for item in data["output"] if isinstance(item, dict) and item.get("type") == "function_call"]


def resolve_task(name, db_path):
    identifier = re.fullmatch(r"task #(\d+)", name.strip(), re.I)
    tasks = db.get_tasks(db_path, list_name="Tasks")
    matches = [task for task in tasks if (task["id"] == int(identifier[1]) if identifier
               else task["title"].casefold() == name.strip().casefold())]
    if len(matches) > 1:
        choices = ", ".join(f"Task #{task['id']}" for task in matches)
        raise ValueError(f"Which task did you mean? Try one of these IDs: {choices}.")
    if not matches:
        raise ValueError("Which task did you mean? Try its exact title or Task #ID.")
    return matches[0]


def interpret_call(name, values, today, db_path):
    match name:
        case "add_task":
            due_date = date.fromisoformat(values["due_date"]) if values["due_date"] is not None else None
            return task_action(values["title"], due_date)
        case "add_shopping_item":
            return task_action(values["title"], shopping=True)
        case "rename_task":
            task = resolve_task(values["task"], db_path)
            details = TaskDetails(title=values["title"])
            return action("rename", details, f"Rename “{task['title']}” (Task #{task['id']}) to “{details.title}”",
                          task_id=task["id"], original_title=task["title"])
        case "add_event":
            entry = ScheduleEntry.model_validate(values)
            clock = f" at {entry.event_time:%H:%M}" if entry.event_time else ""
            repeat = f", repeats {entry.repeat.lower()}" if entry.repeat != "None" else ""
            return action("schedule", entry, f"Add {entry.kind.lower()} “{entry.title}” on {entry.day}{clock}{repeat}")
        case "add_goal":
            goal = GoalInput.model_validate(values)
            unit = f" {goal.unit}" if goal.unit else ""
            return action("goal", goal, f"Add goal “{goal.title}” with a target of {goal.target:g}{unit}")
        case "add_milestone":
            goal = resolve_goal(values["goal"], db_path)
            milestone = MilestoneInput(title=values["title"], threshold=values["threshold"])
            return action("milestone", milestone,
                          f"Add milestone “{milestone.title}” at {milestone.threshold:g} for “{goal['title']}” (Goal #{goal['id']})",
                          goal_id=goal["id"])
        case "log_progress":
            goal = resolve_goal(values["goal"], db_path)
            checkin = CheckinInput(day=values["day"] or today, amount=values["amount"], note=values["note"])
            if checkin.day > date.today():
                raise ValueError("Which day did you mean? Goal check-ins need today’s date or an earlier date.")
            note = f" · Note: {checkin.note}" if checkin.note else ""
            return action("checkin", checkin, f"Log {checkin.amount:g} toward “{goal['title']}” (Goal #{goal['id']}) on {checkin.day}{note}",
                          goal_id=goal["id"])
    raise ValueError("This action is unsupported.")


def preview_model_command(text, today, db_path):
    calls = model_calls(text, today)
    if not 1 <= len(calls) <= 5:
        return {"state": "clarification", "message": "Try one to five changes or one schedule question at a time."}
    try:
        commands = []
        for call in calls:
            name = call.get("name")
            fields = TOOL_FIELDS.get(name)
            values = json.loads(call.get("arguments", ""))
            if fields is None or not isinstance(values, dict) or values.keys() != fields.keys():
                raise ValueError("Unsupported or incomplete tool call.")
            for key, field in fields.items():
                expected = field["type"]
                value = values[key]
                valid = type(value) in (int, float) if expected == "number" else isinstance(value, str)
                if not valid and not (expected == ["string", "null"] and value is None):
                    raise ValueError("Invalid tool arguments.")
            commands.append((name, values))
    except (TypeError, ValueError):
        return {"state": "clarification", "message": "The proposed command was incomplete. Please rephrase it."}

    for name, values in commands:
        if name == "ask_clarification":
            return {"state": "clarification", "message": values["message"].strip()[:300] or "Could you clarify your request?"}
        if name == "show_schedule":
            if len(commands) != 1:
                return {"state": "clarification", "message": "Could you ask the schedule question separately?"}
            try:
                return agenda_result(date.fromisoformat(values["first"]), date.fromisoformat(values["last"]), db_path)
            except ValueError:
                return {"state": "clarification", "message": "Which dates should I show? Choose a range of up to 31 days."}
    try:
        actions = [interpret_call(name, values, today, db_path) for name, values in commands]
    except ValidationError:
        return {"state": "clarification", "message": "Check the title, date, and amounts, then try again."}
    except (ValueError, OverflowError) as error:
        return {"state": "clarification", "message": str(error)}
    return store_proposal(actions, db_path)
