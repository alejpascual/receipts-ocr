#!/usr/bin/env python3
"""Detailed debug of amount parsing to see exactly what's happening."""

import sys
sys.path.append('.')
import logging

# Enable DEBUG logging to see the internal logic
logging.basicConfig(level=logging.DEBUG)

from src.parse import JapaneseReceiptParser

def main():
    parser = JapaneseReceiptParser()

    text = """¥0
¥6,160
2017年7月
¥560)
税込,
ma
¥6,100)
(1)
山科
¥6 160
4点
 ...
¥し
gox 2
ジャスミンボル
¥3,80× 2
¥6,160
ランナムコース
、 県 に関連し
-hhikikho voiti
.........
...川り探し、下さい
(1):
:場合は、
保管
Itt lis siu.1 1 1 14:
17.
1 分区宇田川町
日曜日:1901901000:0291.1
ひいとろ渋谷店 機関連
担当:
発展
上記正に領収いたしました
但し ご飲食代
として
対象は全て軽減税率対象です
内消費費税等
¥560)
(川内線税込計
¥0,160)
(1)消費税等
¥560)
¥6, 160-
悠
領収日:2025年06月10日
領収書"""

    print('=== DETAILED DEBUG OF AMOUNT PARSING ===')
    
    # Let me manually step through what the parser should be doing
    lines = text.split('\n')
    
    print(f'Total lines: {len(lines)}')
    print()
    
    # Look for total keywords and what amounts are near them
    for line_idx, line in enumerate(lines):
        for keyword in parser.total_keywords:
            if keyword in line:
                print(f'Found keyword "{keyword}" in line {line_idx+1}: "{line.strip()}"')
                
                # Check nearby lines for amounts
                for offset in [-1, 0, 1]:
                    check_idx = line_idx + offset
                    if 0 <= check_idx < len(lines):
                        check_line = lines[check_idx]
                        if '¥' in check_line:
                            print(f'  Near line {check_idx+1} ({offset:+d}): "{check_line.strip()}"')
                            
                            # Check for avoid keywords
                            has_avoid = any(avoid_kw in check_line for avoid_kw in parser.avoid_keywords)
                            if has_avoid:
                                print(f'    -> HAS AVOID KEYWORD!')
                print()

    print('Now running the actual parser...')
    amount = parser.parse_amount(text)
    print(f'Final result: ¥{amount}')

if __name__ == "__main__":
    main()