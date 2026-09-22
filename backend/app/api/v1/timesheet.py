"""Authenticated, self-scoped timesheet status and commands."""

from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.dependencies import APIProblem, RequestContext, get_request_context
from app.core.database import get_db
from app.schemas.timesheet import CommandRequest, TimesheetCommandResponse, TimesheetStatusResponse
from app.services.timesheet_service import TimesheetConflict, TimesheetService

router = APIRouter()

_MESSAGES = {
    "start-work": "Работа начата.",
    "start-break": "Перерыв начат.",
    "end-break": "Работа продолжена.",
    "finish-work": "Рабочий день завершён.",
}


def _problem(error: TimesheetConflict) -> APIProblem:
    code = str(error)
    if code == "TRACK_TIME_DISABLED":
        return APIProblem(403, code, "Учёт рабочего времени отключён.")
    if code == "IDEMPOTENCY_KEY_REUSED":
        return APIProblem(409, code, "Ключ команды уже использован для другого действия.")
    if code == "ACCOUNT_SCOPE_INVALID":
        return APIProblem(403, "ACCESS_DENIED", "Нет доступа к аккаунту.")
    return APIProblem(409, "STATUS_TRANSITION_INVALID", "Статус уже изменился. Обновите страницу.")


@router.get("/my-status", response_model=TimesheetStatusResponse)
def my_status(db: Session = Depends(get_db), context: RequestContext = Depends(get_request_context)):
    try:
        return asdict(TimesheetService(db).get_status(context))
    except TimesheetConflict as error:
        raise _problem(error) from error


def _apply(action: str, body: CommandRequest, db: Session, context: RequestContext):
    try:
        result = TimesheetService(db).apply(context, action, body.idempotency_key)
    except TimesheetConflict as error:
        raise _problem(error) from error
    return {**asdict(result), "message": _MESSAGES[action]}


@router.post("/start-work", response_model=TimesheetCommandResponse)
def start_work(body: CommandRequest, db: Session = Depends(get_db), context: RequestContext = Depends(get_request_context)):
    return _apply("start-work", body, db, context)


@router.post("/start-break", response_model=TimesheetCommandResponse)
def start_break(body: CommandRequest, db: Session = Depends(get_db), context: RequestContext = Depends(get_request_context)):
    return _apply("start-break", body, db, context)


@router.post("/end-break", response_model=TimesheetCommandResponse)
def end_break(body: CommandRequest, db: Session = Depends(get_db), context: RequestContext = Depends(get_request_context)):
    return _apply("end-break", body, db, context)


@router.post("/finish-work", response_model=TimesheetCommandResponse)
def finish_work(body: CommandRequest, db: Session = Depends(get_db), context: RequestContext = Depends(get_request_context)):
    return _apply("finish-work", body, db, context)
