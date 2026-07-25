"""schemas/customer.py — Customer + RFM shapes (Phase 19)"""

from pydantic import BaseModel


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
