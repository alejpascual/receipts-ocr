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
        Export transactions and review data to Excel.
        
        Args:
            transactions: List of transaction dictionaries
            review_items: List of items needing review
            include_summary: Whether to include summary sheet
        """
        try:
            # Remove default sheet
            if "Sheet" in self.workbook.sheetnames:
                self.workbook.remove(self.workbook["Sheet"])
            
            # Create transactions sheet
            self._create_transactions_sheet(transactions)
            
            # Create review sheet
            self._create_review_sheet(review_items)
            
            # Create summary sheet if requested
            if include_summary:
                self._create_summary_sheet(transactions)
            
            # Save workbook
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.workbook.save(str(self.output_path))
            
            logger.info(f"Excel file exported to: {self.output_path}")
            
        except Exception as e:
            logger.error(f"Failed to export Excel file: {e}")
            raise
    
    def _create_transactions_sheet(self, transactions: List[Dict[str, Any]]):
        """Create the main transactions sheet."""
        ws = self.workbook.create_sheet("Transactions")
        
        # Define headers with File Name as first column
        headers = ["File Name", "Date", "Amount", "Category", "Description"]
        
        # Add headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="E6E6E6", end_color="E6E6E6", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        
        # Add transaction data
        for row, transaction in enumerate(transactions, 2):
            ws.cell(row=row, column=1, value=transaction.get('file_name', ''))
            ws.cell(row=row, column=2, value=transaction.get('date', ''))
            ws.cell(row=row, column=3, value=transaction.get('amount', 0))
            ws.cell(row=row, column=4, value=transaction.get('category', 'Other'))
            ws.cell(row=row, column=5, value=transaction.get('description', ''))
        
        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)  # Cap at 50 chars
            ws.column_dimensions[column_letter].width = adjusted_width
        
        logger.info(f"Created transactions sheet with {len(transactions)} records")
    
    def _create_review_sheet(self, review_items: List[ReviewItem]):
        """Create the review sheet for items needing manual attention."""
        ws = self.workbook.create_sheet("Review")
        
        # Define headers as specified in PRD
        headers = ["File", "Reason", "Suggested Date", "Suggested Amount", 
                  "Suggested Category", "Raw Snippet"]
        
        # Add headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="FFE6E6", end_color="FFE6E6", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        
        # Add review items
        for row, item in enumerate(review_items, 2):
            file_name = Path(item.file_path).name
            ws.cell(row=row, column=1, value=file_name)
            ws.cell(row=row, column=2, value=item.reason)
            ws.cell(row=row, column=3, value=item.suggested_date or '')
            ws.cell(row=row, column=4, value=item.suggested_amount or '')
            ws.cell(row=row, column=5, value=item.suggested_category or '')
            ws.cell(row=row, column=6, value=item.raw_snippet)
        
        # Auto-adjust column widths
        column_widths = [25, 40, 12, 12, 20, 60]  # Custom widths for review sheet
        for i, width in enumerate(column_widths, 1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width
        
        logger.info(f"Created review sheet with {len(review_items)} items")
    
    def _create_summary_sheet(self, transactions: List[Dict[str, Any]]):
        """Create a summary/pivot sheet with transaction analytics."""
        ws = self.workbook.create_sheet("Summary")
        
        if not transactions:
            ws.cell(row=1, column=1, value="No transactions to summarize")
            return
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(transactions)
        
        # Summary statistics
        ws.cell(row=1, column=1, value="Transaction Summary").font = Font(bold=True, size=14)
        
        row = 3
        ws.cell(row=row, column=1, value="Total Transactions:")
        ws.cell(row=row, column=2, value=len(transactions))
        
        row += 1
        if 'amount' in df.columns:
            total_amount = df['amount'].sum()
            ws.cell(row=row, column=1, value="Total Amount:")
            ws.cell(row=row, column=2, value=f"¥{total_amount:,}")
            
            row += 1
            avg_amount = df['amount'].mean()
            ws.cell(row=row, column=1, value="Average Amount:")
            ws.cell(row=row, column=2, value=f"¥{avg_amount:,.0f}")
        
        # Category breakdown
        row += 3
        ws.cell(row=row, column=1, value="By Category:").font = Font(bold=True)
        row += 1
        
        if 'category' in df.columns:
            category_summary = df.groupby('category').agg({
                'amount': ['count', 'sum']
            }).round(0)
            
            ws.cell(row=row, column=1, value="Category")
            ws.cell(row=row, column=2, value="Count")
            ws.cell(row=row, column=3, value="Total Amount")
            
            for col in range(1, 4):
                ws.cell(row=row, column=col).font = Font(bold=True)
            
            row += 1
            for category, data in category_summary.iterrows():
                ws.cell(row=row, column=1, value=category)
                ws.cell(row=row, column=2, value=int(data[('amount', 'count')]))
                ws.cell(row=row, column=3, value=f"¥{int(data[('amount', 'sum')]):,}")
                row += 1
        
        # Monthly breakdown if dates available
        if 'date' in df.columns:
            row += 2
            ws.cell(row=row, column=1, value="By Month:").font = Font(bold=True)
            row += 1
            
            # Convert dates to datetime for grouping
            df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
            monthly_summary = df.groupby(df['date_parsed'].dt.to_period('M')).agg({
                'amount': ['count', 'sum']
            }).round(0)
            
            ws.cell(row=row, column=1, value="Month")
            ws.cell(row=row, column=2, value="Count")
            ws.cell(row=row, column=3, value="Total Amount")
            
            for col in range(1, 4):
                ws.cell(row=row, column=col).font = Font(bold=True)
            
            row += 1
            for month, data in monthly_summary.iterrows():
                ws.cell(row=row, column=1, value=str(month))
                ws.cell(row=row, column=2, value=int(data[('amount', 'count')]))
                ws.cell(row=row, column=3, value=f"¥{int(data[('amount', 'sum')]):,}")
                row += 1
        
        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 30)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        logger.info("Created summary sheet with analytics")
    
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
            'source_file': Path(file_path).name if file_path else ''
        }