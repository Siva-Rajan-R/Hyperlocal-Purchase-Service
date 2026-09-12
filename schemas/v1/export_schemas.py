from pydantic import BaseModel, Field
from typing import Optional, Literal

class ExportDataRequestSchema(BaseModel):
    shop_id: str
    from_record: Optional[int] = Field(default=1, ge=1, description="Starting record index (1-indexed)")
    to_record: Optional[int] = Field(default=100, ge=1, description="Ending record index (1-indexed)")
    format: Optional[Literal["csv", "xlsx"]] = Field(default="csv", description="File format: csv or xlsx")
    query: Optional[str] = Field(default=None, description="Search term filter")
    from_date: Optional[str] = Field(default=None, description="Start date (YYYY-MM-DD)")
    to_date: Optional[str] = Field(default=None, description="End date (YYYY-MM-DD)")
    user_id: Optional[str] = Field(default=None, description="Requesting User ID for notification")
    status: Optional[str] = Field(default=None, description="Status filter")
    supplier_id: Optional[str] = Field(default=None, description="Supplier filter")
    exclude_cancle: Optional[bool] = Field(default=None, description="Exclude canceled purchases")
    exclude_cancel: Optional[bool] = Field(default=None, description="Exclude canceled purchases")
    exclude_canceled: Optional[bool] = Field(default=None, description="Exclude canceled purchases")
    exclude_cancelled: Optional[bool] = Field(default=None, description="Exclude canceled purchases")
    exclude_draft: Optional[bool] = Field(default=None, description="Exclude draft purchases")
    exclude_drafts: Optional[bool] = Field(default=None, description="Exclude draft purchases")
    exclude_not_paid: Optional[bool] = Field(default=None, description="Exclude unpaid purchases")
    exclude_unpaid: Optional[bool] = Field(default=None, description="Exclude unpaid purchases")
    exclude_paid: Optional[bool] = Field(default=None, description="Exclude paid purchases")
    exclude_completed_payment: Optional[bool] = Field(default=None, description="Exclude paid purchases")
    exclude_partial_paid: Optional[bool] = Field(default=None, description="Exclude partial paid purchases")
    exclude_partially_paid: Optional[bool] = Field(default=None, description="Exclude partial paid purchases")
    exclude_outstanding: Optional[bool] = Field(default=None, description="Exclude purchases with outstanding amount")
    exclude_outstading: Optional[bool] = Field(default=None, description="Exclude purchases with outstanding amount")
    exclude_non_outstanding: Optional[bool] = Field(default=None, description="Exclude purchases without outstanding amount")
    exclude_non_outstating: Optional[bool] = Field(default=None, description="Exclude purchases without outstanding amount")
    exclude_return: Optional[bool] = Field(default=None, description="Exclude purchases with returns")
    exclude_returns: Optional[bool] = Field(default=None, description="Exclude purchases with returns")
    exclude_non_return: Optional[bool] = Field(default=None, description="Exclude purchases without returns")
    exclude_non_returns: Optional[bool] = Field(default=None, description="Exclude purchases without returns")

class ExportJobResponseSchema(BaseModel):
    job_id: str
    entity: str
    status: str = "QUEUED"
    message: str = "Export task scheduled successfully in the background"

class ExportStatusResponseSchema(BaseModel):
    job_id: str
    entity: str
    status: str  # QUEUED, IN_PROGRESS, COMPLETED, FAILED
    download_url: Optional[str] = None
    file_name: Optional[str] = None
    total_records: Optional[int] = 0
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
