#!/usr/bin/env python3
"""Debug the three amount parsing issues."""

import sys
sys.path.append('.')
from src.parse import JapaneseReceiptParser

def main():
    parser = JapaneseReceiptParser()

    # Issue 1: 2025-06-14 13-46.pdf - should be ¥570, getting ¥51
    text1 = """GR266325
登録番号
TSDID7D201330
消費税額等( %)
日黒ビジネスマンション5F TEL 03-3442-35-
〒141-0021 10京都品川区上大崎2丁目15-2
消費税額等( %)
収入印紙
ネパールの用途安コーダル
手 形
小 切 手
2025 年 0 月/4 日 上記正に領収いたしました
現 金
色の食事とし
内 訳
fopul
金 額
No.
様
領 収 証念日記念とさったこ"""

    # Issue 2: 2025-06-14 19-48.pdf - should be ¥1,738, getting ¥738  
    text2 = """21273
1名
レシートNo.
01190
Tは軽減税率(8.0%)対象商品
釣り銭
0円
預かり
1,738
QRコード決済
1, 738円
合計
158円)
(内税消費税
0円
消費税(10.0%)
1,738円
小 計
1,738円
10%対象
1.078ウ
チリ産サーーモン & クリームチー
660ウ
11
ペッパー -- Cチース
# 00052
19:48
2025年 6月14日(土)
登録番号:T5011001052058
TEL 03-3461-3081
東京都渋谷区恵比寿西1-2-7 UKビル1
BAGEL &BAGEL X Kiri Cafe
BAGEL&BAGEL
×
B&B
Kiri"""

    # Issue 3: 2025-06-21 13-43.pdf - should be ¥3,564, getting ¥3,554
    text3 = """2名
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

    print('=== DEBUGGING THREE AMOUNT PARSING ISSUES ===')
    print()

    # Test each case
    tests = [
        ("2025-06-14 13-46.pdf", text1, 570, "First receipt - expected ¥570"),
        ("2025-06-14 19-48.pdf", text2, 1738, "Second receipt - expected ¥1,738"), 
        ("2025-06-21 13-43.pdf", text3, 3564, "Third receipt - expected ¥3,564")
    ]

    for filename, text, expected, description in tests:
        print(f"{description}")
        print(f"File: {filename}")
        
        amount = parser.parse_amount(text)
        status = "✅ CORRECT" if amount == expected else "❌ WRONG"
        print(f"Current result: ¥{amount}")
        print(f"Expected: ¥{expected}")
        print(f"Status: {status}")
        print()
        
        # Show all amounts found in text for analysis
        lines = text.split('\n')
        amounts_found = []
        for i, line in enumerate(lines):
            if '¥' in line or '円' in line:
                amounts_found.append(f"Line {i+1}: '{line.strip()}'")
        
        if amounts_found:
            print("Lines with amounts/yen:")
            for amount_line in amounts_found[:10]:  # Show first 10
                print(f"  {amount_line}")
        print()
        print("-" * 60)
        print()

if __name__ == "__main__":
    main()