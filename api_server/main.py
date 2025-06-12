from fastapi import FastAPI, HTTPException, Depends, Query, Path, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import date
import os
from dotenv import load_dotenv
from fastapi.responses import JSONResponse

from .models import (
    Invoice, InvoiceStatusUpdate, InvoiceSummary, 
    APIResponse, ErrorResponse, InvoiceStatus, InvoiceType
)
from .database import DatabaseClient
from .auth import get_user_from_request, verify_slack_auth

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Invoice AI API",
    description="Internal API for invoice management with AI integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change during prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database client
db = DatabaseClient()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Invoice AI API is running", "status": "healthy"}

@app.get("/api/invoices/summary", response_model=InvoiceSummary)
async def get_invoices_summary(
    status: Optional[InvoiceStatus] = Query(None, description="Filter by status"),
    due_date_before: Optional[date] = Query(None, description="Filter by due date before this date"),
    customer_name: Optional[str] = Query(None, description="Filter by customer name (partial match)"),
    created_by_user_id: Optional[str] = Query(None, description="Filter by creator user ID"),
    invoice_type: Optional[InvoiceType] = Query(None, description="Filter by invoice type (RECEIVABLE/PAYABLE)"),
    auth: bool = Depends(verify_slack_auth)
):
    """
    Get a summary of invoices based on various filters.
    
    Returns statistics including:
    - Total outstanding amount
    - Number of overdue invoices
    - Invoices due this month
    - Total invoice count
    - Amount paid this month
    - Number of draft invoices
    """
    try:
        # Validate user if provided
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

@app.get("/api/invoices/search", response_model=List[Invoice])
async def search_invoices(
    customer_name: Optional[str] = Query(None, description="Search by customer name"),
    status: Optional[InvoiceStatus] = Query(None, description="Filter by status"),
    created_by_user_id: Optional[str] = Query(None, description="Filter by creator"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    auth: bool = Depends(verify_slack_auth)
):
    """
    Search invoices with various filters.
    
    - **customer_name**: Partial match on customer name
    - **status**: Filter by invoice status
    - **created_by_user_id**: Filter by creator user ID
    - **limit**: Maximum number of results (1-50)
    """
    try:
        # Validate user if provided
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

@app.get("/api/invoices/{invoice_id}", response_model=Invoice)
async def get_invoice(
    invoice_id: str = Path(..., description="Invoice ID (e.g., INV-2024-001)"),
    user_id: Optional[str] = Query(None, description="Slack user ID for filtering"),
    auth: bool = Depends(verify_slack_auth)
):
    """
    Retrieve detailed information for a specific invoice.
    
    - **invoice_id**: The invoice identifier (e.g., INV-2024-001)
    - **user_id**: Optional Slack user ID to filter by user's invoices only
    """
    try:
        # Validate and get user
        validated_user = get_user_from_request(user_id)
        
        # Get invoice from database
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

@app.put("/api/invoices/{invoice_id}/status", response_model=APIResponse)
async def update_invoice_status(
    invoice_id: str = Path(..., description="Invoice ID to update"),
    status_update: InvoiceStatusUpdate = ...,
    user_id: Optional[str] = Query(None, description="Slack user ID for filtering"),
    auth: bool = Depends(verify_slack_auth)
):
    """
    Update the status of an invoice.
    
    - **invoice_id**: The invoice identifier to update
    - **status**: New status (Draft, Sent, Paid, Overdue, Cancelled)
    - **user_id**: Optional Slack user ID to filter by user's invoices only
    """
    try:
        # Validate and get user
        validated_user = get_user_from_request(user_id)
        
        # First check if invoice exists
        existing_invoice = db.get_invoice_by_id(invoice_id, validated_user)
        if not existing_invoice:
            raise HTTPException(
                status_code=404,
                detail=f"Invoice {invoice_id} not found"
            )
        
        # Update status
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

@app.get("/api/health")
async def health_check(auth: bool = Depends(verify_slack_auth)):
    """Detailed health check with database connectivity"""
    try:
        # Test database connection
        test_summary = db.get_invoices_summary()
        
        return {
            "status": "healthy",
            "database": "connected",
            "total_invoices": test_summary.total_invoices,
            "timestamp": date.today().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service unavailable: {str(e)}"
        )

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            success=False,
            error=exc.detail,
            details=f"Status Code: {exc.status_code}"
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            success=False,
            error="Internal server error",
            details=str(exc)
        ).dict()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )