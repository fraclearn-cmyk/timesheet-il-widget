"""
Reports API
API endpoints для отчётов
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime

from app.core.database import get_db
from app.services.report_service import ReportService
from app.models.report import ReportType, ReportFormat
from app.schemas.report import (
    DailyReportRequest,
    WeeklyReportRequest,
    MonthlyReportRequest,
    DailySummary,
    WeeklySummary,
    MonthlySummary,
    EmployeeReport,
    PeriodStatistics,
    ReportResponse,
    ReportListResponse,
    ReportGenerateRequest
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/daily", response_model=DailySummary)
def get_daily_report(
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    date: date = Query(..., description="Дата отчёта"),
    user_id: Optional[int] = Query(None, description="ID пользователя (опционально)"),
    department: Optional[str] = Query(None, description="Отдел (опционально)"),
    db: Session = Depends(get_db)
):
    """
    Получить дневной отчёт
    
    - **account_id**: ID аккаунта
    - **date**: Дата (YYYY-MM-DD)
    - **user_id**: Фильтр по пользователю (опционально)
    - **department**: Фильтр по отделу (опционально)
    """
    return ReportService.get_daily_report(
        db=db,
        account_id=account_id,
        target_date=date,
        user_id=user_id,
        department=department
    )


@router.get("/weekly", response_model=WeeklySummary)
def get_weekly_report(
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    week_start: date = Query(..., description="Начало недели (понедельник)"),
    user_id: Optional[int] = Query(None, description="ID пользователя"),
    department: Optional[str] = Query(None, description="Отдел"),
    db: Session = Depends(get_db)
):
    """
    Получить недельный отчёт
    
    - **week_start**: Дата начала недели (желательно понедельник)
    """
    return ReportService.get_weekly_report(
        db=db,
        account_id=account_id,
        week_start=week_start,
        user_id=user_id,
        department=department
    )


@router.get("/monthly", response_model=MonthlySummary)
def get_monthly_report(
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    year: int = Query(..., description="Год"),
    month: int = Query(..., ge=1, le=12, description="Месяц (1-12)"),
    user_id: Optional[int] = Query(None, description="ID пользователя"),
    department: Optional[str] = Query(None, description="Отдел"),
    db: Session = Depends(get_db)
):
    """
    Получить месячный отчёт
    
    - **year**: Год (например, 2026)
    - **month**: Месяц (1-12)
    """
    return ReportService.get_monthly_report(
        db=db,
        account_id=account_id,
        year=year,
        month=month,
        user_id=user_id,
        department=department
    )


@router.get("/employee/{user_id}", response_model=EmployeeReport)
def get_employee_report(
    user_id: int,
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    start_date: date = Query(..., description="Начало периода"),
    end_date: date = Query(..., description="Конец периода"),
    db: Session = Depends(get_db)
):
    """
    Получить детальный отчёт по сотруднику
    
    - **user_id**: ID пользователя
    - **start_date**: Начало периода
    - **end_date**: Конец периода
    """
    report = ReportService.get_employee_report(
        db=db,
        account_id=account_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )
    
    if not report:
        raise HTTPException(status_code=404, detail="Данные не найдены")
    
    return report


@router.get("/statistics", response_model=PeriodStatistics)
def get_period_statistics(
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    start_date: date = Query(..., description="Начало периода"),
    end_date: date = Query(..., description="Конец периода"),
    department: Optional[str] = Query(None, description="Отдел"),
    db: Session = Depends(get_db)
):
    """
    Получить статистику за произвольный период
    
    - **start_date**: Начало периода
    - **end_date**: Конец периода
    - **department**: Фильтр по отделу (опционально)
    """
    return ReportService.get_period_statistics(
        db=db,
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        department=department
    )


@router.post("/generate", response_model=ReportResponse, status_code=201)
def generate_report(
    request: ReportGenerateRequest,
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    generated_by: int = Query(..., description="ID пользователя, создающего отчёт"),
    db: Session = Depends(get_db)
):
    """
    Сгенерировать и сохранить отчёт
    
    - Создаёт отчёт и сохраняет его в БД
    - Возвращает ID отчёта для последующего скачивания
    """
    # Generate report data based on type
    if request.report_type == ReportType.DAILY:
        data = ReportService.get_daily_report(
            db=db,
            account_id=account_id,
            target_date=request.start_date,
            user_id=request.user_id,
            department=request.department
        ).dict()
        title = f"Дневной отчёт {request.start_date}"
        
    elif request.report_type == ReportType.WEEKLY:
        data = ReportService.get_weekly_report(
            db=db,
            account_id=account_id,
            week_start=request.start_date,
            user_id=request.user_id,
            department=request.department
        ).dict()
        title = f"Недельный отчёт {request.start_date}"
        
    elif request.report_type == ReportType.MONTHLY:
        data = ReportService.get_monthly_report(
            db=db,
            account_id=account_id,
            year=request.start_date.year,
            month=request.start_date.month,
            user_id=request.user_id,
            department=request.department
        ).dict()
        title = f"Месячный отчёт {request.start_date.strftime('%B %Y')}"
        
    elif request.report_type == ReportType.EMPLOYEE:
        if not request.user_id:
            raise HTTPException(status_code=400, detail="user_id обязателен для employee report")
        data = ReportService.get_employee_report(
            db=db,
            account_id=account_id,
            user_id=request.user_id,
            start_date=request.start_date,
            end_date=request.end_date
        ).dict()
        title = f"Отчёт сотрудника {request.start_date} - {request.end_date}"
        
    else:  # CUSTOM
        data = ReportService.get_period_statistics(
            db=db,
            account_id=account_id,
            start_date=request.start_date,
            end_date=request.end_date,
            department=request.department
        ).dict()
        title = f"Отчёт {request.start_date} - {request.end_date}"
    
    # Create summary
    summary = {
        "report_type": request.report_type.value,
        "generated_at": datetime.now().isoformat(),
        "period": f"{request.start_date} - {request.end_date}"
    }
    
    # Save report
    report = ReportService.save_report(
        db=db,
        account_id=account_id,
        report_type=request.report_type,
        report_format=request.report_format,
        title=title,
        start_date=datetime.combine(request.start_date, datetime.min.time()),
        end_date=datetime.combine(request.end_date, datetime.max.time()),
        data=data,
        generated_by=generated_by,
        user_id=request.user_id,
        department=request.department,
        summary=summary
    )
    
    return report


@router.get("", response_model=ReportListResponse)
def get_reports_list(
    account_id: str = Query(..., description="ID аккаунта amoCRM"),
    skip: int = Query(0, ge=0, description="Пропустить записей"),
    limit: int = Query(100, ge=1, le=1000, description="Лимит записей"),
    report_type: Optional[ReportType] = Query(None, description="Фильтр по типу"),
    db: Session = Depends(get_db)
):
    """
    Получить список сохранённых отчётов
    
    - **skip**: Пагинация - пропустить записей
    - **limit**: Пагинация - лимит записей
    - **report_type**: Фильтр по типу отчёта
    """
    reports = ReportService.get_reports(
        db=db,
        account_id=account_id,
        skip=skip,
        limit=limit,
        report_type=report_type
    )
    
    # Count total (simple approach, can be optimized)
    total = len(ReportService.get_reports(db=db, account_id=account_id, skip=0, limit=10000))
    
    return ReportListResponse(
        total=total,
        reports=reports
    )


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: int,
    db: Session = Depends(get_db)
):
    """
    Получить отчёт по ID
    """
    report = ReportService.get_report_by_id(db=db, report_id=report_id)
    
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    
    return report


@router.delete("/{report_id}", status_code=204)
def delete_report(
    report_id: int,
    db: Session = Depends(get_db)
):
    """
    Удалить отчёт
    """
    success = ReportService.delete_report(db=db, report_id=report_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    
    return None


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    format: ReportFormat = Query(ReportFormat.EXCEL, description="Формат скачивания"),
    db: Session = Depends(get_db)
):
    """
    Скачать отчёт в выбранном формате
    
    - **format**: Формат (excel, pdf, csv)
    
    TODO: Реализовать Excel/PDF export
    """
    report = ReportService.get_report_by_id(db=db, report_id=report_id)
    
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    
    # TODO: Implement Excel/PDF generation
    raise HTTPException(status_code=501, detail="Excel/PDF export в разработке")
