#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, '/Users/alejpascual/Coding/Current/receipts-ocr/src')

from parse import JapaneseReceiptParser

def debug_simple_postal():
    """Simple debug to see which amount has highest priority."""
    
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

    parser = JapaneseReceiptParser()
    
    # Parse manually to get all candidates
    lines = text.split('\n')
    amount_candidates = []
    
    # Simulate the parsing logic to get candidates
    for line_idx, line in enumerate(lines):
        # Look for amounts near total keywords
        for keyword in parser.total_keywords:
            if keyword in line:
                # Search in current line and adjacent lines
                search_lines = []
                search_lines.append((line, line_idx, 'current'))
                if line_idx > 0:
                    search_lines.append((lines[line_idx - 1], line_idx - 1, 'previous'))
                if line_idx < len(lines) - 1:
                    search_lines.append((lines[line_idx + 1], line_idx + 1, 'next'))
                
                for search_line, search_idx, position in search_lines:
                    amounts = parser._extract_amounts_from_line(search_line)
                    for amount, confidence in amounts:
                        # Skip if tax amount
                        if parser._is_tax_amount(amount, search_line, lines, search_idx):
                            continue
                        
                        # Calculate priority similar to actual parser
                        if keyword == '合計':
                            if position == 'previous':
                                keyword_priority = 6000
                            elif position == 'current':
                                keyword_priority = 5000
                            else:
                                keyword_priority = 4000
                        else:
                            keyword_priority = 1000
                        
                        # Check for avoid keywords and apply penalties
                        line_has_avoid_keyword = any(avoid_kw in search_line for avoid_kw in parser.avoid_keywords)
                        prev_line_has_avoid_keyword = False
                        if search_idx > 0:
                            prev_line = lines[search_idx - 1]
                            prev_line_has_avoid_keyword = any(avoid_kw in prev_line for avoid_kw in parser.avoid_keywords)
                        
                        if line_has_avoid_keyword:
                            keyword_priority -= 50
                        elif prev_line_has_avoid_keyword:
                            keyword_priority -= 180
                        
                        amount_candidates.append((amount, keyword_priority + confidence, search_line, f"keyword:{keyword}, position:{position}"))
    
    # Also add frequency-based candidates
    frequency = {230: 4, 250: 4}  # Both appear 4 times
    
    # Add frequency candidates with penalties
    for amount in [230, 250]:
        line_containing_amount = f"¥{amount}"
        confidence = 90  # typical confidence
        frequency_priority = confidence + (frequency[amount] * 300)
        
        # Apply penalties for ¥250 (has "お預り金額" in previous line)
        if amount == 250:
            frequency_priority -= 180  # penalty for avoid keyword in previous line
        
        amount_candidates.append((amount, frequency_priority, line_containing_amount, "frequency"))
    
    print("=== ALL AMOUNT CANDIDATES ===")
    sorted_candidates = sorted(amount_candidates, key=lambda x: x[1], reverse=True)
    for amount, priority, line, source in sorted_candidates:
        if amount in [230, 250]:  # Only show the amounts we care about
            print(f"¥{amount}: priority {priority} from {source} in line '{line.strip()}'")
    
    print(f"\n=== WINNER ===")
    if sorted_candidates:
        winner = sorted_candidates[0]
        print(f"Highest priority: ¥{winner[0]} with priority {winner[1]}")
        if winner[0] == 230:
            print("✅ SUCCESS: ¥230 (合計) should win!")
        elif winner[0] == 250:
            print("❌ ERROR: ¥250 (お預り金額) is still winning")

if __name__ == "__main__":
    debug_simple_postal()