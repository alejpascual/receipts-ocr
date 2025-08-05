#!/usr/bin/env python3

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, '/Users/alejpascual/Coding/Current/receipts-ocr/src')

from parse import JapaneseReceiptParser
from classify import CategoryClassifier

def debug_missing_invoices():
    """Debug why certain invoices are missing from March processing."""
    
    parser = JapaneseReceiptParser()
    classifier = CategoryClassifier('/Users/alejpascual/Coding/Current/receipts-ocr/rules/categories.yml')
    
    # Test files that should be included but are missing
    missing_files = [
        'Meishi_c5b04321a73ed057cd91a6455da3b3b4.json',
        'Starbucks refill_fa999e8c17d1a9d903e4d0cf3d31e6ff.json',
        'Shinkansen hirosima_7f6b189a91f6eec15152918d59286f03.json',
        'shinkansen tokyo_01fe600007203ba1b7016753056c446f.json',
        'Slimblade_67d708bebd706cee8903fb720dcc2513.json',
        'Suica recharge March 21_439b6e1f3aa9b829f7515849a4f35b2c.json'
    ]
    
    ocr_dir = '/Users/alejpascual/Downloads/receipts-output/ocr_json'
    
    for filename in missing_files:
        filepath = os.path.join(ocr_dir, filename)
        if not os.path.exists(filepath):
            print(f"❌ FILE NOT FOUND: {filename}")
            continue
            
        print(f"\n=== DEBUGGING {filename} ===")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)
            
            text = ocr_data['full_text']
            
            # Test parsing
            date = parser.parse_date(text)
            amount = parser.parse_amount(text)
            vendor = parser.parse_vendor(text)
            category, category_confidence = classifier.classify(vendor, "", text)
            
            print(f"DATE: {date}")
            print(f"AMOUNT: ¥{amount}" if amount else "AMOUNT: None")
            print(f"VENDOR: {vendor}")
            print(f"CATEGORY: {category} (confidence: {category_confidence:.2f})")
            
            # Check if date is March 2025
            is_march_2025 = False
            if date:
                try:
                    from datetime import datetime
                    parsed_date = datetime.strptime(date, '%Y-%m-%d')
                    if parsed_date.year == 2025 and parsed_date.month == 3:
                        is_march_2025 = True
                        print("✅ IS MARCH 2025")
                    else:
                        print(f"❌ NOT MARCH 2025: {parsed_date.year}-{parsed_date.month}")
                except ValueError as e:
                    print(f"❌ DATE PARSE ERROR: {e}")
            else:
                print("❌ NO DATE FOUND")
            
            # Show issues
            issues = []
            if not date:
                issues.append("No date")
            if not amount:
                issues.append("No amount")
            if not is_march_2025:
                issues.append("Not March 2025")
            
            if issues:
                print(f"❌ ISSUES: {', '.join(issues)}")
            else:
                print("✅ SHOULD BE INCLUDED - NO ISSUES FOUND!")
                
        except Exception as e:
            print(f"❌ ERROR PROCESSING {filename}: {e}")

if __name__ == "__main__":
    debug_missing_invoices()