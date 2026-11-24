from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, ConfigDict, StrictBool, StringConstraints

import database as db


ListName = Literal["Tasks", "Shopping"]
Priority = Literal["Normal", "High", "Low"]
Repeat = Literal["None", "Daily", "Weekly"]
TaskId = Annotated[int, Path(gt=0, le=2**63 - 1)]


class TaskDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    due_date: date | None = None
    priority: Priority = "Normal"
    repeat: Repeat = "None"


class NewTask(TaskDetails):
    list_name: ListName = "Tasks"


class Completion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completed: StrictBool


class Task(TaskDetails):
    id: int
    title: str
    list_name: ListName
    completed: bool


def task_router(database_uri):
    router = APIRouter(prefix="/api/tasks")

    @router.get("", response_model=list[Task])
    def list_tasks(list_name: ListName = "Tasks"):
        fields = Task.model_fields
        return [{name: row[name] for name in fields} for row in db.get_tasks(database_uri, list_name=list_name)]

    @router.post("", status_code=201)
    def create_task(task: NewTask):
        try:
            task_id = db.create_task(db_path=database_uri, **task.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"id": task_id}

    @router.patch("/{task_id}", status_code=204)
    def edit_task(task_id: TaskId, task: TaskDetails):
        try:
            updated = db.update_task_title(task_id, db_path=database_uri, **task.model_dump(exclude_unset=True))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not updated:
            raise HTTPException(status_code=404, detail="This item no longer exists.")

    @router.patch("/{task_id}/completion", status_code=204)
    def complete_task(task_id: TaskId, completion: Completion):
        try:
            updated = db.update_task_completion(task_id, completion.completed, database_uri)
        except OverflowError as error:
            raise HTTPException(status_code=422, detail="The next due date is outside the supported range.") from error
        if not updated:
            raise HTTPException(status_code=404, detail="This item no longer exists.")

    @router.delete("/{task_id}", status_code=204)
    def delete_task(task_id: TaskId):
        if not db.delete_task(task_id, database_uri):
            raise HTTPException(status_code=404, detail="This item no longer exists.")

    return router
