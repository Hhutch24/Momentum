from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

import database as db


GoalId = Annotated[int, Path(gt=0, le=2**63 - 1)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
TrimmedText = Annotated[str, StringConstraints(strip_whitespace=True)]
PositiveAmount = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class GoalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    target: PositiveAmount
    unit: TrimmedText = ""


class CheckinInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date
    amount: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    note: TrimmedText = ""


class MilestoneInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    threshold: PositiveAmount


def goal_router(database_uri):
    router = APIRouter(prefix="/api/goals")
    read_uri = database_uri + "?mode=ro"
    write_uri = database_uri + "?mode=rw"

    @router.get("")
    def list_goals(day: date):
        return [dict(goal) for goal in db.get_goal_summaries(day, read_uri)]

    @router.get("/{goal_id}")
    def goal_detail(goal_id: GoalId, day: date):
        goals = db.get_goal_summaries(day, read_uri, goal_id=goal_id)
        if not goals:
            raise HTTPException(status_code=404, detail="This goal no longer exists.")
        goal = dict(goals[0])
        return {
            **goal,
            "checkins": [dict(checkin) for checkin in db.get_checkins(goal_id, read_uri)],
            "milestones": [dict(milestone, reached=goal["progress"] >= milestone["threshold"])
                           for milestone in db.get_milestones(goal_id, read_uri)],
        }

    @router.post("", status_code=201)
    def create_goal(goal: GoalInput):
        return {"id": db.create_goal(db_path=write_uri, **goal.model_dump())}

    @router.post("/{goal_id}/checkins", status_code=204)
    def add_checkin(goal_id: GoalId, checkin: CheckinInput):
        if checkin.day > date.today():
            raise HTTPException(status_code=422, detail="Choose today or an earlier check-in date.")
        if not db.add_checkin(goal_id, db_path=write_uri, **checkin.model_dump()):
            raise HTTPException(status_code=404, detail="This goal no longer exists.")

    @router.post("/{goal_id}/milestones", status_code=204)
    def add_milestone(goal_id: GoalId, milestone: MilestoneInput):
        if not db.add_milestone(goal_id, db_path=write_uri, **milestone.model_dump()):
            raise HTTPException(status_code=404, detail="This goal no longer exists.")

    @router.delete("/{goal_id}", status_code=204)
    def delete_goal(goal_id: GoalId):
        if not db.delete_goal(goal_id, write_uri):
            raise HTTPException(status_code=404, detail="This goal no longer exists.")

    return router
