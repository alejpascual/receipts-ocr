#!/usr/bin/env python3
"""Debug receipt 3 specifically to understand why ¥1,408 is chosen over ¥3,564."""

import sys
sys.path.append('.')
from src.parse import JapaneseReceiptParser

def main():
    parser = JapaneseReceiptParser()
    
    text = """2名
山本
T13
No. 14050
判
お釣り
¥3,564
クレジットカード
¥324)
( 内消費税等
¥3,564)
(10%対象
¥3,554
合
¥3,564
小計
¥748
今川家のなめろう ×
¥1,408
食 ×1
丼ぶり定
さばとろ丼
食 ×1
¥1,408
丼ぶり定
さばとろ丼
13:42:00
2025/06/21
T2011001040676
登録番号:
TEL : 03-6304-0710
ダイカンプラザビネス清田ビル2F
東京都新宿区西新宿7-9-15
〒160-0023
西新宿店
いまがわ食堂"""

    print('=== DEBUGGING RECEIPT 3 AMOUNT SELECTION ===')
    
    # Check for total keywords
    lines = text.split('\n')
    print(f'Total lines: {len(lines)}')
    print()
    
    print('Lines with total keywords:')
    for i, line in enumerate(lines):
        for keyword in parser.total_keywords:
            if keyword in line:
                print(f'Line {i+1}: "{line.strip()}" (keyword: {keyword})')
    print()
    
    print('All amount occurrences:')
    for i, line in enumerate(lines):
        if '¥3,564' in line or '¥1,408' in line or '¥3,554' in line:
            print(f'Line {i+1}: "{line.strip()}"')
            # Check if this line has avoid keywords
            has_avoid = any(kw in line for kw in parser.avoid_keywords)
            if has_avoid:
                avoid_keywords = [kw for kw in parser.avoid_keywords if kw in line]
                print(f'  -> HAS AVOID KEYWORDS: {avoid_keywords}')
    print()
    
    print('Testing amount extraction for key lines:')
    test_lines = [
        '¥3,564',
        '合',  # Line with "合" keyword
        '¥3,564',  # Line after "合"
        '小計',
        '¥1,408'
    ]
    
    for line in test_lines:
        amounts = parser._extract_amounts_from_line(line)
        print(f'Line "{line}": {amounts}')
    
    print()
    print('Final result:')
    amount = parser.parse_amount(text)
    print(f'Extracted: ¥{amount}')
    print(f'Expected: ¥3564')

if __name__ == "__main__":
    main()