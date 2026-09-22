from sqlalchemy import Column, DateTime, Integer, JSON, String, UniqueConstraint
from app.core.database import Base
from app.core.time_utils import utc_now


class TimesheetCommand(Base):
    __tablename__ = "timesheet_commands"
    __table_args__ = (UniqueConstraint("account_id", "amocrm_user_id", "key", name="uq_timesheet_commands_scope_key"),)

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, nullable=False)
    amocrm_user_id = Column(Integer, nullable=False)
    key = Column(String(36), nullable=False)
    action = Column(String(30), nullable=False)
    response = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
