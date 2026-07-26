from pydantic import BaseModel, Field


class DutySummary(BaseModel):
    duty_date: str
    shift_name: str
    persons: list[str]


class NextDutySummary(BaseModel):
    duty_date: str
    shift_name: str


class PersonalDashboard(BaseModel):
    today_duties: list[DutySummary]
    next_duty: NextDutySummary | None = None
    pending_swap_confirm_count: int = 0
    pending_cover_confirm_count: int = 0


class ManagementDashboard(BaseModel):
    pending_approval_count: int | None = None
    pending_cover_arrangement_count: int | None = None
    schedule_status: str | None = None
    system_status: list[str] = Field(default_factory=list)


class DashboardReminder(BaseModel):
    type: str
    title: str
    count: int = 0
    path: str | None = None


class DashboardResponse(BaseModel):
    personal: PersonalDashboard
    management: ManagementDashboard | None = None
    reminders: list[DashboardReminder] = Field(default_factory=list)
