#!/usr/bin/env python3
"""Regenerate Excel with clean descriptions - MARCH 2025 ONLY."""
import sys
import json
import os
from pathlib import Path
from datetime import datetime
from collections import Counter
import logging

sys.path.append('src')
from parse import JapaneseReceiptParser
from classify import CategoryClassifier
from review import ReviewQueue, ReviewItem
from export import ExcelExporter

def main():
    # Get directories from environment variables or use defaults
    ocr_dir = os.environ.get('OCR_DIR', './ocr_json')
    output_dir = os.environ.get('OUTPUT_DIR', './out')
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Initialize components
    parser = JapaneseReceiptParser()
    classifier = CategoryClassifier('rules/categories.yml')
    review_queue = ReviewQueue()
    
    # Find all OCR JSON files
    ocr_files = list(Path(ocr_dir).glob('*.json'))
    
    print(f"Processing {len(ocr_files)} OCR files...")
    
    # Process each file and filter for March 2025
    clean_transactions = []
    review_items = []
    skipped_months = Counter()
    
    for ocr_file in ocr_files:
        try:
            with open(ocr_file, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)
            
            text = ocr_data['full_text']
            ocr_confidence = ocr_data.get('confidence', 0.0)
            file_path = ocr_data['file_path']
            
            # DEBUG: Track specific missing files
            debug_files = ['Meishi.pdf', 'Starbucks refill.pdf', 'Slimblade.pdf', 'Suica recharge March 21.pdf']
            is_debug_file = any(debug_name in str(ocr_file) for debug_name in debug_files)
            if is_debug_file:
                print(f"\n🔍 DEBUG: Processing {ocr_file.name}")
            
            # Extract data
            date = parser.parse_date(text)
            amount = parser.parse_amount(text)
            vendor = parser.parse_vendor(text)
            
            # Classify category
            category, category_confidence = classifier.classify(vendor, "", text)
            
            # Check if this is March 2025
            is_march_2025 = False
            is_no_date_review = False
            parsed_date = None
            
            if date:
                try:
                    parsed_date = datetime.strptime(date, '%Y-%m-%d')
                    if parsed_date.year == 2025 and parsed_date.month == 3:
                        is_march_2025 = True
                    else:
                        # Track what months we're skipping
                        month_key = f"{parsed_date.year}-{parsed_date.month:02d}"
                        skipped_months[month_key] += 1
                except ValueError:
                    skipped_months['unknown'] += 1
            else:
                # CRITICAL FIX: No date found - this should go to REVIEW, not be skipped!
                is_no_date_review = True
                skipped_months['no_date_review'] += 1
                print(f"⚠️  No date found in {file_path} - sending to review instead of skipping")
            
            # Process March 2025 receipts OR receipts with no date (for review)
            if not is_march_2025 and not is_no_date_review:
                if is_debug_file:
                    print(f"🔍 DEBUG: {ocr_file.name} - NOT March 2025 (date: {date})")
                continue
            
            if is_debug_file:
                if is_march_2025:
                    print(f"🔍 DEBUG: {ocr_file.name} - IS March 2025! Date: {date}, Amount: ¥{amount}, Category: {category}")
                elif is_no_date_review:
                    print(f"🔍 DEBUG: {ocr_file.name} - NO DATE - sending to review! Amount: ¥{amount}, Category: {category}")
                
            # Create clean filename from original path
            original_filename = Path(file_path).name
            clean_file_path = original_filename
            
            # Check if needs review (including high-value transaction check)
            # CRITICAL: No-date receipts automatically go to review
            if is_no_date_review:
                needs_review = True
            else:
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
                if is_debug_file:
                    print(f"🔍 DEBUG: {ocr_file.name} - CLEAN TRANSACTION (not flagged for review)")
                
                # Generate CLEAN description using category
                description = parser.extract_description_context(text, vendor, amount, category)
                
                # Use the same clean filename we created above
                transaction = {
                    'date': date,
                    'amount': amount,
                    'category': category,
                    'description': description,
                    'vendor': vendor,
                    'filename': clean_file_path,
                    'category_confidence': category_confidence,
                    'ocr_confidence': ocr_confidence
                }
                clean_transactions.append(transaction)
            else:
                if is_debug_file:
                    print(f"🔍 DEBUG: {ocr_file.name} - SENT TO REVIEW (needs manual review)")
                
                # Add to review queue with reason - generate reason manually
                reasons = []
                if not date:
                    if is_no_date_review:
                        reasons.append("no date found - needs manual date entry")
                    else:
                        reasons.append("missing date")
                if not amount:
                    reasons.append("missing amount")
                if category_confidence < 0.3:
                    reasons.append("low category confidence")
                if ocr_confidence < 0.3:
                    reasons.append("low OCR quality")
                if category == "Other":
                    reasons.append("unknown category")
                
                review_reason = "; ".join(reasons) if reasons else "unknown issue"
                
                review_item = ReviewItem(
                    file_path=clean_file_path,
                    reason=review_reason,
                    suggested_date=date,
                    suggested_amount=amount,
                    suggested_category=category,
                    raw_snippet=text[:200] + "..." if len(text) > 200 else text,
                    confidence_scores={
                        'category': category_confidence,
                        'ocr': ocr_confidence
                    }
                )
                review_items.append(review_item)
                
        except Exception as e:
            logger.error(f"Error processing {ocr_file}: {e}")
            continue
    
    # Filter stats
    march_count = len(clean_transactions) + len(review_items)
    total_skipped = sum(skipped_months.values())
    
    print("Filtered to March 2025 only:")
    print(f"  ✅ March 2025 transactions: {march_count}")
    print(f"  ⏭️  Non-March transactions skipped: {total_skipped}")
    if skipped_months:
        months_detail = dict(skipped_months)
        print(f"  Skipped months: {months_detail}")
    
    if not clean_transactions and not review_items:
        print("❌ No March 2025 transactions found!")
        return
    
    # Sort transactions by date
    clean_transactions.sort(key=lambda x: x['date'] if x['date'] else '1900-01-01')
    
    # Generate Excel
    output_path = Path(output_dir) / 'transactions_March_2025.xlsx'
    exporter = ExcelExporter(output_path)
    exporter.export_transactions(
        clean_transactions,
        review_items,
        include_summary=True
    )
    
    print(f"✅ Generated {len(clean_transactions)} clean March 2025 transactions in {output_path}")
    
    if review_items:
        print(f"📋 {len(review_items)} items sent to manual review")
        print()
        print("⚠️ Manual review needed for:")
        for item in review_items[:5]:  # Show first 5
            print(f"  - {item.file_path}: {item.reason}")
        if len(review_items) > 5:
            print(f"  ... and {len(review_items) - 5} more items")
    
    # Show sample descriptions for verification
    if clean_transactions:
        print()
        print("Sample descriptions:")
        for txn in clean_transactions[:5]:
            amount_str = f"¥{txn['amount']}" if txn['amount'] else "¥???"
            print(f"  {txn['date']}: {amount_str} - {txn['description']} ({txn['category']})")

if __name__ == "__main__":
    main()