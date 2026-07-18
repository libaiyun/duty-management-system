from calendar import monthrange
from datetime import date
from pathlib import Path
from uuid import uuid4

import xlsxwriter
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.export import ExportTask
from app.models.schedule import MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson


def create_schedule_export(
    db: Session,
    task: ExportTask,
    schedule: MonthlySchedule,
    year: int,
    month: int,
    export_dir: Path,
) -> ExportTask:
    """Create one monthly duty-table XLSX and persist the task outcome."""
    task.status = "running"
    db.flush()
    try:
        days = db.scalars(
            select(ScheduleDay)
            .where(ScheduleDay.schedule_id == schedule.id)
            .where(ScheduleDay.duty_date >= date(year, month, 1))
            .where(ScheduleDay.duty_date <= date(year, month, monthrange(year, month)[1]))
            .options(
                selectinload(ScheduleDay.shifts).selectinload(ScheduleShift.shift_def),
                selectinload(ScheduleDay.shifts)
                .selectinload(ScheduleShift.persons)
                .selectinload(ScheduleShiftPerson.person),
            )
            .order_by(ScheduleDay.duty_date)
        ).all()
        if not days:
            raise ValueError("该月份暂无排班数据")

        shift_defs: dict[int, str] = {}
        for day in days:
            for shift in day.shifts:
                shift_defs.setdefault(shift.shift_def_id, shift.shift_def.name)
        export_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"值班表_{year:04d}{month:02d}_{uuid4().hex[:8]}.xlsx"
        file_path = export_dir / file_name
        workbook = xlsxwriter.Workbook(file_path)
        worksheet = workbook.add_worksheet("值班表")
        header_format = workbook.add_format({"bold": True, "align": "center", "bg_color": "#D9EAF7", "border": 1})
        cell_format = workbook.add_format({"border": 1, "valign": "vcenter"})
        headers = ["日期", "星期", *shift_defs.values()]
        for column, header in enumerate(headers):
            worksheet.write(0, column, header, header_format)
            worksheet.set_column(column, column, 14 if column < 2 else 22)
        weekdays = ["一", "二", "三", "四", "五", "六", "日"]
        for row, day in enumerate(days, start=1):
            worksheet.write(row, 0, day.duty_date.isoformat(), cell_format)
            worksheet.write(row, 1, f"星期{weekdays[day.weekday]}", cell_format)
            people_by_shift = {
                shift.shift_def_id: "、".join(person.person.name for person in shift.persons) for shift in day.shifts
            }
            for column, shift_def_id in enumerate(shift_defs, start=2):
                worksheet.write(row, column, people_by_shift.get(shift_def_id, ""), cell_format)
        workbook.close()
        task.status = "completed"
        task.file_name = file_name
        task.file_path = file_name
        task.error_message = None
    except Exception as exc:
        task.status = "failed"
        task.error_message = str(exc)
    db.flush()
    return task
