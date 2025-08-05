#!/usr/bin/env python3
"""Test parsing on the user's actual receipt content."""

import sys
sys.path.append('src')

from parse import JapaneseReceiptParser
from classify import CategoryClassifier

def test_user_receipt():
    """Test parsing the user's receipt with the YY.MM.DD format."""
    
    parser = JapaneseReceiptParser()
    classifier = CategoryClassifier('rules/categories.yml')
    
    # Simulated OCR text from the user's receipt image
    receipt_text = """24.10.30
ホワイトソース
ハンバーグ定食/並盛
ホワイト
187
¥880 (税込み)
TEL:03-5828-0590
つゆだくなどご要望のお客様は食券を
お持ちになり、最初日まどお越し下さい
11:52  PayPay  ¥880
(株) 松屋フーズ 目黒駅前店
2024-10-30 11-53.pdf"""
    
    print("=== Testing User's Receipt ===")
    print("Receipt text (simulated from image):")
    print(receipt_text)
    print()
    
    # Parse the receipt
    date = parser.parse_date(receipt_text)
    amount = parser.parse_amount(receipt_text)
    vendor = parser.parse_vendor(receipt_text)
    category, confidence = classifier.classify(vendor, "", receipt_text)
    
    print("=== Parsing Results ===")
    print(f"📅 Date: {date}")
    print(f"💰 Amount: ¥{amount}")
    print(f"🏢 Vendor: {vendor}")
    print(f"📂 Category: {category} (confidence: {confidence:.2f})")
    
    # Check if the date parsing worked
    if date == "2024-10-30":
        print(f"\n✅ SUCCESS: YY.MM.DD format correctly parsed!")
        print(f"   '24.10.30' → '{date}' ✓")
    else:
        print(f"\n❌ FAILED: Expected 2024-10-30, got {date}")
    
    # This should no longer need manual review for missing date
    if date:
        print(f"✅ Receipt will NOT be flagged for 'no date found' anymore!")
    else:
        print(f"❌ Receipt would still be flagged for missing date")

if __name__ == "__main__":
    test_user_receipt()