import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agenda import get_agenda
from database import DATABASE_PATH
from goal_api import goal_router
from planner import period_bounds
from schedule_api import schedule_router
from task_api import task_router


class AgendaItem(BaseModel):
    id: int
    source: Literal["schedule", "task"]
    date: date
    title: str
    kind: str
    time: str | None
    completed: bool | None
    priority: str | None


class DailyAgenda(BaseModel):
    date: date
    items: list[AgendaItem]


class PlannerItem(AgendaItem):
    series_start: date | None = None
    repeat: str | None = None


class PlannerPeriod(BaseModel):
    first: date
    last: date
    items: list[PlannerItem]


def create_app(db_path: Path = DATABASE_PATH):
    api = FastAPI(title="Momentum API")
    # SQLite enforces read-only access on GET routes and opens existing files only.
    database_uri = db_path.resolve().as_uri()
    api.include_router(task_router(database_uri + "?mode=rw"))
    api.include_router(schedule_router(database_uri + "?mode=rw"))
    api.include_router(goal_router(database_uri))

    @api.exception_handler(sqlite3.OperationalError)
    async def database_unavailable(_request: Request, _error: sqlite3.OperationalError):
        return JSONResponse(status_code=503, content={"detail": "The database is unavailable."})

    @api.get("/api/agenda", response_model=DailyAgenda)
    def daily_agenda(day: Annotated[date, Query(alias="date")]):
        items = get_agenda(day, day, db_path=database_uri + "?mode=ro")
        return {"date": day, "items": items}

    @api.get("/api/planner", response_model=PlannerPeriod)
    def planner_period(day: Annotated[date, Query(alias="date")], view: Literal["Day", "Week", "Month"] = "Week"):
        first, last = period_bounds(day, view)
        return {"first": first, "last": last, "items": get_agenda(first, last, db_path=database_uri + "?mode=ro")}

    return api


app = create_app(Path(os.environ.get("MOMENTUM_DB_PATH", DATABASE_PATH)))
