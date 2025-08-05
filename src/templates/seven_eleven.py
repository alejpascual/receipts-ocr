"""Seven-Eleven receipt template."""

import re
from typing import Optional
from .base_template import BaseTemplate, TemplateMatch, TemplateResult


class SevenElevenTemplate(BaseTemplate):
    """Template for Seven-Eleven receipts."""
    
    def __init__(self):
        vendor_patterns = [
            'セブンイレブン',
            'seven-eleven', 
            'seven eleven',
            '7-eleven',
            '7-イレブン',
            re.compile(r'セブン.*イレブン', re.IGNORECASE),
        ]
        super().__init__("SevenEleven", vendor_patterns, confidence_threshold=0.8)
        
        # SevenEleven-specific patterns
        self.date_patterns = [
            r'(\d{4})年(\d{1,2})月(\d{1,2})日',  # Japanese date
            r'(\d{4})/(\d{1,2})/(\d{1,2})',     # Slash date
            r'(\d{2})/(\d{1,2})/(\d{1,2})',     # Short slash date
        ]
        
        self.amount_keywords = [
            '合計', '総計', 'お支払い金額', 'お支払金額', '税込'
        ]
        
        # Common Seven-Eleven items for context
        self.common_items = [
            'コーヒー', 'coffee', 'ドリップ',
            'おにぎり', 'onigiri', 
            'お茶', '茶', 'tea',
            'パン', 'bread', 'サンド',
            'お弁当', '弁当', 'bento'
        ]
    
    def parse(self, text: str, match: TemplateMatch) -> TemplateResult:
        """Parse Seven-Eleven receipt with specific logic."""
        # Parse date with template patterns
        date = self._parse_date_with_patterns(text, self.date_patterns)
        
        # Parse amount with Seven-Eleven specific logic
        amount = self._parse_seven_eleven_amount(text)
        
        # Generate description
        description = self._generate_seven_eleven_description(text)
        
        # Calculate confidence
        parsed_fields = {'date': date, 'amount': amount, 'vendor': match.vendor}
        confidence = self._calculate_confidence(parsed_fields, match.confidence)
        
        return TemplateResult(
            date=date,
            amount=amount,
            vendor=match.vendor,
            description=description,
            confidence=confidence,
            template_name=self.name,
            metadata={
                'chain_type': 'convenience_store',
                'template_version': '1.0',
                'matched_items': self._find_common_items(text)
            }
        )
    
    def _extract_vendor_name(self, text: str, pattern: str) -> str:
        """Extract Seven-Eleven store name with location."""
        # Look for store location in text
        location_match = re.search(r'セブンイレブン([^\n]+)', text)
        if location_match:
            location = location_match.group(1).strip()
            return f"Seven-Eleven {location}"
        
        return "Seven-Eleven"
    
    def _parse_seven_eleven_amount(self, text: str) -> Optional[int]:
        """Parse amount with Seven-Eleven specific logic."""
        # First try standard keywords
        amount = self._parse_amount_with_keywords(text, self.amount_keywords)
        if amount:
            return amount
        
        # Seven-Eleven specific patterns
        lines = text.split('\n')
        
        # Look for amount patterns specific to Seven-Eleven receipts
        for line in lines:
            # Pattern: ¥XXX at end of line (common in Seven-Eleven)
            if re.match(r'.*¥\s*([0-9,]+)\s*$', line.strip()):
                match = re.search(r'¥\s*([0-9,]+)\s*$', line)
                if match:
                    try:
                        amount_str = match.group(1).replace(',', '')
                        amount = int(amount_str)
                        if 50 <= amount <= 5000:  # Typical Seven-Eleven range
                            return amount
                    except ValueError:
                        continue
        
        return None
    
    def _generate_seven_eleven_description(self, text: str) -> str:
        """Generate description based on Seven-Eleven items."""
        text_lower = text.lower()
        found_items = []
        
        # Check for common Seven-Eleven items
        item_categories = {
            'coffee': ['コーヒー', 'coffee', 'ドリップ', 'カフェ'],
            'food': ['おにぎり', 'お弁当', '弁当', 'パン', 'サンド'],
            'drinks': ['お茶', '茶', 'tea', 'ドリンク', '飲み物'],
            'snacks': ['スナック', 'チップス', 'お菓子'],
        }
        
        for category, items in item_categories.items():
            if any(item in text_lower for item in items):
                found_items.append(category)
        
        if found_items:
            if len(found_items) == 1:
                return f"convenience store - {found_items[0]}"
            else:
                return f"convenience store - {', '.join(found_items)}"
        
        return "convenience store purchase"
    
    def _find_common_items(self, text: str) -> list:
        """Find common Seven-Eleven items in text."""
        text_lower = text.lower()
        found_items = []
        
        for item in self.common_items:
            if item.lower() in text_lower:
                found_items.append(item)
        
        return found_items