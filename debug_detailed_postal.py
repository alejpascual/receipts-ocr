#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, '/Users/alejpascual/Coding/Current/receipts-ocr/src')

from parse import JapaneseReceiptParser
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

def debug_detailed_postal():
    """Debug the exact parsing flow for postal receipt."""
    
    # The exact OCR text from the postal receipt
    text = """TNo. 250321A3801
端N28箱03
取扱日時:2025年 3月21日 11:27
登録番号 T1010001112577
東京都千代田区大手町2-3-1
〒100-8792 日本郵便株式会社
おつり
¥20
お預り金額
¥250
合計
¥230
非課税計
¥120
(内消費税等(10%)
¥10)
課税計(10%
¥110
郵便物引受合計通数
2通
小 計
¥120
@120
1通
¥120
書状定形航空使第2
14. 0g
小 計
¥110
@110
1通
第一種定形
¥110
「証紙切手引受
様
領収書"""

    print("=== POSTAL RECEIPT TEXT ===")
    print(text)
    print("\n=== PARSING ANALYSIS ===")
    
    parser = JapaneseReceiptParser()
    
    # Show which keywords are in avoid list  
    print(f"AVOID KEYWORDS: {parser.avoid_keywords}")
    print(f"TOTAL KEYWORDS: {parser.total_keywords}")
    
    # Check each line manually
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if '250' in line or '230' in line:
            print(f"\nLine {i}: '{line.strip()}'")
            
            # Check for avoid keywords
            avoid_found = []
            for avoid_kw in parser.avoid_keywords:
                if avoid_kw in line:
                    avoid_found.append(avoid_kw)
            
            if avoid_found:
                print(f"  AVOID KEYWORDS FOUND: {avoid_found}")
            
            # Check for total keywords
            total_found = []
            for total_kw in parser.total_keywords:
                if total_kw in line:
                    total_found.append(total_kw)
            
            if total_found:
                print(f"  TOTAL KEYWORDS FOUND: {total_found}")
    
    print(f"\n=== RUNNING PARSER (with debug logs) ===")
    amount = parser.parse_amount(text)
    print(f"\nFINAL PARSED AMOUNT: ¥{amount}")
    
    if amount == 250:
        print("❌ ERROR: Parser chose ¥250 (お預り金額) instead of ¥230 (合計)")
    elif amount == 230:
        print("✅ SUCCESS: Parser correctly chose ¥230 (合計)")
    else:
        print(f"❓ UNEXPECTED: Parser chose ¥{amount}")

if __name__ == "__main__":
    debug_detailed_postal()