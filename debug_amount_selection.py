#!/usr/bin/env python3
"""Debug amount selection for the specific receipts that had wrong amounts."""

import sys
import json
from pathlib import Path

sys.path.append('src')
from parse import JapaneseReceiptParser

def debug_specific_amount_issues():
    """Debug the specific receipts with known amount selection issues."""
    
    parser = JapaneseReceiptParser()
    ocr_dir = Path("/Users/alejpascual/Downloads/receipts-output/ocr_json")
    
    problem_cases = [
        {
            "file": "2025-02-17 15-26",
            "expected": 2040,
            "selected": 1854,
            "issue": "Should select ¥2040 visible in OCR, not ¥1854"
        },
        {
            "file": "2025-02-28 18-20", 
            "expected": 440,
            "selected": 40,
            "issue": "Should select total amount ¥440, not ¥40"
        },
        {
            "file": "2025-02-25 14-11 1",
            "expected": 1780,
            "selected": 1780,  # This one was actually correct
            "issue": "Check why this was initially wrong"
        }
    ]
    
    print("=== Debugging Amount Selection Issues ===")
    
    for case in problem_cases:
        print(f"\n🔍 Case: {case['file']}")
        print(f"   Expected: ¥{case['expected']}, Got: ¥{case['selected']}")
        print(f"   Issue: {case['issue']}")
        
        # Find matching OCR file
        matching_files = list(ocr_dir.glob(f"*{case['file']}*.json"))
        
        if not matching_files:
            print(f"❌ No OCR file found")
            continue
            
        for ocr_file in matching_files:
            print(f"\n📄 Analyzing: {ocr_file.name}")
            
            try:
                with open(ocr_file, 'r', encoding='utf-8') as f:
                    ocr_data = json.load(f)
                
                text = ocr_data['full_text']
                
                # Show full OCR text to understand what amounts are available
                print(f"\n📝 Full OCR text:")
                for i, line in enumerate(text.split('\n'), 1):
                    if line.strip():
                        print(f"  {i:2d}: {line.strip()}")
                
                # Test amount parsing with debug logging
                print(f"\n🔍 Amount parsing analysis:")
                import logging
                logging.getLogger().setLevel(logging.DEBUG)
                
                amount = parser.parse_amount(text)
                print(f"Final selected amount: ¥{amount}")
                
                # Check if expected amount exists in text
                expected_str = str(case['expected'])
                if expected_str in text:
                    print(f"✅ Expected amount ¥{case['expected']} IS in the text")
                    # Find which lines contain it
                    for i, line in enumerate(text.split('\n'), 1):
                        if expected_str in line:
                            print(f"    Line {i}: {line.strip()}")
                else:
                    print(f"❌ Expected amount ¥{case['expected']} NOT found in text")
                
            except Exception as e:
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_specific_amount_issues()