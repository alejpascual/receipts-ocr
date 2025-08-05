"""Tests for receipt template system."""

import pytest
from src.templates.template_engine import TemplateEngine
from src.templates.seven_eleven import SevenElevenTemplate
from src.templates.starbucks import StarbucksTemplate


class TestTemplateEngine:
    """Test suite for TemplateEngine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = TemplateEngine()
    
    def test_seven_eleven_template_matching(self):
        """Test Seven-Eleven template matching."""
        receipt_text = """
        セブンイレブン千代田店
        2024年10月30日 14:30
        
        ドリップコーヒー    ¥110
        おにぎり           ¥130
        
        合計              ¥240
        """
        
        result = self.engine.parse_with_template(receipt_text)
        
        assert result is not None
        assert result.template_name == "SevenEleven"
        assert result.date == "2024-10-30"
        assert result.amount == 240
        assert "Seven-Eleven" in result.vendor
        assert "convenience store" in result.description
        assert result.confidence > 0.8
    
    def test_starbucks_template_matching(self):
        """Test Starbucks template matching."""
        receipt_text = """
        スターバックスコーヒー渋谷店
        2024年10月30日 15:45
        
        ドリップコーヒー トール
        アメリカーノ グランデ
        
        合計 ¥650
        お支払い金額 ¥650
        """
        
        result = self.engine.parse_with_template(receipt_text)
        
        assert result is not None
        assert result.template_name == "Starbucks"
        assert result.date == "2024-10-30"
        assert result.amount == 650
        assert "Starbucks" in result.vendor
        assert "coffee" in result.description
        assert len(result.metadata['drinks_ordered']) > 0
    
    def test_no_template_match(self):
        """Test handling when no template matches."""
        receipt_text = """
        未知の店舗
        2024年10月30日
        商品A: ¥500
        合計: ¥500
        """
        
        result = self.engine.parse_with_template(receipt_text)
        
        assert result is None  # No template should match unknown store
    
    def test_template_priority(self):
        """Test that best matching template is selected."""
        # Text that could match multiple patterns
        receipt_text = """
        セブンイレブン内スターバックス
        2024年10月30日
        コーヒー ¥300
        合計 ¥300
        """
        
        result = self.engine.parse_with_template(receipt_text)
        
        assert result is not None
        # Should match based on higher confidence, likely Seven-Eleven due to first occurrence
        assert result.template_name in ["SevenEleven", "Starbucks"]
    
    def test_template_stats(self):
        """Test template statistics."""
        stats = self.engine.get_template_stats()
        
        assert stats['total_templates'] >= 2
        assert 'SevenEleven' in stats['template_names']
        assert 'Starbucks' in stats['template_names']
        assert stats['supported_vendors'] > 0
        assert 0 <= stats['average_confidence_threshold'] <= 1


class TestSevenElevenTemplate:
    """Test suite for SevenElevenTemplate."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.template = SevenElevenTemplate()
    
    def test_vendor_pattern_matching(self):
        """Test various Seven-Eleven name patterns."""
        test_patterns = [
            "セブンイレブン千代田店",
            "7-ELEVEN 渋谷店",
            "seven-eleven shibuya",
            "セブン-イレブン"
        ]
        
        for pattern in test_patterns:
            match = self.template.matches(pattern)
            assert match is not None, f"Failed to match: {pattern}"
            assert match.confidence >= 0.8
    
    def test_amount_parsing(self):
        """Test Seven-Eleven specific amount parsing."""
        receipt_text = """
        セブンイレブン
        コーヒー ¥110
        パン ¥150
        合計 ¥260
        """
        
        match = self.template.matches(receipt_text)
        result = self.template.parse(receipt_text, match)
        
        assert result.amount == 260
    
    def test_description_generation(self):
        """Test Seven-Eleven description generation."""
        test_cases = [
            ("コーヒー ¥110", "coffee"),
            ("おにぎり ¥130", "food"),
            ("お茶 ¥100", "drinks"),
            ("コーヒー\nおにぎり", "coffee, food")
        ]
        
        for text, expected_category in test_cases:
            full_text = f"セブンイレブン\n{text}\n合計 ¥200"
            match = self.template.matches(full_text)
            result = self.template.parse(full_text, match)
            
            assert expected_category in result.description


class TestStarbucksTemplate:
    """Test suite for StarbucksTemplate."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.template = StarbucksTemplate()
    
    def test_vendor_pattern_matching(self):
        """Test various Starbucks name patterns."""
        test_patterns = [
            "スターバックスコーヒー渋谷店",
            "Starbucks Coffee Shibuya",
            "スタバ渋谷",
            "STARBUCKS RESERVE"
        ]
        
        for pattern in test_patterns:
            match = self.template.matches(pattern)
            assert match is not None, f"Failed to match: {pattern}"
            assert match.confidence >= 0.8
    
    def test_drink_extraction(self):
        """Test drink extraction from Starbucks receipts."""
        receipt_text = """
        スターバックス
        ドリップコーヒー トール
        カフェラテ グランデ
        合計 ¥650
        """
        
        match = self.template.matches(receipt_text)
        result = self.template.parse(receipt_text, match)
        
        drinks = result.metadata['drinks_ordered']
        assert len(drinks) >= 1
        assert any('coffee' in drink for drink in drinks)
    
    def test_meeting_context_detection(self):
        """Test meeting context detection."""
        receipt_text = """
        スターバックス
        会議用ドリンク
        アメリカーノ トール
        合計 ¥300
        """
        
        match = self.template.matches(receipt_text)
        result = self.template.parse(receipt_text, match)
        
        assert "meeting" in result.description
    
    def test_time_extraction(self):
        """Test time extraction from receipts."""
        receipt_text = """
        スターバックス
        2024年10月30日 15:30
        コーヒー ¥300
        合計 ¥300
        """
        
        match = self.template.matches(receipt_text)
        result = self.template.parse(receipt_text, match)
        
        assert result.metadata['order_time'] == "15:30"


class TestTemplateIntegration:
    """Integration tests for template system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = TemplateEngine()
    
    def test_template_coverage(self):
        """Test template coverage with sample receipts."""
        sample_receipts = [
            """セブンイレブン\n2024/10/30\nコーヒー ¥110\n合計 ¥110""",
            """スターバックス\n2024/10/30\nラテ ¥400\n合計 ¥400""",
            """未知の店\n2024/10/30\n商品 ¥500\n合計 ¥500""",  # Should not match
        ]
        
        coverage = self.engine.test_template_coverage(sample_receipts)
        
        assert coverage['total_tests'] == 3
        assert coverage['matched'] >= 2  # At least Seven-Eleven and Starbucks
        assert coverage['coverage_percentage'] >= 66  # At least 2/3 coverage
        assert 'SevenEleven' in coverage['template_usage']
        assert 'Starbucks' in coverage['template_usage']
    
    def test_fallback_to_general_parsing(self):
        """Test that unknown receipts fall back to general parsing."""
        unknown_receipt = """
        謎の店舗
        2024年10月30日
        商品X: ¥1000
        合計: ¥1000
        """
        
        # Template parsing should return None
        template_result = self.engine.parse_with_template(unknown_receipt)
        assert template_result is None
        
        # General parsing should still work (tested in integration tests)