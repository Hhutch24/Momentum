import calendar
from datetime import date, time, timedelta

import streamlit as st

import database as db
from agenda import get_agenda
from commands import parse_command
from planner import RECURRENCE, period_bounds, repeat_date, scheduled_occurrences


SCHEDULE_KINDS = ("Appointment", "Event", "Deadline", "Birthday", "Reminder")


def show_tasks(list_name, today):
    shopping = list_name == "Shopping"
    st.header("Shopping list" if shopping else "Tasks")
    with st.form("new_task", clear_on_submit=True):
        title = st.text_input("Item" if shopping else "Task title")
        due_date, priority, repeat = None, "Normal", "None"
        if not shopping:
            due_date = st.date_input("Due date (optional)", value=None)
            priority = st.selectbox("Priority", db.PRIORITIES)
            repeat = st.selectbox("Repeat", db.TASK_REPEAT, help="Completing a repeating task adds its next occurrence.")
        if st.form_submit_button("Add item" if shopping else "Add task"):
            try:
                if not title.strip():
                    raise ValueError("Enter a title.")
                db.create_task(title.strip(), list_name=list_name, due_date=due_date,
                               priority=priority, repeat=repeat)
            except ValueError as error:
                st.error(str(error))

    tasks = [task for task in db.get_tasks() if task["list_name"] == list_name]
    if not shopping:
        filter_name = st.radio("Show tasks", ("All tasks", "Due today", "Open tasks"),
                               horizontal=True, key="task_filter")
        if filter_name == "Due today":
            tasks = [task for task in tasks if task["due_date"] == today.isoformat()]
        elif filter_name == "Open tasks":
            tasks = [task for task in tasks if not task["completed"]]
    if not tasks:
        st.info("No items to show.")

    for task in tasks:
        task_id = task["id"]
        checkbox_key = f"task_{task_id}"
        task_column, edit_column, delete_column = st.columns([4, 1, 1])
        task_column.checkbox(task["title"], value=bool(task["completed"]), key=checkbox_key,
                             on_change=save_completion, args=(task_id, checkbox_key))
        details = []
        if task["due_date"]:
            details.append(f"Due {task['due_date']}")
        if task["priority"] != "Normal":
            details.append(f"{task['priority']} priority")
        if task["repeat"] != "None":
            details.append(task["repeat"])
        if details:
            task_column.caption(" · ".join(details))
        edit_column.button("Edit", key=f"edit_{task_id}", on_click=begin_task_edit, args=(task_id,))
        delete_column.button("Delete", key=f"delete_{task_id}", on_click=db.delete_task, args=(task_id,))

        if st.session_state.get("editing_task_id") == task_id:
            with st.form(f"edit_task_{task_id}"):
                title = st.text_input("Title", value=task["title"])
                options = {}
                if not shopping:
                    options["due_date"] = st.date_input("Due date (optional)", value=task["due_date"])
                    options["priority"] = st.selectbox("Priority", db.PRIORITIES, index=db.PRIORITIES.index(task["priority"]))
                    options["repeat"] = st.selectbox("Repeat", db.TASK_REPEAT, index=db.TASK_REPEAT.index(task["repeat"]))
                save = st.form_submit_button("Save")
                cancel = st.form_submit_button("Cancel")
                if save:
                    try:
                        db.update_task_title(task_id, title, **options)
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        cancel = True
                if cancel:
                    st.session_state.editing_task_id = None
                    st.rerun()


def save_completion(task_id, checkbox_key):
    db.update_task_completion(task_id, st.session_state[checkbox_key])


def begin_task_edit(task_id):
    st.session_state.editing_task_id = task_id


def agenda(first, last):
    items = []
    for entry in get_agenda(first, last):
        kind = entry["kind"]
        if entry["source"] == "task":
            kind = "Completed task" if entry["completed"] else "Task due"
        start_time = f"{entry['time']} · " if entry["time"] else ""
        items.append((entry["date"], f"{start_time}{kind} · {entry['title']}"))
    return items


def show_agenda(first, last):
    items = agenda(first, last)
    if not items:
        st.info("Nothing scheduled for this period.")
    for day, label in items:
        st.text(f"{day:%a, %b %d} · {label}")


def show_planner(today):
    st.header("Planner")
    view = st.radio("Calendar view", ("Day", "Week", "Month"), index=1,
                    horizontal=True, key="calendar_view")
    selected = st.date_input("Go to date", value=today)
    if selected is not None:
        first, last = period_bounds(selected, view)
        if view == "Month":
            entries_by_day = {}
            for day, label in agenda(first, last):
                entries_by_day.setdefault(day.day, []).append(label)
            st.caption(selected.strftime("%B %Y"))
            for column, weekday in zip(st.columns(7), calendar.day_abbr):
                column.caption(weekday)
            for week in calendar.monthcalendar(selected.year, selected.month):
                for column, day_number in zip(st.columns(7), week):
                    if day_number:
                        column.write(day_number)
                        for label in entries_by_day.get(day_number, []):
                            column.text(label)
        else:
            show_agenda(first, last)
    with st.expander("Add an event or reminder"):
        schedule_form(today)
    with st.expander("Manage saved events and reminders"):
        entries = db.get_schedule()
        if not entries:
            st.info("No events or reminders yet.")
        for entry in entries:
            entry_id = entry["id"]
            label = f"{entry['day']} · {entry['kind']} · {entry['title']}"
            with st.expander(label):
                schedule_form(today, entry)
                st.button("Delete entry", key=f"delete_entry_{entry_id}", on_click=db.delete_schedule, args=(entry_id,))


def schedule_form(today, entry=None):
    form_key = f"schedule_{entry['id']}" if entry else "new_schedule"
    with st.form(form_key, clear_on_submit=entry is None):
        title = st.text_input("Title", value=entry["title"] if entry else "")
        kind = st.selectbox("Type", SCHEDULE_KINDS, index=SCHEDULE_KINDS.index(entry["kind"]) if entry else 0)
        day = st.date_input("Date", value=entry["day"] if entry else today)
        event_time = st.time_input("Time (optional)", value=time.fromisoformat(entry["time"]) if entry and entry["time"] else None)
        repeat = st.selectbox("Repeat", RECURRENCE, index=RECURRENCE.index(entry["repeat"]) if entry else 0)
        if st.form_submit_button("Save entry" if entry else "Add entry"):
            if not title.strip() or day is None:
                st.error("Enter a title and date.")
            else:
                db.save_schedule(title.strip(), kind, day, event_time, repeat, entry_id=entry["id"] if entry else None)
                st.rerun()


def show_progress(goal):
    st.text(goal["title"])
    st.progress(min(1.0, goal["progress"] / goal["target"]))
    st.caption(f"{goal['progress']:g} / {goal['target']:g} {goal['unit']}")


def show_goals(today):
    st.header("Goals")
    with st.form("new_goal", clear_on_submit=True):
        title = st.text_input("Goal name")
        target = st.number_input("Target amount", min_value=0.01, value=1.0)
        unit = st.text_input("Unit (optional)", placeholder="Dollars, pages, workouts")
        if st.form_submit_button("Add goal"):
            if title.strip():
                db.create_goal(title.strip(), target, unit.strip())
            else:
                st.error("Enter a goal name.")

    for goal in db.get_goals():
        goal_id = goal["id"]
        with st.expander(f"{goal['title']} · Goal {goal_id}"):
            show_progress(goal)
            with st.form(f"checkin_{goal_id}", clear_on_submit=True):
                amount = st.number_input("Progress to add", min_value=0.0)
                day = st.date_input("Check-in date", value=today, max_value=today)
                note = st.text_input("Check-in note (optional)")
                if st.form_submit_button("Log check-in"):
                    if day is None:
                        st.error("Choose a check-in date.")
                    else:
                        db.add_checkin(goal_id, day, amount, note.strip())
                        st.rerun()
            with st.form(f"milestone_{goal_id}", clear_on_submit=True):
                name = st.text_input("Milestone name")
                threshold = st.number_input("Progress needed", min_value=0.01, value=1.0)
                if st.form_submit_button("Add milestone"):
                    if name.strip():
                        db.add_milestone(goal_id, name.strip(), threshold)
                    else:
                        st.error("Enter a milestone name.")
            with st.form(f"goal_reminder_{goal_id}"):
                reminder_day = st.date_input("First check-in reminder", value=today, min_value=today)
                repeat = st.selectbox("Check-in frequency", ("Weekly", "Monthly"))
                if st.form_submit_button("Schedule check-in reminder"):
                    if reminder_day is None:
                        st.error("Choose a reminder date.")
                    else:
                        db.save_schedule(f"Check in on {goal['title']}", "Reminder", reminder_day, None, repeat)
                        st.success("Reminder added to Planner.")
            for milestone in db.get_milestones(goal_id):
                status = "Reached" if goal["progress"] >= milestone["threshold"] else "Upcoming"
                st.text(f"{status} · {milestone['title']} ({milestone['threshold']:g})")

            history = db.get_checkins(goal_id)
            for view in ("Week", "Month"):
                first, _ = period_bounds(today, view)
                total = sum(row["amount"] for row in history if first.isoformat() <= row["day"] <= today.isoformat())
                st.caption(f"This {view.lower()} · {total:g} {goal['unit']}")
            for row in history:
                st.text(f"{row['day']} · +{row['amount']:g} {goal['unit']} {row['note']}".strip())
            if st.checkbox("Confirm deleting this goal and its history", key=f"confirm_goal_{goal_id}"):
                st.button("Delete goal", key=f"delete_goal_{goal_id}", on_click=db.delete_goal, args=(goal_id,))


def command_box(today):
    feedback = st.session_state.pop("command_feedback", None)
    if feedback:
        st.write(feedback)
    with st.form("command", clear_on_submit=True):
        text = st.text_input("What would you like to do?")
        submit = st.form_submit_button("Run command")
    st.caption("Try: I need bananas · Add task study due tomorrow · Remind me to call Sam tomorrow · What's coming up this week? · Log 10 toward Reading")
    if submit:
        st.session_state.pop("pending_command", None)
        try:
            command = parse_command(text, today)
            if command["action"] == "goal":
                name = command["title"].casefold()
                goals = [goal for goal in db.get_goals() if goal["title"].casefold() == name or f"goal {goal['id']}" == name]
                if len(goals) != 1:
                    raise ValueError("Which goal? Use its exact name or its number, such as ‘Log 10 toward Goal 2’.")
                command.update(goal_id=goals[0]["id"], title=goals[0]["title"])
            st.session_state.pending_command = command
        except ValueError as error:
            st.warning(str(error))

    command = st.session_state.get("pending_command")
    if not command:
        return
    action = command["action"]
    if action == "agenda":
        period = command["period"]
        if period == "today":
            first, last = today, today
        elif period == "this week":
            _, last = period_bounds(today, "Week")
            first = today
        else:
            first, last = period_bounds(repeat_date(today.replace(day=1), "Monthly", 1), "Month")
        show_agenda(first, last)
        return

    if action == "goal":
        st.text(f"Log {command['amount']:g} toward {command['title']}")
    else:
        day = command.get("day")
        label = "shopping item" if action == "shopping" else action
        st.text(f"Add {label} · {command['title']}" + (f" · {day}" if day else ""))
    confirm, cancel = st.columns(2)
    if confirm.button("Confirm"):
        if action == "goal":
            if any(goal["id"] == command["goal_id"] for goal in db.get_goals()):
                db.add_checkin(command["goal_id"], today, command["amount"], "")
                feedback = "Progress saved."
            else:
                feedback = "That goal is no longer available."
        elif action == "reminder":
            db.save_schedule(command["title"], "Reminder", command["day"], None, "None")
            feedback = "Reminder saved."
        else:
            db.create_task(command["title"], list_name="Shopping" if action == "shopping" else "Tasks",
                           due_date=command.get("day"))
            feedback = "Item saved."
        st.session_state.pop("pending_command", None)
        st.session_state.command_feedback = feedback
        st.rerun()
    if cancel.button("Cancel command"):
        st.session_state.pop("pending_command", None)
        st.rerun()


def show_home(today):
    command_box(today)
    st.header("Today")
    show_agenda(today, today)
    st.header("Upcoming events and reminders")
    upcoming = scheduled_occurrences(db.get_schedule(), today + timedelta(days=1), today + timedelta(days=7))
    if not upcoming:
        st.info("No events or reminders in the next seven days.")
    for day, entry in upcoming:
        start_time = f"{entry['time']} · " if entry["time"] else ""
        st.text(f"{day:%a, %b %d} · {start_time}{entry['kind']} · {entry['title']}")
    st.header("Goals")
    goals = db.get_goals()
    if not goals:
        st.info("Add a goal to track your progress here.")
    for goal in goals[:3]:
        show_progress(goal)


def main():
    st.set_page_config(page_title="Momentum", page_icon="📅", layout="wide")
    db.initialize_database()
    st.title("Momentum 📅")
    page = st.sidebar.radio("Navigate", ("Home", "Tasks", "Planner", "Shopping", "Goals"))
    today = date.today()
    if page == "Home":
        show_home(today)
    elif page == "Planner":
        show_planner(today)
    elif page == "Goals":
        show_goals(today)
    else:
        show_tasks(page, today)


if __name__ == "__main__":
    main()
