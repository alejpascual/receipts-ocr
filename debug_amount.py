#!/usr/bin/env python3
"""Debug the amount parsing issue with 2025-06-10 23-17.pdf."""

import sys
sys.path.append('.')
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

    print('DEBUG: Testing current amount parsing...')
    amount = parser.parse_amount(text)
    print(f'Current result: ¥{amount}')
    print(f'Expected: ¥6160')
    print(f'Status: {"CORRECT" if amount == 6160 else "WRONG"}')

    print()
    print('DEBUG: Lines with amounts...')

    lines = text.split('\n')
    for i, line in enumerate(lines):
        if '¥560' in line or '¥6,160' in line or '¥6160' in line or '¥6 160' in line:
            print(f'Line {i+1}: "{line.strip()}"')
            
            # Check if this line has avoid keywords
            avoid_keywords = ['内消費税', '消費税', '税額', '税金', '内消費費税等']
            has_avoid = any(kw in line for kw in avoid_keywords)
            if has_avoid:
                print(f'  -> HAS AVOID KEYWORD!')

if __name__ == "__main__":
    main()