from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request

from app.schemas.assistant import AssistantAnswer, QuestionRequest
from app.schemas.run import RunRecord
from app.services.design_assistant import DesignAssistant

router = APIRouter(tags=["design-assistant"])


def _assistant(request: Request) -> DesignAssistant:
    runs = request.app.state.run_service
    if not hasattr(runs, "design_assistant"):
        runs.design_assistant = DesignAssistant(runs)
    return runs.design_assistant


@router.post("/assistant/questions", response_model=AssistantAnswer)
async def ask_question(question: QuestionRequest, request: Request):
    return await _assistant(request).ask(question)


@router.get("/assistant/conversations/{conversation_id}", response_model=list[AssistantAnswer])
def conversation(conversation_id: UUID, request: Request):
    return _assistant(request).repository.history(conversation_id)


@router.post("/assistant/answers/{answer_id}/confirm", response_model=RunRecord, status_code=202)
def confirm_proposal(answer_id: UUID, request: Request, background_tasks: BackgroundTasks):
    assistant = _assistant(request)
    record, decision = assistant.confirm(answer_id)
    background_tasks.add_task(assistant.runs.resume, record.id, decision)
    return record
