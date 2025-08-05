#!/usr/bin/env python3
"""Test the new YY.MM.DD date pattern."""

import sys
sys.path.append('src')

from parse import JapaneseReceiptParser

def test_date_pattern():
    """Test the new YY.MM.DD date pattern with the example from the user."""
    
    parser = JapaneseReceiptParser()
    
    # Test cases from the user's receipt and similar formats
    test_cases = [
        {
            "text": "24.10.30\nホワイトソース\nハンバーグ定食",
            "expected": "2024-10-30",
            "description": "User's example: 24.10.30 = October 30, 2024"
        },
        {
            "text": "25.03.15\n合計 ¥1200",
            "expected": "2025-03-15", 
            "description": "March 15, 2025 format"
        },
        {
            "text": "23.12.31\n年末のお買い物",
            "expected": "2023-12-31",
            "description": "December 31, 2023 format"
        },
        {
            "text": "99.05.20\n昔のレシート",
            "expected": "1999-05-20",
            "description": "Year 99 should become 1999"
        }
    ]
    
    print("=== Testing YY.MM.DD Date Pattern ===")
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. {case['description']}")
        print(f"   Text: {case['text'].split()[0]}")
        
        parsed_date = parser.parse_date(case['text'])
        
        if parsed_date == case['expected']:
            print(f"   ✅ SUCCESS: {parsed_date}")
        else:
            print(f"   ❌ FAILED: Expected {case['expected']}, got {parsed_date}")
    
    # Test that it doesn't conflict with other patterns
    print(f"\n=== Testing No Conflicts ===")
    
    conflict_tests = [
        {
            "text": "2024年10月30日",
            "expected": "2024-10-30",
            "description": "Full Japanese format should still work"
        },
        {
            "text": "2024/10/30", 
            "expected": "2024-10-30",
            "description": "YYYY/MM/DD format should still work"
        }
    ]
    
    for case in conflict_tests:
        parsed_date = parser.parse_date(case['text'])
        if parsed_date == case['expected']:
            print(f"   ✅ {case['description']}: {parsed_date}")
        else:
            print(f"   ❌ {case['description']}: Expected {case['expected']}, got {parsed_date}")

if __name__ == "__main__":
    test_date_pattern()