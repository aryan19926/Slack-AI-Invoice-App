import os
from supabase import create_client, Client
from typing import List, Optional, Dict, Any
from datetime import date, datetime
import json
from .models import Invoice, InvoiceStatus, InvoiceType, LineItem, InvoiceSummary

class DatabaseClient:
    def __init__(self):
        url: str = os.getenv("SUPABASE_URL")
        key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.supabase: Client = create_client(url, key)
    
    def get_invoice_by_id(self, invoice_id: str, user_id: Optional[str] = None) -> Optional[Invoice]:
        """Get a single invoice by invoice_id"""
        try:
            query = self.supabase.table("invoices").select("*").eq("invoice_id", invoice_id)
            
            # Optional: Filter by user if provided
            if user_id:
                query = query.eq("created_by_user_id", user_id)
            
            result = query.execute()
            
            if result.data and len(result.data) > 0:
                invoice_data = result.data[0]
                return self._convert_to_invoice(invoice_data)
            return None
        except Exception as e:
            print(f"Error fetching invoice {invoice_id}: {e}")
            return None
    
    def update_invoice_status(self, invoice_id: str, status: InvoiceStatus, user_id: Optional[str] = None) -> bool:
        """Update invoice status"""
        try:
            query = self.supabase.table("invoices").update({"status": status.value}).eq("invoice_id", invoice_id)
            
            # Optional: Filter by user if provided
            if user_id:
                query = query.eq("created_by_user_id", user_id)
            
            result = query.execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"Error updating invoice {invoice_id}: {e}")
            return False
    
    def get_invoices_summary(self, 
                           status: Optional[InvoiceStatus] = None,
                           due_date_before: Optional[date] = None,
                           customer_name: Optional[str] = None,
                           created_by_user_id: Optional[str] = None,
                           invoice_type: Optional[InvoiceType] = None) -> InvoiceSummary:
        """Get invoice summary with filtering"""
        try:
            # Base query
            query = self.supabase.table("invoices").select("*")
            
            # Apply filters
            if status:
                query = query.eq("status", status.value)
            if due_date_before:
                query = query.lte("due_date", due_date_before.isoformat())
            if customer_name:
                query = query.ilike("customer_name", f"%{customer_name}%")
            if created_by_user_id:
                query = query.eq("created_by_user_id", created_by_user_id)
            if invoice_type:
                query = query.eq("type", invoice_type.value)
            
            result = query.execute()
            invoices = result.data
            
            # Calculate summary statistics
            total_outstanding = 0
            overdue_count = 0
            due_this_month = []
            paid_this_month = 0
            draft_count = 0
            
            today = datetime.now().date()
            current_month_start = today.replace(day=1)
            
            for invoice in invoices:
                amount = float(invoice['amount'])
                status_val = invoice['status']
                due_date = datetime.fromisoformat(invoice['due_date']).date()
                
                # Count draft invoices
                if status_val == 'Draft':
                    draft_count += 1
                
                # Count overdue invoices
                if status_val == 'Overdue':
                    overdue_count += 1
                
                # Calculate outstanding (not paid or cancelled)
                if status_val not in ['Paid', 'Cancelled']:
                    total_outstanding += amount
                
                # Track paid this month
                if status_val == 'Paid' and due_date >= current_month_start:
                    paid_this_month += amount
                
                # Track due this month
                if due_date.month == today.month and due_date.year == today.year:
                    due_this_month.append({
                        "invoice_id": invoice['invoice_id'],
                        "customer_name": invoice['customer_name'],
                        "amount": amount,
                        "due_date": due_date.isoformat(),
                        "status": status_val
                    })
            
            return InvoiceSummary(
                total_outstanding=total_outstanding,
                overdue_count=overdue_count,
                due_this_month=due_this_month,
                total_invoices=len(invoices),
                paid_this_month=paid_this_month,
                draft_count=draft_count
            )
        
        except Exception as e:
            print(f"Error getting invoice summary: {e}")
            return InvoiceSummary(
                total_outstanding=0,
                overdue_count=0,
                due_this_month=[],
                total_invoices=0,
                paid_this_month=0,
                draft_count=0
            )
    
    def search_invoices(self, 
                       customer_name: Optional[str] = None,
                       status: Optional[InvoiceStatus] = None,
                       created_by_user_id: Optional[str] = None,
                       limit: int = 10) -> List[Invoice]:
        """Search invoices with various filters"""
        try:
            query = self.supabase.table("invoices").select("*")
            
            if customer_name:
                query = query.ilike("customer_name", f"%{customer_name}%")
            if status:
                query = query.eq("status", status.value)
            if created_by_user_id:
                query = query.eq("created_by_user_id", created_by_user_id)
            
            query = query.limit(limit).order("last_updated", desc=True)
            result = query.execute()
            
            return [self._convert_to_invoice(invoice_data) for invoice_data in result.data]
        
        except Exception as e:
            print(f"Error searching invoices: {e}")
            return []
    
    def _convert_to_invoice(self, invoice_data: Dict[str, Any]) -> Invoice:
        """Convert database row to Invoice model"""
        # Parse line_items JSON
        line_items = []
        if invoice_data.get('line_items'):
            try:
                line_items_data = invoice_data['line_items']
                if isinstance(line_items_data, str):
                    line_items_data = json.loads(line_items_data)
                line_items = [LineItem(**item) for item in line_items_data]
            except Exception as e:
                print(f"Error parsing line_items: {e}")
                line_items = []
        
        return Invoice(
            id=invoice_data['id'],
            invoice_id=invoice_data['invoice_id'],
            customer_name=invoice_data['customer_name'],
            amount=float(invoice_data['amount']),
            currency=invoice_data['currency'],
            status=InvoiceStatus(invoice_data['status']),
            company_id=invoice_data.get('company_id'),
            type=InvoiceType(invoice_data['type']),
            issue_date=datetime.fromisoformat(invoice_data['issue_date']).date(),
            due_date=datetime.fromisoformat(invoice_data['due_date']).date(),
            line_items=line_items,
            notes=invoice_data.get('notes'),
            created_by_user_id=invoice_data.get('created_by_user_id'),
            last_updated=datetime.fromisoformat(invoice_data['last_updated'].replace('Z', '+00:00'))
        )