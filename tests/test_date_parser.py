"""Tests for DateParser component."""

import pytest
from src.parsers.date_parser import DateParser
from src.parsers.base import ReceiptContext


class TestDateParser:
    """Test suite for DateParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = DateParser()
    
    def test_japanese_full_date(self):
        """Test parsing of full Japanese date format."""
        text = "2024年10月30日 14:30\n領収証"
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == "2024-10-30"
        assert result.confidence > 0.8
        assert result.metadata['pattern_type'] == 'japanese_full'
    
    def test_wareki_date(self):
        """Test parsing of Japanese era dates."""
        text = "令和6年7月12日\n株式会社テスト"
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == "2024-07-12"  # 令和6年 = 2024
        assert result.confidence > 0.9
        assert result.metadata['pattern_type'] == 'wareki'
    
    def test_dot_separated_date(self):
        """Test YY.MM.DD format common in Japanese receipts."""
        text = "24.10.30\nセブンイレブン\n¥450"
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == "2024-10-30"
        assert result.confidence > 0.4
        assert result.metadata['pattern_type'] == 'dot'
    
    def test_slash_date(self):
        """Test YYYY/MM/DD format."""
        text = "2024/12/25\nスターバックス"
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == "2024-12-25"
        assert result.metadata['pattern_type'] == 'slash'
    
    def test_date_priority_with_keywords(self):
        """Test that dates near keywords get higher priority."""
        text = """
        2024/01/01 due date
        Invoice Date: 2024/10/30
        Service period: 2024/11/01
        """
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == "2024-10-30"  # Should pick invoice date
    
    def test_ocr_correction_high_value(self):
        """Test OCR correction for high-value documents."""
        text = """
        TAX INVOICE
        Invoice Date: 2025-05-31
        Amount: ¥237,600
        March rental payment
        """
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        # Should correct 05-31 to 03-31 based on "March rental" context
        assert result.value == "2025-03-31"
    
    def test_month_day_only(self):
        """Test MM月DD日 format with year inference."""
        text = "10月30日\nコンビニ購入"
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == "2025-10-30"  # Should infer current year
        assert result.metadata['pattern_type'] == 'month_day'
    
    def test_invalid_dates_rejected(self):
        """Test that invalid dates are properly rejected."""
        invalid_texts = [
            "2024/13/30",  # Invalid month
            "2024/10/32",  # Invalid day
            "1999/10/30",  # Too old
            "2030/10/30",  # Too far in future
        ]
        
        for text in invalid_texts:
            context = ReceiptContext(full_text=text)
            result = self.parser.parse(context)
            # Should either be None or not match the invalid date
            if result:
                assert result.value != text.replace('/', '-')
    
    def test_no_date_found(self):
        """Test handling when no date is found."""
        text = "¥1,500\nコーヒー代\n合計"
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is None
    
    def test_multiple_dates_best_selected(self):
        """Test that best date is selected from multiple candidates."""
        text = """
        Service Date: 2024/10/01
        2024/10/15
        Invoice Date: 2024/10/30
        ¥50,000
        """
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        # Should prefer "Invoice Date" due to higher keyword priority
        assert result.value == "2024-10-30"
    
    def test_shinkansen_date_format(self):
        """Test specialized format like '2024 -10.30'."""
        text = "2024 -10.30\nJR東日本\n新幹線"
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == "2024-10-30"
        assert result.metadata['pattern_type'] == 'shinkansen'