"""Allowlisted XLSX rendering for detailed timesheet rows."""

from __future__ import annotations

from datetime import date, datetime, timezone
from io import BytesIO
import re
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from app.schemas.report import DetailedReportRow, TimesheetColumn


HEADERS = {
    TimesheetColumn.EMPLOYEE: "Сотрудник",
    TimesheetColumn.DATE: "Дата",
    TimesheetColumn.START: "Начало",
    TimesheetColumn.END: "Окончание",
    TimesheetColumn.BREAK: "Перерыв",
    TimesheetColumn.WORK: "Работа",
    TimesheetColumn.SHIFT_LATENESS: "Минуты",
    TimesheetColumn.SHIFT_LATE_REASON: "Объяснительная",
    TimesheetColumn.BREAK_LATENESS: "Минуты",
    TimesheetColumn.BREAK_LATE_REASON: "Объяснительная",
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
LATENESS_GROUPS = {
    TimesheetColumn.SHIFT_LATENESS: "Начало дня",
    TimesheetColumn.SHIFT_LATE_REASON: "Начало дня",
    TimesheetColumn.BREAK_LATENESS: "Перерыв",
    TimesheetColumn.BREAK_LATE_REASON: "Перерыв",
}
REASON_COLUMNS = {TimesheetColumn.SHIFT_LATE_REASON, TimesheetColumn.BREAK_LATE_REASON}
MINUTE_COLUMNS = {TimesheetColumn.SHIFT_LATENESS, TimesheetColumn.BREAK_LATENESS}
# XML 1.0 excludes these controls, surrogate code points and terminal noncharacters.
# Keep supported tabs, newlines and carriage returns; visibly mark every replacement.
INVALID_XML_TEXT = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
EXCEL_CELL_TEXT_LIMIT = 32767
OVERFLOW_SHEET = "Объяснительные"
OVERFLOW_MARKER = "Полный список — на листе «Объяснительные»."


def _header(sheet, columns: list[TimesheetColumn]) -> int:
    if not any(column in LATENESS_GROUPS for column in columns):
        sheet.append([HEADERS[column] for column in columns])
        return 1
    for index, column in enumerate(columns, 1):
        if column not in LATENESS_GROUPS:
            sheet.cell(1, index, HEADERS[column])
            sheet.merge_cells(
                start_row=1, end_row=3, start_column=index, end_column=index
            )
        else:
            sheet.cell(3, index, HEADERS[column])
    # Arbitrary selections keep their requested order; merge only contiguous groups.
    for level in (1, 2):
        start = 1
        while start <= len(columns):
            column = columns[start - 1]
            if column not in LATENESS_GROUPS:
                start += 1
                continue
            label = "Опоздания" if level == 1 else LATENESS_GROUPS[column]
            end = start
            while (
                end < len(columns)
                and columns[end] in LATENESS_GROUPS
                and (level == 1 or LATENESS_GROUPS[columns[end]] == label)
            ):
                end += 1
            sheet.cell(level, start, label)
            if end > start:
                sheet.merge_cells(
                    start_row=level, end_row=level, start_column=start, end_column=end
                )
            start = end + 1
    return 3


def _excel_text_length(value: str) -> int:
    # Excel counts UTF-16 units, including two for each supplementary character.
    return len(value.encode("utf-16-le")) // 2


def _break_reasons(row: DetailedReportRow) -> tuple[str, bool]:
    lines = []
    for incident in row.break_late_reason:
        label = (
            f"Перерыв №{incident.sequence} — {(incident.late_seconds + 59) // 60} мин"
        )
        lines.append(
            _safe_text(f"{label}: {incident.reason}" if incident.reason else label)
        )
    text = "\n".join(lines)
    if _excel_text_length(text) <= EXCEL_CELL_TEXT_LIMIT:
        return text, False
    length = _excel_text_length(OVERFLOW_MARKER)
    complete = []
    for line in lines:
        size = _excel_text_length(line) + 1  # separator before the marker/next line
        if length + size > EXCEL_CELL_TEXT_LIMIT:
            break
        complete.append(line)
        length += size
    return "\n".join([*complete, OVERFLOW_MARKER]), True


def _write_overflow_sheet(book: Workbook, rows: list[DetailedReportRow]) -> None:
    sheet = book.create_sheet(OVERFLOW_SHEET)
    sheet.append(["Сотрудник", "Дата", "Перерыв №", "Минуты", "Объяснительная"])
    for row in rows:
        for incident in row.break_late_reason:
            sheet.append(
                [
                    _safe_text(row.employee_name),
                    row.date,
                    incident.sequence,
                    (incident.late_seconds + 59) // 60,
                    _safe_text(incident.reason or ""),
                ]
            )
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for cells in sheet.iter_rows(min_row=2):
        cells[1].number_format = DATE_FORMAT
        cells[2].number_format = cells[3].number_format = "0"
        cells[4].alignment = Alignment(wrap_text=True, vertical="top")
    for index in range(1, 6):
        sheet.column_dimensions[get_column_letter(index)].width = (
            45 if index == 5 else 20
        )
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:E{sheet.max_row}"


def safe_report_filename(date_from: date, date_to: date) -> str:
    return f"timesheet_{date_from.isoformat()}_{date_to.isoformat()}.xlsx"


def _safe_text(value: str) -> str:
    value = INVALID_XML_TEXT.sub("\ufffd", value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def _local_datetime(value: datetime | None, group_timezone: str) -> datetime | None:
    if value is None:
        return None
    utc_value = (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )
    return utc_value.astimezone(ZoneInfo(group_timezone)).replace(tzinfo=None)


class TimesheetExcelService:
    def render(
        self, rows: list[DetailedReportRow], columns: list[TimesheetColumn]
    ) -> bytes:
        book = Workbook()
        sheet = book.active
        sheet.title = "Табель"
        header_rows = _header(sheet, columns)
        overflow_rows = []
        for row in rows:
            break_reasons = ""
            if TimesheetColumn.BREAK_LATE_REASON in columns:
                break_reasons, overflow = _break_reasons(row)
                if overflow:
                    overflow_rows.append(row)
            values = {
                TimesheetColumn.EMPLOYEE: _safe_text(row.employee_name),
                TimesheetColumn.DATE: row.date,
                TimesheetColumn.START: _local_datetime(
                    row.started_at, row.group_timezone
                ),
                TimesheetColumn.END: _local_datetime(row.ended_at, row.group_timezone),
                TimesheetColumn.BREAK: row.break_seconds / 86400,
                TimesheetColumn.WORK: row.work_seconds / 86400,
                TimesheetColumn.SHIFT_LATENESS: (row.shift_late_seconds + 59) // 60,
                TimesheetColumn.SHIFT_LATE_REASON: _safe_text(
                    row.shift_late_reason or ""
                ),
                TimesheetColumn.BREAK_LATENESS: (row.break_late_seconds + 59) // 60,
                TimesheetColumn.BREAK_LATE_REASON: break_reasons,
                TimesheetColumn.STATUS: STATUS_LABELS[row.status],
            }
            sheet.append([values[column] for column in columns])
        for cells in sheet.iter_rows(max_row=header_rows):
            for cell in cells:
                cell.alignment = Alignment(
                    horizontal="center", vertical="center", wrap_text=True
                )
                cell.font = Font(bold=True)
        for column_index, column in enumerate(columns, start=1):
            number_format = None
            if column == TimesheetColumn.DATE:
                number_format = DATE_FORMAT
            elif column in (TimesheetColumn.START, TimesheetColumn.END):
                number_format = DATETIME_FORMAT
            elif column in (
                TimesheetColumn.BREAK,
                TimesheetColumn.WORK,
            ):
                number_format = DURATION_FORMAT
            elif column in MINUTE_COLUMNS:
                number_format = "0"
            if number_format is not None:
                for cells in sheet.iter_cols(
                    min_col=column_index, max_col=column_index, min_row=header_rows + 1
                ):
                    for cell in cells:
                        cell.number_format = number_format
            if column in REASON_COLUMNS:
                for cells in sheet.iter_cols(
                    min_col=column_index, max_col=column_index, min_row=header_rows + 1
                ):
                    for cell in cells:
                        cell.alignment = Alignment(wrap_text=True, vertical="top")
            sheet.column_dimensions[get_column_letter(column_index)].width = (
                45 if column in REASON_COLUMNS else 20
            )
        sheet.freeze_panes = f"A{header_rows + 1}"
        sheet.auto_filter.ref = (
            f"A{header_rows}:{get_column_letter(len(columns))}{sheet.max_row}"
        )
        if overflow_rows:
            _write_overflow_sheet(book, overflow_rows)
        output = BytesIO()
        book.save(output)
        return output.getvalue()
