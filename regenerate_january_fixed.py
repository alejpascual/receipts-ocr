#!/usr/bin/env python3
"""Regenerate Excel with all January 2025 incorporation files - FIXED VERSION."""

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
    
    # FIXED: Get the specific files that should be in January 2025
    january_files = [
        'Invoice(5830_4013)_be6b6d5a7b3a8b2db22b7b1e5d4d9c8e.json',  # Rent invoice
        '2025-02-21 14-56_0356172a8984be6902eb1d1e73e0220e.json',  # The missing receipt  
        'Screenshot 2025-08-02 at 17.29.35_bf888794f04636d656b8921c5b4124c7.json',
        'Screenshot 2025-08-02 at 17.29.51_f6ffb72ff1bd8d31b628253b2104850a.json', 
        'Screenshot 2025-08-02 at 17.37.33_ef22c3810fbbc5a5c6326a0ae4501939.json',
        'Screenshot 2025-08-02 at 17.55.14_d4f77d429960a2fee32b9b583fccfd8f.json',
        'invoice-monitor_e9d8f7c6b5a4932e1f0e9d8c7b6a5948.json',
        'Stamp receipt 1 (incorporation)_8f52dd5734b9646068fca9578f00ad1e.json',
        'Stamp receipt 2 (incorporation)_b03c7ffbee8dad5fd67fefb59c922ad2.json', 
        'Visa Stamp_9b4317470713d0e0a8d94a085a9293e9.json',
        'houmu kyoku document_735d6b01603fd906e877c9bfcd0f7333.json',
        'houmy kyoku document_d475d20ab4cdbbc5d00e10a812604f06.json',
        '2025-02-25 10-12_4c437e5f055e0e2e40cc0eebca19b867.json'  # This one too
    ]
    
    # Find files that actually exist (use partial matching since hashes might differ)
    existing_files = []
    for target_file in january_files:
        # Try exact match first
        exact_path = ocr_dir / target_file
        if exact_path.exists():
            existing_files.append(exact_path)
        else:
            # Try partial matching on the base name
            base_name = target_file.split('_')[0]
            matches = list(ocr_dir.glob(f"{base_name}_*.json"))
            if matches:
                existing_files.extend(matches)
    
    # Also add files by pattern matching
    pattern_files = []
    for pattern in ['Invoice*4013*.json', '*2025-02-21 14-56*.json', '*2025-02-25 10-12*.json', 
                   '*Screenshot*17.29*.json', '*Screenshot*17.37*.json', '*Screenshot*17.55*.json',
                   '*monitor*.json', '*Stamp receipt*.json', '*Visa Stamp*.json', 
                   '*houmu*.json', '*houmy*.json']:
        pattern_files.extend(ocr_dir.glob(pattern))
    
    # Combine and deduplicate
    all_january_files = list(set(existing_files + pattern_files))
    
    print(f"Processing {len(all_january_files)} January 2025 incorporation OCR files...")
    
    for json_file in all_january_files:
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
                    # CRITICAL: Only include January 2025 transactions
                    try:
                        date_obj = datetime.strptime(date, '%Y-%m-%d')
                        if date_obj.year == 2025 and date_obj.month == 1:
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
                            print(f"Added: {clean_file_path} - {date} - ¥{amount} - {category}")
                        else:
                            print(f"Skipped (not January 2025): {clean_file_path} - {date} - ¥{amount} - {category}")
                    except ValueError:
                        print(f"Skipped (invalid date): {clean_file_path} - {date} - ¥{amount} - {category}")
            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            continue
    
    # Force filename to be January 2025
    filename = "transactions_January_2025.xlsx"
    
    # Remove old file first
    output_dir_path = os.getenv('OUTPUT_DIR', '.')
    output_dir = Path(output_dir_path)
    old_excel_path = output_dir / filename
    if old_excel_path.exists():
        old_excel_path.unlink()
    
    # Export to new Excel with clean descriptions AND review items
    excel_path = output_dir / filename
    exporter = ExcelExporter(excel_path)
    exporter.export_transactions(transactions, review_queue.items, include_summary=True)
    
    print(f'✅ Generated {len(transactions)} clean transactions in {excel_path}')
    print(f'📋 {len(review_queue.items)} items sent to manual review')
    
    if review_queue.items:
        print(f"\n⚠️ Manual review needed for:")
        for item in review_queue.items[:10]:  # Show more items
            print(f"  - {Path(item.file_path).name}: {item.reason}")
    
    print("\nAll transactions:")
    for i, t in enumerate(transactions):
        print(f"  {t['date']}: ¥{t['amount']} - {t['description']} ({t['category']})")

if __name__ == '__main__':
    main()