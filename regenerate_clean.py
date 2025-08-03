#!/usr/bin/env python3
"""Regenerate Excel with clean descriptions from existing OCR JSON files."""

import sys
import json
from pathlib import Path
from datetime import datetime
from collections import Counter

# Add src to path
sys.path.append('src')

from parse import JapaneseReceiptParser
from classify import CategoryClassifier
from export import ExcelExporter
from review import ReviewQueue


def determine_month_year_from_transactions(transactions):
    """
    Determine the most common month/year from transaction dates.
    
    Args:
        transactions: List of transaction dictionaries with date fields
        
    Returns:
        String in format "August 2024" or "Mixed Months" if no clear majority
    """
    if not transactions:
        return "Unknown Period"
    
    # Extract month/year from valid dates
    month_years = []
    for transaction in transactions:
        date_str = transaction.get('date')
        if date_str:
            try:
                # Parse ISO date format (YYYY-MM-DD)
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                month_year = date_obj.strftime('%B %Y')  # e.g., "August 2024"
                month_years.append(month_year)
            except ValueError:
                continue
    
    if not month_years:
        return "Unknown Period"
    
    # Find most common month/year
    month_year_counts = Counter(month_years)
    most_common = month_year_counts.most_common(1)[0]
    
    # If the most common month/year represents >50% of transactions, use it
    if most_common[1] / len(month_years) > 0.5:
        return most_common[0]
    else:
        return "Mixed Months"

def main():
    # Initialize components
    parser = JapaneseReceiptParser()
    classifier = CategoryClassifier(Path('rules/categories.yml'))
    review_queue = ReviewQueue()
    
    # Read existing OCR results and regenerate with clean descriptions
    transactions = []
    ocr_dir = Path('batch-results/ocr_json')  # Use the complete original batch
    
    print(f"Processing {len(list(ocr_dir.glob('*.json')))} OCR files...")
    
    for json_file in sorted(ocr_dir.glob('*.json')):
        try:
            with open(json_file) as f:
                data = json.load(f)
            
            text = data.get('full_text', '')
            if not text:
                continue
                
            # Parse data
            date = parser.parse_date(text)
            amount = parser.parse_amount(text)
            vendor = parser.parse_vendor(text)
            
            # Classify category first
            category, category_confidence = classifier.classify(vendor, "", text)
            
            # Get OCR confidence from the data
            ocr_confidence = data.get('confidence', 0.8)
            
            # Extract clean file name from JSON file path BEFORE creating review queue
            original_file_name = Path(json_file).stem
            # Remove the hash suffix (everything after last underscore)
            if '_' in original_file_name:
                clean_file_path = '_'.join(original_file_name.split('_')[:-1]) + '.pdf'
            else:
                clean_file_path = original_file_name + '.pdf'
            
            # Add to review queue with CLEAN filename (this will check confidence thresholds)
            review_queue.add_from_extraction(
                file_path=clean_file_path,
                date=date,
                amount=amount,
                category=category,
                category_confidence=category_confidence,
                ocr_confidence=ocr_confidence,
                raw_text=text
            )
            
            # Only add to transactions if we have valid date and amount AND it's not flagged for review
            if date and amount:
                # Check if this item was flagged for review
                current_review_count = len(review_queue.items)
                
                # Temporarily check if this would be flagged for review
                needs_review = review_queue.should_review(
                    date=date,
                    amount=amount,
                    category=category,
                    category_confidence=category_confidence,
                    ocr_confidence=ocr_confidence,
                    file_path=clean_file_path
                )
                
                if not needs_review:
                    # Generate CLEAN description using category
                    description = parser.extract_description_context(text, vendor, amount, category)
                    
                    # Use the same clean filename we created above
                    transaction = {
                        'file_name': clean_file_path,
                        'date': date,
                        'amount': amount,
                        'category': category,
                        'description': description
                    }
                    transactions.append(transaction)
            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            continue
    
    # Determine month/year for filename
    month_year = determine_month_year_from_transactions(transactions)
    
    # Create filename with month/year
    if month_year in ["Unknown Period", "Mixed Months"]:
        filename = f"transactions_{month_year.replace(' ', '_')}.xlsx"
    else:
        # Convert "August 2024" to "transactions_August_2024.xlsx"
        filename = f"transactions_{month_year.replace(' ', '_')}.xlsx"
    
    # Export to new Excel with clean descriptions AND review items
    excel_path = Path(filename)
    exporter = ExcelExporter(excel_path)
    exporter.export_transactions(transactions, review_queue.items, include_summary=True)
    
    print(f'✅ Generated {len(transactions)} clean transactions in {excel_path}')
    print(f'📋 {len(review_queue.items)} items sent to manual review')
    
    if review_queue.items:
        print(f"\n⚠️ Manual review needed for:")
        for item in review_queue.items[:5]:  # Show first 5
            print(f"  - {Path(item.file_path).name}: {item.reason}")
        if len(review_queue.items) > 5:
            print(f"  ... and {len(review_queue.items) - 5} more items")
    
    print("\nSample descriptions:")
    for i, t in enumerate(transactions[:5]):
        print(f"  {t['date']}: ¥{t['amount']} - {t['description']} ({t['category']})")

if __name__ == '__main__':
    main()