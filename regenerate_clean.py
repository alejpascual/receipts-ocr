#!/usr/bin/env python3
"""Regenerate Excel with clean descriptions from existing OCR JSON files."""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.append('src')

from parse import JapaneseReceiptParser
from classify import CategoryClassifier
from export import ExcelExporter
from review import ReviewQueue

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
            
            # Add to review queue if needed (this will check confidence thresholds)
            review_queue.add_from_extraction(
                file_path=str(json_file),
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
                    file_path=str(json_file)
                )
                
                if not needs_review:
                    # Generate CLEAN description using category
                    description = parser.extract_description_context(text, vendor, amount, category)
                    
                    # Extract clean file name from JSON file path
                    original_file_name = Path(json_file).stem
                    # Remove the hash suffix (everything after last underscore)
                    if '_' in original_file_name:
                        clean_file_name = '_'.join(original_file_name.split('_')[:-1]) + '.pdf'
                    else:
                        clean_file_name = original_file_name + '.pdf'
                    
                    transaction = {
                        'file_name': clean_file_name,
                        'date': date,
                        'amount': amount,
                        'category': category,
                        'description': description
                    }
                    transactions.append(transaction)
            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            continue
    
    # Export to new Excel with clean descriptions AND review items
    excel_path = Path('final-clean-descriptions.xlsx')
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