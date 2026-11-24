import argparse
from datetime import date, time, timedelta
from pathlib import Path

import database as db


def seed_demo(path, today):
    # Creating the file exclusively also protects a database supplied accidentally.
    with path.open("xb"):
        pass
    db.initialize_database(path)
    db.create_task("Review the weekly plan", path, due_date=today, priority="High", repeat="Weekly")
    completed = db.create_task("Pack gym bag", path, due_date=today)
    db.update_task_completion(completed, True, path)
    db.create_task("Coffee", path, list_name="Shopping")
    db.save_schedule("Portfolio walkthrough", "Appointment", today, time(10, 30), "None", path)
    db.save_schedule("Water the plants", "Reminder", today + timedelta(days=1), None, "Weekly", path)
    goal = db.create_goal("Reading", 100, "pages", path)
    db.add_milestone(goal, "First chapter", 15, path)
    db.add_checkin(goal, today, 10, "Read before breakfast", path)


def main():
    parser = argparse.ArgumentParser(description="Create a new SQLite database with fictional Momentum demo data.")
    parser.add_argument("--path", type=Path, default=Path("momentum-demo.db"))
    args = parser.parse_args()
    try:
        seed_demo(args.path, date.today())
    except FileExistsError:
        parser.exit(1, "That database already exists. Choose a new path.\n")
    print(f"Demo database created at {args.path.resolve()}")


if __name__ == "__main__":
    main()
