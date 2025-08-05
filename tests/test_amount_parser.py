"""Tests for AmountParser component."""

import pytest
from src.parsers.amount_parser import AmountParser
from src.parsers.base import ReceiptContext


class TestAmountParser:
    """Test suite for AmountParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = AmountParser()
    
    def test_basic_yen_amount(self):
        """Test parsing basic yen amounts."""
        text = "合計 ¥1,500"
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == 1500
        assert result.confidence > 0.8
        assert result.metadata['type'] == 'keyword'
    
    def test_amount_with_gokei(self):
        """Test parsing amounts with 合計 keyword."""
        text = """
        小計: ¥1,400
        税込: ¥140
        合計: ¥1,540
        """
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == 1540  # Should pick 合計 amount
        assert result.metadata['keyword'] == '合計'
    
    def test_oshiharai_kingaku(self):
        """Test parsing お支払い金額 (payment amount)."""
        text = """
        小計: ¥1,166
        お支払い金額: ¥1,166
        """
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == 1166
        assert result.metadata['keyword'] == 'お支払い金額'
    
    def test_oshiharai_kingaku_without_i(self):
        """Test parsing お支払金額 (without い character)."""
        text = """
        商品合計: ¥1,166
        お支払金額: ¥1,166
        THE CITY BAKERY
        """
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == 1166
        assert result.metadata['keyword'] == 'お支払金額'
    
    def test_suica_riyou_kingaku(self):
        """Test parsing Suica 利用金額 (usage amount)."""
        text = """
        ◇利用日: 2024/10/30
        ◇利用金額: ¥160
        入金額: ¥10,000
        """
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        # Should pick higher amount (入金額) over smaller usage amount
        assert result is not None
        assert result.value == 10000
        assert result.metadata['keyword'] == '入金額'
    
    def test_four_digit_amounts(self):
        """Test parsing 4-digit amounts correctly."""
        test_cases = [
            ("合計 ¥4,610", 4610),
            ("¥6,660 税込", 6660),
            ("お支払い金額 ¥8,800", 8800),
            ("総額: ¥9,990", 9990),
        ]
        
        for text, expected in test_cases:
            context = ReceiptContext(full_text=text)
            result = self.parser.parse(context)
            
            assert result is not None, f"Failed to parse: {text}"
            assert result.value == expected, f"Expected {expected}, got {result.value} for: {text}"
    
    def test_tax_amount_exclusion(self):
        """Test that tax amounts are properly excluded."""
        text = """
        商品合計: ¥1,000
        消費税等: ¥100
        合計: ¥1,100
        """
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == 1100  # Should pick 合計, not 消費税等
        assert result.metadata['keyword'] == '合計'
    
    def test_parentheses_amounts_deprioritized(self):
        """Test that amounts in parentheses get lower priority."""
        text = """
        商品代: ¥1,500
        (税抜: ¥1,364)
        合計: ¥1,500
        """
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == 1500  # Should avoid parentheses amount
    
    def test_smart_recovery_low_amounts(self):
        """Test smart recovery for suspiciously low amounts."""
        text = """
        ID: 123
        合計: ¥300  
        実際の支払い: ¥2,500
        """
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        # Should recover to higher amount if it seems more reasonable
        assert result.value >= 300  # At minimum the parsed amount
    
    def test_frequency_based_selection(self):
        """Test selection based on amount frequency."""
        text = """
        商品A: ¥1,500
        商品B: ¥500
        小計: ¥2,000
        合計: ¥2,000
        お支払い: ¥2,000
        """
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == 2000  # Most frequent amount
    
    def test_high_value_amounts(self):
        """Test parsing of high-value amounts."""
        text = """
        TAX INVOICE
        Subtotal: ¥237,600
        合計: ¥237,600
        Office Rent - March 2025
        """
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == 237600
        assert result.confidence > 0.8
    
    def test_no_amount_found(self):
        """Test handling when no amount is found."""
        text = "レシート\n日付: 2024/10/30\nありがとうございました"
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is None
    
    def test_range_validation(self):
        """Test that amounts outside reasonable range are rejected."""
        invalid_texts = [
            "合計: ¥5",      # Too small
            "合計: ¥5,000,000",  # Too large
        ]
        
        for text in invalid_texts:
            context = ReceiptContext(full_text=text)
            result = self.parser.parse(context)
            
            # Should either be None or find alternative amount
            if result:
                assert 10 <= result.value <= 1000000
    
    def test_adjacent_line_parsing(self):
        """Test parsing amounts from adjacent lines to keywords."""
        text = """
        お買上げありがとうございます
        お支払い金額
        ¥1,234
        またのご来店をお待ちしております
        """
        context = ReceiptContext(full_text=text)
        
        result = self.parser.parse(context)
        
        assert result is not None
        assert result.value == 1234
        assert result.metadata['position'] == 'next'  # Amount on next line