import re
from datetime import date, timedelta


def parse_day(text, today):
    if text.lower() == "today":
        return today
    if text.lower() == "tomorrow":
        return today + timedelta(days=1)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
    raise ValueError("Which date did you mean? Try today, tomorrow, or YYYY-MM-DD.")


def parse_command(text, today):
    text = text.strip().rstrip("?!").strip()
    query = re.fullmatch(r"(?:what['’]s coming up|show my schedule) (today|this week|next month)", text, re.I)
    if query:
        return {"action": "agenda", "period": query[1].lower()}

    goal = re.fullmatch(r"log (\d+(?:\.\d+)?) (?:toward|for) (.+)", text, re.I)
    if goal:
        amount = float(goal[1])
        if not 0 < amount < float("inf"):
            raise ValueError("Enter a positive progress amount.")
        return {"action": "goal", "amount": amount, "title": goal[2]}

    reminder = re.fullmatch(r"remind me to (.+?)(?: on (.+)| (today|tomorrow))", text, re.I)
    if reminder:
        return {"action": "reminder", "title": reminder[1], "day": parse_day(reminder[2] or reminder[3], today)}
    if text.lower().startswith("remind me to "):
        raise ValueError("When should I remind you? Try: Remind me to call Sam tomorrow.")

    shopping = re.fullmatch(r"(?:i need|add to shopping) (.+)", text, re.I)
    if shopping:
        return {"action": "shopping", "title": shopping[1]}

    task = re.fullmatch(r"(?:add task|task:)\s+(.+)", text, re.I)
    if task:
        parts = re.split(r"\s+due\s+", task[1], maxsplit=1, flags=re.I)
        return {"action": "task", "title": parts[0], "day": parse_day(parts[1], today) if len(parts) == 2 else None}

    raise ValueError("I couldn't match that request. Try one of the examples below the command box.")
