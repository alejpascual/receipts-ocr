#!/usr/bin/env python3
"""Debug the specific February receipts that were incorrectly parsed."""

import sys
import json
from pathlib import Path

sys.path.append('src')
from parse import JapaneseReceiptParser
from classify import CategoryClassifier

def debug_specific_receipts():
    """Debug the receipts that were incorrectly parsed based on user feedback."""
    
    parser = JapaneseReceiptParser()
    classifier = CategoryClassifier('rules/categories.yml')
    
    # Look for the OCR files that correspond to the corrected receipts
    ocr_dir = Path("/Users/alejpascual/Downloads/receipts-output/ocr_json")
    
    problem_files = [
        # Screenshot file with wrong date
        "Screenshot 2025-08-01 at 16.38",
        # Files with potential amount issues
        "2025-02-17 15-26",
        "2025-02-28 18-20", 
        "2025-02-25 14-11",
        "2025-02-25 19-29"
    ]
    
    print("=== Debugging February Receipt Issues ===")
    
    for problem_file in problem_files:
        print(f"\n🔍 Looking for: {problem_file}")
        
        # Find matching OCR JSON files
        matching_files = list(ocr_dir.glob(f"*{problem_file}*.json"))
        
        if not matching_files:
            print(f"❌ No OCR file found for {problem_file}")
            continue
            
        for ocr_file in matching_files:
            print(f"\n📄 Processing: {ocr_file.name}")
            
            try:
                with open(ocr_file, 'r', encoding='utf-8') as f:
                    ocr_data = json.load(f)
                
                text = ocr_data['full_text']
                
                # Parse the receipt
                date = parser.parse_date(text)
                amount = parser.parse_amount(text)
                vendor = parser.parse_vendor(text)
                category, category_confidence = classifier.classify(vendor, "", text)
                
                print(f"  📅 Parsed date: {date}")
                print(f"  💰 Parsed amount: ¥{amount}")
                print(f"  🏢 Parsed vendor: {vendor}")
                print(f"  📂 Category: {category} (confidence: {category_confidence:.2f})")
                
                # Show first few lines of OCR text to understand content
                print(f"  📝 OCR preview:")
                for i, line in enumerate(text.split('\n')[:5]):
                    if line.strip():
                        print(f"    {i+1}: {line.strip()}")
                
                # Special checks based on known issues
                if "Screenshot" in ocr_file.name:
                    print(f"  ⚠️  SCREENSHOT FILE - Date should come from receipt content, not filename")
                    if "railway" in text.lower() or "vps" in text.lower():
                        print(f"  🔧 Should be Software and Services (Railway VPS)")
                
            except Exception as e:
                print(f"❌ Error processing {ocr_file}: {e}")

def test_new_classifications():
    """Test the new category classifications we added."""
    
    classifier = CategoryClassifier('rules/categories.yml')
    
    test_cases = [
        ("Railway VPS hosting service", "railway vps monthly subscription"),
        ("VPS Server", "virtual private server hosting"),
        ("Vercel hosting", "vercel deployment hosting"),
        ("AWS services", "aws ec2 server hosting"),
        ("Domain registration", "domain ssl certificate")
    ]
    
    print(f"\n=== Testing New Software Service Classifications ===")
    
    for description, text in test_cases:
        category, confidence = classifier.classify("", "", text)
        status = "✅" if category == "Software and Services" else "❌"
        print(f"{status} {description}: {category} (confidence: {confidence:.2f})")

if __name__ == "__main__":
    debug_specific_receipts()
    test_new_classifications()