#!/usr/bin/env python3
"""Regenerate Excel with clean descriptions from existing OCR JSON files - January 2025 only."""

import sys
import json
import os
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
    # Use environment variable or fallback to default batch results
    ocr_dir_path = os.getenv('OCR_DIR', 'batch-results/ocr_json')
    ocr_dir = Path(ocr_dir_path)
    
    # Get all files from January 2025 incorporation processing (most recent OCR files)
    all_files = sorted(ocr_dir.glob('*.json'), key=lambda x: x.stat().st_mtime, reverse=True)
    
    # Filter for January-related files and files from the recent incorporation batch
    january_keywords = ['2025-01-', 'Invoice(5830_4013)', 'Screenshot 2025-08-02 at 17.29', 
                       'Screenshot 2025-08-02 at 17.37', 'Screenshot 2025-08-02 at 17.55',
                       'invoice-monitor', 'Stamp receipt', 'Visa Stamp', 'houmu kyoku', 'houmy kyoku']
    
    january_files = []
    for f in all_files:
        if any(keyword in f.name for keyword in january_keywords):
            january_files.append(f)
    
    print(f"Processing {len(january_files)} January 2025 incorporation OCR files...")
    
    for json_file in january_files:
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
                
                # Temporarily check if this would be flagged for review (including high-value check)
                needs_review = review_queue.should_review(
                    date=date,
                    amount=amount,
                    category=category,
                    category_confidence=category_confidence,
                    ocr_confidence=ocr_confidence,
                    file_path=clean_file_path,
                    ocr_text=text,
                    parser=parser
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
    
    # Force filename to be January 2025
    filename = "transactions_January_2025.xlsx"
    
    # Export to new Excel with clean descriptions AND review items
    # Use environment variable or current directory for output
    output_dir_path = os.getenv('OUTPUT_DIR', '.')
    output_dir = Path(output_dir_path)
    excel_path = output_dir / filename
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