"""Excel export functionality for transactions and review data."""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows
from datetime import datetime

try:
    from .review import ReviewItem
except ImportError:
    from review import ReviewItem

logger = logging.getLogger(__name__)


class ExcelExporter:
    """Export transaction data and review items to Excel."""
    
    def __init__(self, output_path: Path):
        """
        Initialize Excel exporter.
        
        Args:
            output_path: Path for the output Excel file
        """
        self.output_path = output_path
        self.workbook = Workbook()
        
    def export_transactions(self, 
                          transactions: List[Dict[str, Any]], 
                          review_items: List[ReviewItem],
                          include_summary: bool = False):
        """
        Export transactions and review data to a single consolidated Excel sheet.
        
        Args:
            transactions: List of transaction dictionaries
            review_items: List of items needing review
            include_summary: Whether to include summary section (always True now)
        """
        try:
            # Remove default sheet
            if "Sheet" in self.workbook.sheetnames:
                self.workbook.remove(self.workbook["Sheet"])
            
            # Create single consolidated sheet
            self._create_consolidated_sheet(transactions, review_items, include_summary)
            
            # Save workbook
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.workbook.save(str(self.output_path))
            
            logger.info(f"Excel file exported to: {self.output_path}")
            
        except Exception as e:
            logger.error(f"Failed to export Excel file: {e}")
            raise
    
    def _create_consolidated_sheet(self, transactions: List[Dict[str, Any]], review_items: List[ReviewItem], include_summary: bool = True):
        """Create a single consolidated sheet with transactions, review items, and summary."""
        ws = self.workbook.create_sheet("All Transactions")
        
        current_row = 1
        
        # Add summary section first if requested
        if include_summary:
            current_row = self._add_summary_section(ws, transactions, current_row)
            current_row += 2  # Add spacing
        
        # Create review lookup for merging data
        review_lookup = {Path(item.file_path).name: item for item in review_items}
        
        # Define headers for consolidated view
        headers = ["File Name", "Date", "Amount", "Category", "Description", 
                  "Review Status", "Review Reason", "Raw Snippet"]
        
        # Add section title
        ws.cell(row=current_row, column=1, value="ALL TRANSACTIONS").font = Font(bold=True, size=14)
        current_row += 2
        
        # Add headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=current_row, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="E6E6E6", end_color="E6E6E6", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        
        current_row += 1
        
        # Sort transactions: OK first, then REVIEW
        # Separate transactions into OK and REVIEW categories
        ok_transactions = []
        review_transactions = []
        
        for transaction in transactions:
            file_name = transaction.get('file_name', '')
            review_item = review_lookup.get(file_name)
            
            if review_item:
                review_transactions.append((transaction, review_item))
            else:
                ok_transactions.append((transaction, None))
        
        # Add OK transactions first
        for transaction, review_item in ok_transactions:
            file_name = transaction.get('file_name', '')
            
            # Basic transaction data
            ws.cell(row=current_row, column=1, value=file_name)
            ws.cell(row=current_row, column=2, value=transaction.get('date', ''))
            ws.cell(row=current_row, column=3, value=transaction.get('amount', 0))
            ws.cell(row=current_row, column=4, value=transaction.get('category', 'Other'))
            ws.cell(row=current_row, column=5, value=transaction.get('description', ''))
            
            # OK status
            ws.cell(row=current_row, column=6, value="OK")
            ws.cell(row=current_row, column=7, value="")
            ws.cell(row=current_row, column=8, value="")
            
            current_row += 1
        
        # Add REVIEW transactions at the end
        for transaction, review_item in review_transactions:
            file_name = transaction.get('file_name', '')
            
            # Basic transaction data
            ws.cell(row=current_row, column=1, value=file_name)
            ws.cell(row=current_row, column=2, value=transaction.get('date', ''))
            ws.cell(row=current_row, column=3, value=transaction.get('amount', 0))
            ws.cell(row=current_row, column=4, value=transaction.get('category', 'Other'))
            ws.cell(row=current_row, column=5, value=transaction.get('description', ''))
            
            # Review information
            ws.cell(row=current_row, column=6, value="REVIEW")
            ws.cell(row=current_row, column=7, value=review_item.reason)
            ws.cell(row=current_row, column=8, value=review_item.raw_snippet)
            
            current_row += 1
        
        # Add any review items that don't have corresponding transactions
        for item in review_items:
            file_name = Path(item.file_path).name
            # Check if this review item already has a transaction
            has_transaction = any(t.get('file_name') == file_name for t in transactions)
            
            if not has_transaction:
                ws.cell(row=current_row, column=1, value=file_name)
                ws.cell(row=current_row, column=2, value=item.suggested_date or '')
                ws.cell(row=current_row, column=3, value=item.suggested_amount or '')
                ws.cell(row=current_row, column=4, value=item.suggested_category or '')
                ws.cell(row=current_row, column=5, value="")
                ws.cell(row=current_row, column=6, value="REVIEW")
                ws.cell(row=current_row, column=7, value=item.reason)
                ws.cell(row=current_row, column=8, value=item.raw_snippet)
                current_row += 1
        
        # Auto-adjust column widths
        column_widths = [25, 12, 12, 20, 40, 12, 40, 60]
        for i, width in enumerate(column_widths, 1):
            if i <= len(headers):
                column_letter = chr(64 + i)  # Convert to column letter (A, B, C...)
                ws.column_dimensions[column_letter].width = width
        
        logger.info(f"Created consolidated sheet with {len(transactions)} transactions and {len(review_items)} review items")
    
    
    def _add_summary_section(self, ws, transactions: List[Dict[str, Any]], start_row: int) -> int:
        """Add summary statistics to the top of the consolidated sheet."""
        if not transactions:
            ws.cell(row=start_row, column=1, value="No transactions to summarize")
            return start_row + 1
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(transactions)
        
        # Title
        ws.cell(row=start_row, column=1, value="TRANSACTION SUMMARY").font = Font(bold=True, size=14)
        current_row = start_row + 2
        
        # Basic stats in a horizontal layout
        ws.cell(row=current_row, column=1, value="Total Transactions:").font = Font(bold=True)
        ws.cell(row=current_row, column=2, value=len(transactions))
        
        if 'amount' in df.columns:
            total_amount = df['amount'].sum()
            ws.cell(row=current_row, column=4, value="Total Amount:").font = Font(bold=True)
            ws.cell(row=current_row, column=5, value=f"¥{total_amount:,}")
            
            avg_amount = df['amount'].mean()
            ws.cell(row=current_row, column=7, value="Average Amount:").font = Font(bold=True)
            ws.cell(row=current_row, column=8, value=f"¥{avg_amount:,.0f}")
        
        current_row += 2
        
        # Category breakdown in compact format
        if 'category' in df.columns:
            ws.cell(row=current_row, column=1, value="Category Breakdown:").font = Font(bold=True)
            current_row += 1
            
            category_summary = df.groupby('category').agg({
                'amount': ['count', 'sum']
            }).round(0)
            
            # Headers
            ws.cell(row=current_row, column=1, value="Category").font = Font(bold=True)
            ws.cell(row=current_row, column=2, value="Count").font = Font(bold=True)
            ws.cell(row=current_row, column=3, value="Amount").font = Font(bold=True)
            current_row += 1
            
            # Data - limit to top categories to keep compact
            top_categories = category_summary.nlargest(5, ('amount', 'sum'))
            for category, data in top_categories.iterrows():
                ws.cell(row=current_row, column=1, value=category)
                ws.cell(row=current_row, column=2, value=int(data[('amount', 'count')]))
                ws.cell(row=current_row, column=3, value=f"¥{int(data[('amount', 'sum')]):,}")
                current_row += 1
        
        return current_row
    
    @staticmethod
    def validate_transaction_data(transactions: List[Dict[str, Any]]) -> List[str]:
        """
        Validate transaction data before export.
        
        Args:
            transactions: List of transaction dictionaries
            
        Returns:
            List of validation error messages
        """
        errors = []
        required_fields = ['date', 'amount', 'category', 'description']
        
        for i, transaction in enumerate(transactions):
            for field in required_fields:
                if field not in transaction:
                    errors.append(f"Transaction {i+1}: Missing '{field}' field")
                elif transaction[field] is None:
                    errors.append(f"Transaction {i+1}: '{field}' is None")
                elif field == 'amount' and not isinstance(transaction[field], (int, float)):
                    errors.append(f"Transaction {i+1}: Amount must be numeric")
        
        return errors
    
    @staticmethod
    def create_transaction_dict(date: Optional[str], 
                              amount: Optional[int], 
                              category: str, 
                              description: str,
                              file_path: str = "") -> Dict[str, Any]:
        """
        Create a properly formatted transaction dictionary.
        
        Args:
            date: ISO date string (YYYY-MM-DD)
            amount: Amount in JPY
            category: Category name
            description: Description text
            file_path: Source file path (for metadata)
            
        Returns:
            Transaction dictionary
        """
        return {
            'date': date or '',
            'amount': amount or 0,
            'category': category,
            'description': description,
            'file_name': Path(file_path).name if file_path else ''
        }