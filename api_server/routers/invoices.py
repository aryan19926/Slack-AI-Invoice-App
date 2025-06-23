from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional, List
from datetime import date
from ..models import Invoice, InvoiceStatusUpdate, InvoiceSummary, APIResponse, InvoiceStatus, InvoiceType
from ..database import DatabaseClient
from ..auth import get_user_from_request

router = APIRouter(
    prefix="/api/invoices",
    tags=["invoices"]
)
db = DatabaseClient()

@router.get("/summary", response_model=InvoiceSummary)
async def get_invoices_summary(
    status: Optional[InvoiceStatus] = Query(None, description="Filter by status"),
    due_date_before: Optional[date] = Query(None, description="Filter by due date before this date"),
    customer_name: Optional[str] = Query(None, description="Filter by customer name (partial match)"),
    created_by_user_id: Optional[str] = Query(None, description="Filter by creator user ID"),
    invoice_type: Optional[InvoiceType] = Query(None, description="Filter by invoice type (RECEIVABLE/PAYABLE)")
):
    try:
        validated_user = get_user_from_request(created_by_user_id)
        summary = db.get_invoices_summary(
            status=status,
            due_date_before=due_date_before,
            customer_name=customer_name,
            created_by_user_id=validated_user,
            invoice_type=invoice_type
        )
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting invoice summary: {str(e)}"
        )

@router.get("/search", response_model=List[Invoice])
async def search_invoices(
    customer_name: Optional[str] = Query(None, description="Search by customer name"),
    status: Optional[InvoiceStatus] = Query(None, description="Filter by status"),
    created_by_user_id: Optional[str] = Query(None, description="Filter by creator"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results")
):
    try:
        validated_user = get_user_from_request(created_by_user_id)
        invoices = db.search_invoices(
            customer_name=customer_name,
            status=status,
            created_by_user_id=validated_user,
            limit=limit
        )
        return invoices
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error searching invoices: {str(e)}"
        )

@router.get("/{invoice_id}", response_model=Invoice)
async def get_invoice(
    invoice_id: str = Path(..., description="Invoice ID (e.g., INV-2024-001)"),
    user_id: Optional[str] = Query(None, description="Slack user ID for filtering")
):
    try:
        validated_user = get_user_from_request(user_id)
        invoice = db.get_invoice_by_id(invoice_id, validated_user)
        if not invoice:
            raise HTTPException(
                status_code=404, 
                detail=f"Invoice {invoice_id} not found"
            )
        return invoice
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving invoice: {str(e)}"
        )

@router.put("/{invoice_id}/status", response_model=APIResponse)
async def update_invoice_status(
    invoice_id: str = Path(..., description="Invoice ID to update"),
    status_update: InvoiceStatusUpdate = ...,
    user_id: Optional[str] = Query(None, description="Slack user ID for filtering")
):
    try:
        validated_user = get_user_from_request(user_id)
        existing_invoice = db.get_invoice_by_id(invoice_id, validated_user)
        if not existing_invoice:
            raise HTTPException(
                status_code=404,
                detail=f"Invoice {invoice_id} not found"
            )
        success = db.update_invoice_status(invoice_id, status_update.status, validated_user)
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to update invoice {invoice_id} status"
            )
        return APIResponse(
            success=True,
            message=f"Invoice {invoice_id} status updated to {status_update.status.value}",
            data={"invoice_id": invoice_id, "new_status": status_update.status.value}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating invoice status: {str(e)}"
        )


