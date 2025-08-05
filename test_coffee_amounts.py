#!/usr/bin/env python3

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, '/Users/alejpascual/Coding/Current/receipts-ocr/src')

from parse import JapaneseReceiptParser
from classify import CategoryClassifier

def test_coffee_amounts():
    """Test amount parsing for coffee receipts and check for common issues."""
    
    parser = JapaneseReceiptParser()
    classifier = CategoryClassifier('/Users/alejpascual/Coding/Current/receipts-ocr/rules/categories.yml')
    
    ocr_dir = '/Users/alejpascual/Downloads/receipts-output/ocr_json'
    
    # Find potential coffee receipts or amounts like 911
    coffee_files = []
    for filename in os.listdir(ocr_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(ocr_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Look for coffee-related terms or the 911 amount
                    if any(term in content.lower() for term in ['coffee', 'roastery', 'owl', '911', 'カフェ', 'コーヒー']):
                        coffee_files.append(filename)
            except:
                continue
    
    print(f"Found {len(coffee_files)} potential coffee-related files:")
    for filename in coffee_files[:10]:  # Check first 10
        print(f"  - {filename}")
    
    print(f"\n=== Testing Coffee Amount Parsing ===")
    
    # Test each potential coffee file
    for filename in coffee_files[:5]:  # Test first 5
        filepath = os.path.join(ocr_dir, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)
            
            text = ocr_data['full_text']
            
            print(f"\n🔍 TESTING: {filename}")
            
            # Parse the receipt
            date = parser.parse_date(text)
            amount = parser.parse_amount(text)
            vendor = parser.parse_vendor(text)
            category, category_confidence = classifier.classify(vendor, "", text)
            
            print(f"   Date: {date}")
            print(f"   Amount: ¥{amount}" if amount else "   Amount: None")
            print(f"   Vendor: {vendor}")
            print(f"   Category: {category} (confidence: {category_confidence:.2f})")
            
            # Check for specific issues
            if amount == 911:
                print(f"   ⚠️  FOUND ¥911 AMOUNT - investigating...")
                # Show some OCR text to debug
                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if '911' in line or any(word in line.lower() for word in ['total', '合計', '合計', 'coffee', 'コーヒー']):
                        print(f"   OCR Line {i}: {line.strip()}")
            
            # Check coffee classification
            if 'coffee' in text.lower() or 'owl' in text.lower() or 'roastery' in text.lower():
                if category == 'Other':
                    print(f"   ❌ CLASSIFICATION ISSUE: Coffee receipt classified as 'Other'")
                elif category in ['entertainment', 'meetings']:
                    print(f"   ✅ Coffee correctly classified as {category}")
                else:
                    print(f"   ⚠️  Unusual classification: {category}")
        
        except Exception as e:
            print(f"   ❌ Error processing {filename}: {e}")

if __name__ == "__main__":
    test_coffee_amounts()