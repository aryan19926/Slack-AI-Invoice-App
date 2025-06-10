from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from enum import Enum

class InvoiceStatus(str, Enum):
    DRAFT = "Draft"
    SENT = "Sent"
    PAID = "Paid"
    OVERDUE = "Overdue"
    CANCELLED = "Cancelled"

class InvoiceType(str, Enum):
    RECEIVABLE = "RECEIVABLE"
    PAYABLE = "PAYABLE"

class LineItem(BaseModel):
    description: str
    quantity: int
    unit_price: float

class Invoice(BaseModel):
    id: int
    invoice_id: str
    customer_name: str
    amount: float
    currency: str
    status: InvoiceStatus
    company_id: Optional[str] = None
    type: InvoiceType
    issue_date: date
    due_date: date
    line_items: List[LineItem]
    notes: Optional[str] = None
    created_by_user_id: Optional[str] = None
    last_updated: datetime

class InvoiceStatusUpdate(BaseModel):
    status: InvoiceStatus

class InvoiceSummaryQuery(BaseModel):
    status: Optional[InvoiceStatus] = None
    due_date_before: Optional[date] = None
    customer_name: Optional[str] = None
    created_by_user_id: Optional[str] = None
    type: Optional[InvoiceType] = None

class InvoiceSummary(BaseModel):
    total_outstanding: float
    overdue_count: int
    due_this_month: List[Dict[str, Any]]
    total_invoices: int
    paid_this_month: float
    draft_count: int

class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[str] = None