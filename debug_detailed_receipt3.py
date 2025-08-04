#!/usr/bin/env python3
"""Detailed debugging of receipt 3 candidate selection."""

import sys
sys.path.append('.')
import logging

# Enable DEBUG logging
logging.basicConfig(level=logging.DEBUG)

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

    print('=== DETAILED DEBUGGING RECEIPT 3 ===')
    amount = parser.parse_amount(text)
    print(f'Final extracted amount: ¥{amount}')

if __name__ == "__main__":
    main()