"""Integration tests for the complete parsing system."""

import pytest
from src.parse_v2 import JapaneseReceiptParser


class TestIntegration:
    """Integration tests for complete receipt parsing."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = JapaneseReceiptParser()
    
    def test_seven_eleven_receipt(self):
        """Test parsing a typical Seven-Eleven receipt."""
        receipt_text = """
        セブンイレブン千代田店
        2024年10月30日 14:30
        
        ドリップコーヒー    ¥110
        おにぎり           ¥130
        お茶              ¥150
        
        小計              ¥390
        合計              ¥390
        お預り            ¥500
        おつり            ¥110
        """
        
        result = self.parser.parse_receipt(receipt_text)
        
        assert result['date'] == "2024-10-30"
        assert result['amount'] == 390
        assert 'セブン' in result['vendor'] or 'Seven' in result['vendor']
        assert result['confidence_scores']['date'] > 0.8
        assert result['confidence_scores']['amount'] > 0.8
    
    def test_starbucks_receipt(self):
        """Test parsing a Starbucks receipt."""
        receipt_text = """
        スターバックスコーヒー渋谷店
        2024年10月30日 15:45
        
        ドリップコーヒー トール
        アメリカーノ
        
        合計 ¥650
        お支払い金額 ¥650
        カード支払い
        """
        
        result = self.parser.parse_receipt(receipt_text)
        
        assert result['date'] == "2024-10-30"
        assert result['amount'] == 650
        assert 'Starbucks' in result['vendor'] or 'スターバックス' in result['vendor']
        assert 'coffee' in result['description'] or 'コーヒー' in result['description']
    
    def test_ikea_restaurant_receipt(self):
        """Test parsing an IKEA restaurant receipt."""
        receipt_text = """
        IKEA渋谷レストラン
        2024年10月30日
        
        プラントボール      ¥400
        ソフトクリーム      ¥200
        
        小計              ¥600
        税込合計          ¥660
        """
        
        result = self.parser.parse_receipt(receipt_text)
        
        assert result['date'] == "2024-10-30"
        assert result['amount'] == 660
        assert 'IKEA' in result['vendor']
        # Should detect as food/entertainment based on プラントボール
    
    def test_suica_train_receipt(self):
        """Test parsing a Suica train receipt."""
        receipt_text = """
        JR東日本
        2024年10月30日
        
        ◇利用日: 2024/10/30
        ◇利用金額: ¥160
        ◇残額: ¥2,340
        支払い方法: Apple Pay
        """
        
        result = self.parser.parse_receipt(receipt_text)
        
        assert result['date'] == "2024-10-30"
        assert result['amount'] == 160
        assert 'JR' in result['vendor']
        assert 'train' in result['description'] or '電車' in result['description']
    
    def test_chatgpt_invoice(self):
        """Test parsing a ChatGPT invoice."""
        receipt_text = """
        OpenAI
        Invoice Date: 2024-10-30
        
        ChatGPT Plus Subscription
        Monthly subscription fee
        
        Amount: $20.00
        ¥3,000 (converted)
        
        Total: ¥3,000
        """
        
        result = self.parser.parse_receipt(receipt_text)
        
        assert result['date'] == "2024-10-30"
        assert result['amount'] == 3000
        assert 'ChatGPT' in result['description']
        assert 'OpenAI' in result['vendor'] or 'chatgpt' in result['vendor'].lower()
    
    def test_high_value_rent_invoice(self):
        """Test parsing a high-value rent invoice."""
        receipt_text = """
        TAX INVOICE
        Invoice Date: 2025-03-31
        Account number: 12345
        Invoice number: INV-2025-001
        
        Office Rent - March 2025
        Kitchen Amenities
        BOKSEN Co-working
        
        Subtotal: ¥237,600
        Total: ¥237,600
        """
        
        result = self.parser.parse_receipt(receipt_text)
        
        assert result['date'] == "2025-03-31"
        assert result['amount'] == 237600
        assert result['description'] == 'office rent'
        # Should flag for high-value review
        assert self.parser.should_flag_for_high_value_review(
            receipt_text, result['amount'], result['date']
        )
    
    def test_dot_separated_date_receipt(self):
        """Test receipt with YY.MM.DD date format."""
        receipt_text = """
        コンビニ
        24.10.30
        
        商品A: ¥200
        商品B: ¥300
        合計: ¥500
        """
        
        result = self.parser.parse_receipt(receipt_text)
        
        assert result['date'] == "2024-10-30"
        assert result['amount'] == 500
    
    def test_wareki_date_receipt(self):
        """Test receipt with Japanese era date."""
        receipt_text = """
        株式会社テスト
        令和6年10月30日
        
        サービス料: ¥5,000
        合計: ¥5,000
        """
        
        result = self.parser.parse_receipt(receipt_text)
        
        assert result['date'] == "2024-10-30"  # 令和6年 = 2024
        assert result['amount'] == 5000
    
    def test_missing_data_handling(self):
        """Test handling of receipts with missing data."""
        receipt_text = """
        店舗名不明
        商品購入
        ありがとうございました
        """
        
        result = self.parser.parse_receipt(receipt_text)
        
        # Should handle gracefully
        assert result['date'] is None
        assert result['amount'] is None
        assert result['vendor'] is not None  # Should still try to extract something
        assert result['description'] == 'business expense'  # Default
    
    def test_confidence_scores(self):
        """Test that confidence scores are reasonable."""
        receipt_text = """
        確実なレシート
        2024年10月30日 14:30
        合計: ¥1,500
        """
        
        result = self.parser.parse_receipt(receipt_text)
        
        # All confidence scores should be between 0 and 1
        for field, confidence in result['confidence_scores'].items():
            assert 0.0 <= confidence <= 1.0, f"Invalid confidence for {field}: {confidence}"
        
        # High-quality data should have high confidence
        if result['date'] and result['amount']:
            assert result['confidence_scores']['date'] > 0.5
            assert result['confidence_scores']['amount'] > 0.5
    
    def test_metadata_inclusion(self):
        """Test that parsing metadata is included."""
        receipt_text = """
        テストショップ
        2024/10/30
        合計 ¥1,000
        """
        
        result = self.parser.parse_receipt(receipt_text)
        
        assert 'metadata' in result
        assert 'date_meta' in result['metadata']
        assert 'amount_meta' in result['metadata']
        assert 'vendor_meta' in result['metadata']
        
        # Check that metadata contains useful information
        if result['date']:
            assert 'pattern_type' in result['metadata']['date_meta']
        if result['amount']:
            assert 'type' in result['metadata']['amount_meta']
    
    def test_legacy_compatibility(self):
        """Test that legacy methods still work."""
        receipt_text = """
        レガシーテスト
        2024年10月30日
        合計: ¥2,000
        """
        
        # Test individual legacy methods
        date = self.parser.parse_date(receipt_text)
        amount = self.parser.parse_amount(receipt_text)
        vendor = self.parser.parse_vendor(receipt_text)
        description = self.parser.extract_description_context(
            receipt_text, vendor, amount, "entertainment"
        )
        
        assert date == "2024-10-30"
        assert amount == 2000
        assert vendor is not None
        assert description is not None