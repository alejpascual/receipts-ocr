#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, '/Users/alejpascual/Coding/Current/receipts-ocr/src')

from parse import JapaneseReceiptParser

def test_shinkansen_parsing():
    """Test date parsing for Shinkansen receipts."""
    
    parser = JapaneseReceiptParser()
    
    # Test the exact OCR text from the Shinkansen files
    shinkansen_hiroshima_text = """2025 -3.29
京都駅MK322発行
00322-01
90000000031010
Visa Debit
この枠は大切に保存してください。
払戻しの際は購入時のカードをお持ちください。
乗車変更や払戻しの取扱箇所、内容、方法等に制限があります。
3月29日 のぞみ 67号 京都→広島 乗車券込み
3枚(冊)
ムイブング
商品や一他、 定 小金ま5-5922910,0.0,,,,,.0
会社区分:
1 C
取引内容:お買上
¥36,420
会社名·会員番号
VISA-XXXXXXXXXXXX6474
(JR西日本)
有 X--XX"""

    shinkansen_tokyo_text = """広島駅 N34 発行
30374-01
税務署承認
(認心
付につき大
(2937鉄道展式会社
JR乗車券類
購入商品
福袋
印紙税申告
〔クレジット扱い〕
¥59,880(消費税等込み)
税 10%
2025 -3.30
登録番号: T12001059675
e月額
様
第 以降"""

    print("=== Testing Shinkansen Date Parsing ===")
    
    print("\n🚅 Hiroshima Shinkansen:")
    print("OCR text contains: '2025 -3.29' and '3月29日'")
    date1 = parser.parse_date(shinkansen_hiroshima_text)
    amount1 = parser.parse_amount(shinkansen_hiroshima_text)
    print(f"Parsed date: {date1}")
    print(f"Parsed amount: ¥{amount1}")
    
    if date1 == "2025-03-29":
        print("✅ SUCCESS: Date correctly parsed as March 29, 2025")
    else:
        print(f"❌ ERROR: Expected 2025-03-29, got {date1}")
    
    print("\n🚅 Tokyo Shinkansen:")
    print("OCR text contains: '2025 -3.30'")
    date2 = parser.parse_date(shinkansen_tokyo_text)
    amount2 = parser.parse_amount(shinkansen_tokyo_text)
    print(f"Parsed date: {date2}")
    print(f"Parsed amount: ¥{amount2}")
    
    if date2 == "2025-03-30":
        print("✅ SUCCESS: Date correctly parsed as March 30, 2025")
    else:
        print(f"❌ ERROR: Expected 2025-03-30, got {date2}")
    
    # Test if both would be included in March 2025 processing
    if date1 and date2:
        from datetime import datetime
        try:
            parsed_date1 = datetime.strptime(date1, '%Y-%m-%d')
            parsed_date2 = datetime.strptime(date2, '%Y-%m-%d')
            
            is_march_2025_1 = parsed_date1.year == 2025 and parsed_date1.month == 3
            is_march_2025_2 = parsed_date2.year == 2025 and parsed_date2.month == 3
            
            print(f"\n=== March 2025 Processing Check ===")
            print(f"Hiroshima Shinkansen would be included: {'✅ YES' if is_march_2025_1 else '❌ NO'}")
            print(f"Tokyo Shinkansen would be included: {'✅ YES' if is_march_2025_2 else '❌ NO'}")
            
            if is_march_2025_1 and is_march_2025_2:
                print("🎉 BOTH SHINKANSEN RECEIPTS WILL NOW BE INCLUDED!")
            
        except ValueError as e:
            print(f"❌ Date parsing validation failed: {e}")

if __name__ == "__main__":
    test_shinkansen_parsing()