import calendar
from datetime import date, timedelta


RECURRENCE = ("None", "Daily", "Weekly", "Monthly", "Yearly")


def repeat_date(start, repeat, index):
    """Find an occurrence using the original date as the anchor."""
    if repeat in ("Daily", "Weekly"):
        return start + timedelta(days=index * (7 if repeat == "Weekly" else 1))
    months = index * (12 if repeat == "Yearly" else 1)
    year_offset, month_index = divmod(start.month - 1 + months, 12)
    year, month = start.year + year_offset, month_index + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def period_bounds(day, view):
    if view == "Day":
        return day, day
    if view == "Week":
        start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=min(6, (date.max - start).days))
    return day.replace(day=1), day.replace(day=calendar.monthrange(day.year, day.month)[1])


def scheduled_occurrences(entries, first, last):
    occurrences = []
    for entry in entries:
        start = date.fromisoformat(entry["day"])
        repeat = entry["repeat"]
        if repeat == "None":
            if first <= start <= last:
                occurrences.append((start, entry))
            continue
        if repeat in ("Daily", "Weekly"):
            interval = 7 if repeat == "Weekly" else 1
            index = max(0, ((first - start).days + interval - 1) // interval)
        else:
            months = (first.year - start.year) * 12 + first.month - start.month
            index = max(0, months // (12 if repeat == "Yearly" else 1))
        while True:
            try:
                day = repeat_date(start, repeat, index)
            except (OverflowError, ValueError):
                # The next occurrence is beyond Python's maximum calendar date.
                break
            if day > last:
                break
            if day >= first:
                occurrences.append((day, entry))
            if day == last:
                break
            index += 1
    return sorted(occurrences, key=lambda item: (item[0], item[1]["time"] or "", item[1]["id"]))
