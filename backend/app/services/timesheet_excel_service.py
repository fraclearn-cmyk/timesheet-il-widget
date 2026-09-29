"""Allowlisted XLSX rendering for detailed timesheet rows."""

from __future__ import annotations

from datetime import date, datetime, timezone
from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from app.schemas.report import DetailedReportRow, TimesheetColumn


HEADERS = {
    TimesheetColumn.EMPLOYEE: "Сотрудник",
    TimesheetColumn.DATE: "Дата",
    TimesheetColumn.START: "Начало",
    TimesheetColumn.END: "Окончание",
    TimesheetColumn.BREAK: "Перерыв",
    TimesheetColumn.WORK: "Работа",
    TimesheetColumn.LATENESS: "Опоздание",
    TimesheetColumn.STATUS: "Статус",
}
STATUS_LABELS = {
    "working": "Работает",
    "on_break": "Перерыв",
    "finished": "Закончил(а)",
}
DATETIME_FORMAT = "dd.mm.yyyy hh:mm"
DATE_FORMAT = "dd.mm.yyyy"
DURATION_FORMAT = "[h]:mm"


def safe_report_filename(date_from: date, date_to: date) -> str:
    return f"timesheet_{date_from.isoformat()}_{date_to.isoformat()}.xlsx"


def _safe_text(value: str) -> str:
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def _local_datetime(value: datetime | None, group_timezone: str) -> datetime | None:
    if value is None:
        return None
    utc_value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return utc_value.astimezone(ZoneInfo(group_timezone)).replace(tzinfo=None)


class TimesheetExcelService:
    def render(self, rows: list[DetailedReportRow], columns: list[TimesheetColumn]) -> bytes:
        book = Workbook()
        sheet = book.active
        sheet.title = "Табель"
        sheet.append([HEADERS[column] for column in columns])
        for row in rows:
            values = {
                TimesheetColumn.EMPLOYEE: _safe_text(row.employee_name),
                TimesheetColumn.DATE: row.date,
                TimesheetColumn.START: _local_datetime(row.started_at, row.group_timezone),
                TimesheetColumn.END: _local_datetime(row.ended_at, row.group_timezone),
                TimesheetColumn.BREAK: row.break_seconds / 86400,
                TimesheetColumn.WORK: row.work_seconds / 86400,
                TimesheetColumn.LATENESS: row.late_seconds / 86400,
                TimesheetColumn.STATUS: STATUS_LABELS[row.status],
            }
            sheet.append([values[column] for column in columns])
        for column_index, column in enumerate(columns, start=1):
            number_format = None
            if column == TimesheetColumn.DATE:
                number_format = DATE_FORMAT
            elif column in (TimesheetColumn.START, TimesheetColumn.END):
                number_format = DATETIME_FORMAT
            elif column in (TimesheetColumn.BREAK, TimesheetColumn.WORK, TimesheetColumn.LATENESS):
                number_format = DURATION_FORMAT
            if number_format is not None:
                for cells in sheet.iter_cols(min_col=column_index, max_col=column_index, min_row=2):
                    for cell in cells:
                        cell.number_format = number_format
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{sheet.max_row}"
        output = BytesIO()
        book.save(output)
        return output.getvalue()
