from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints

from command_service import ProposalError, finish_proposal, preview_command


class CommandInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    today: date


def command_router(db_path):
    router = APIRouter(prefix="/api/commands")

    @router.post("/preview")
    def preview(command: CommandInput):
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
