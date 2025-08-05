#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, '/Users/alejpascual/Coding/Current/receipts-ocr/src')

from parse import JapaneseReceiptParser
import logging

def debug_amount_priorities():
    """Debug the exact priority calculation for ¥230 vs ¥250."""
    
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

    print("=== DETAILED PRIORITY ANALYSIS ===")
    
    parser = JapaneseReceiptParser()
    lines = text.split('\n')
    
    # Let's manually trace the key lines
    print("Key lines analysis:")
    print(f"Line 8: '{lines[8]}' - contains お預り金額")
    print(f"Line 9: '{lines[9]}' - contains ¥250")
    print(f"Line 10: '{lines[10]}' - contains 合計")
    print(f"Line 11: '{lines[11]}' - contains ¥230")
    print(f"Line 12: '{lines[12]}' - contains 非課税計")
    
    # Check avoid keywords in each relevant line
    print(f"\nAvoid keyword analysis:")
    
    # Line 8 (お預り金額)
    avoid_found_line8 = [kw for kw in parser.avoid_keywords if kw in lines[8]]
    print(f"Line 8 '{lines[8]}' avoid keywords: {avoid_found_line8}")
    
    # Line 9 (¥250)  
    avoid_found_line9 = [kw for kw in parser.avoid_keywords if kw in lines[9]]
    print(f"Line 9 '{lines[9]}' avoid keywords: {avoid_found_line9}")
    
    # Line 10 (合計)
    avoid_found_line10 = [kw for kw in parser.avoid_keywords if kw in lines[10]]
    print(f"Line 10 '{lines[10]}' avoid keywords: {avoid_found_line10}")
    
    # Total keywords
    print(f"\nTotal keyword analysis:")
    total_found_line8 = [kw for kw in parser.total_keywords if kw in lines[8]]
    print(f"Line 8 '{lines[8]}' total keywords: {total_found_line8}")
    
    total_found_line10 = [kw for kw in parser.total_keywords if kw in lines[10]]
    print(f"Line 10 '{lines[10]}' total keywords: {total_found_line10}")
    
    print(f"\n=== Expected Logic ===")
    print(f"¥250 should be on line 9, found near 'お預り金額' on line 8")
    print(f"¥230 should be on line 11, found near '合計' on line 10")
    print(f"'お預り金額' is in avoid_keywords: {'お預り金額' in parser.avoid_keywords}")
    print(f"'合計' is in total_keywords: {'合計' in parser.total_keywords}")
    print(f"Therefore: ¥250 should be heavily penalized, ¥230 should get high priority from '合計'")

if __name__ == "__main__":
    debug_amount_priorities()