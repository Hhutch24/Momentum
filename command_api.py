from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints

from command_service import ProposalError, finish_proposal, preview_command
from model_commands import ModelUnavailable, model_enabled, preview_model_command


class CommandInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    today: date
    mode: Literal["local", "ai"] = "local"


def command_router(db_path):
    router = APIRouter(prefix="/api/commands")

    @router.get("/config")
    def config():
        return {"ai_enabled": model_enabled()}

    @router.post("/preview")
    def preview(command: CommandInput):
        if command.mode == "ai":
            try:
                return preview_model_command(command.text, command.today, db_path)
            except ModelUnavailable as error:
                raise HTTPException(status_code=503, detail=str(error)) from error
        return preview_command(command.text, command.today, db_path)

    def finish(proposal_id, confirm):
        try:
            return finish_proposal(proposal_id.hex, confirm, db_path)
        except ProposalError as error:
            raise HTTPException(status_code=error.status_code, detail=str(error)) from error

    @router.post("/{proposal_id}/confirm")
    def confirm(proposal_id: UUID):
        return finish(proposal_id, True)

    @router.post("/{proposal_id}/cancel")
    def cancel(proposal_id: UUID):
        return finish(proposal_id, False)

    return router
