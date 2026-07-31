"""schemas/customer.py — Customer + RFM shapes (Phase 19)"""

from datetime import date

from pydantic import BaseModel, Field, model_validator


class CustomerCreate(BaseModel):
    """Manually add a customer. At least one identity field is required."""
    name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    total_spent: float = Field(default=0, ge=0, lt=10_000_000)
    purchase_count: int = Field(default=0, ge=0, lt=1_000_000)
    last_purchase_date: date | None = None
    sms_opt_in: bool = False
    email_opt_in: bool = False

    @model_validator(mode="after")
    def _need_identity(self):
        if not (self.name or self.email or self.phone):
            raise ValueError("Enter at least a name, email, or phone.")
        return self


class UploadResult(BaseModel):
    created: int
    updated: int
    total: int


class CustomerListItem(BaseModel):
    id: str
    name: str | None
    email: str | None
    phone: str | None
    total_spent: float
    purchase_count: int
    last_purchase_date: str | None
    first_purchase_date: str | None
    recency_days: int | None
    r_score: int
    f_score: int
    m_score: int
    segment: str
    recommendation: str
    sms_opt_in: bool
    email_opt_in: bool


class SegmentBucket(BaseModel):
    segment: str
    count: int
    total_spent: float
    recommendation: str


class SegmentSummary(BaseModel):
    total_customers: int
    total_value: float
    sms_opted_in: int
    email_opted_in: int
    segments: list[SegmentBucket]
