from datetime import date, time
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

import database as db


ScheduleKind = Literal["Appointment", "Event", "Deadline", "Birthday", "Reminder"]
Repeat = Literal["None", "Daily", "Weekly", "Monthly", "Yearly"]
EntryId = Annotated[int, Path(gt=0, le=2**63 - 1)]


class ScheduleEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    kind: ScheduleKind
    day: date
    event_time: time | None = None
    repeat: Repeat = "None"

    @field_validator("event_time")
    @classmethod
    def validate_local_time(cls, value):
        if value is not None and (value.tzinfo is not None or value.second or value.microsecond):
            raise ValueError("Choose a local time in hours and minutes.")
        return value


def schedule_router(database_uri):
    router = APIRouter(prefix="/api/schedule")

    @router.post("", status_code=201)
    def create_entry(entry: ScheduleEntry):
        return {"id": db.save_schedule(db_path=database_uri, **entry.model_dump())}

    @router.put("/{entry_id}", status_code=204)
    def edit_entry(entry_id: EntryId, entry: ScheduleEntry):
        if not db.save_schedule(db_path=database_uri, entry_id=entry_id, **entry.model_dump()):
            raise HTTPException(status_code=404, detail="This entry no longer exists.")

    @router.delete("/{entry_id}", status_code=204)
    def delete_entry(entry_id: EntryId):
        if not db.delete_schedule(entry_id, database_uri):
            raise HTTPException(status_code=404, detail="This entry no longer exists.")

    return router
