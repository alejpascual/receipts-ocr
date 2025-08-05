"""Starbucks receipt template."""

import re
from typing import Optional
from .base_template import BaseTemplate, TemplateMatch, TemplateResult


class StarbucksTemplate(BaseTemplate):
    """Template for Starbucks receipts."""
    
    def __init__(self):
        vendor_patterns = [
            'スターバックス',
            'starbucks',
            'スタバ',
            re.compile(r'スターバックス.*コーヒー', re.IGNORECASE),
            re.compile(r'starbucks.*coffee', re.IGNORECASE),
        ]
        super().__init__("Starbucks", vendor_patterns, confidence_threshold=0.8)
        
        # Starbucks-specific patterns
        self.date_patterns = [
            r'(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})',  # With time
            r'(\d{4})年(\d{1,2})月(\d{1,2})日',  # Japanese date
            r'(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})',     # With time
            r'(\d{4})/(\d{1,2})/(\d{1,2})',     # Slash date
        ]
        
        self.amount_keywords = [
            '合計', 'お支払い金額', 'お支払金額', '税込合計', 'total'
        ]
        
        # Common Starbucks items
        self.drink_items = {
            'coffee': ['ドリップコーヒー', 'drip coffee', 'americano', 'アメリカーノ'],
            'latte': ['ラテ', 'latte', 'カフェラテ'],
            'cappuccino': ['カプチーノ', 'cappuccino'],
            'espresso': ['エスプレッソ', 'espresso'],
            'frappuccino': ['フラペチーノ', 'frappuccino'],
            'tea': ['ティー', 'tea', 'チャイ', 'chai'],
        }
        
        self.food_items = [
            'サンドイッチ', 'sandwich', 'パン', 'bread',
            'ケーキ', 'cake', 'マフィン', 'muffin',
            'クッキー', 'cookie', 'スコーン', 'scone'
        ]
        
        self.sizes = ['short', 'tall', 'grande', 'venti', 'ショート', 'トール', 'グランデ', 'ベンティ']
    
    def parse(self, text: str, match: TemplateMatch) -> TemplateResult:
        """Parse Starbucks receipt with specific logic."""
        # Parse date with time awareness
        date = self._parse_starbucks_date(text)
        
        # Parse amount with Starbucks specific logic
        amount = self._parse_starbucks_amount(text)
        
        # Generate coffee-specific description
        description = self._generate_starbucks_description(text)
        
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
                'chain_type': 'coffee_shop',
                'template_version': '1.0',
                'drinks_ordered': self._extract_drinks(text),
                'order_time': self._extract_time(text)
            }
        )
    
    def _extract_vendor_name(self, text: str, pattern: str) -> str:
        """Extract Starbucks store name with location."""
        # Look for store location
        patterns = [
            r'スターバックス.*?([^\n]+店)',
            r'starbucks.*?([^\n]+store)',
            r'スターバックスコーヒー([^\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                return f"Starbucks {location}"
        
        return "Starbucks"
    
    def _parse_starbucks_date(self, text: str) -> Optional[str]:
        """Parse date with time handling for Starbucks."""
        for pattern in self.date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) >= 3:
                        year, month, day = groups[:3]
                        
                        # Handle 2-digit years
                        if len(year) == 2:
                            year_int = int(year)
                            if year_int <= 30:
                                year = f"20{year}"
                            else:
                                year = f"19{year}"
                        
                        # Validate ranges
                        month_int, day_int = int(month), int(day)
                        if not (1 <= month_int <= 12 and 1 <= day_int <= 31):
                            continue
                        
                        return f"{year}-{month_int:02d}-{day_int:02d}"
                        
                except (ValueError, IndexError):
                    continue
        
        # Fallback to base method
        return self._parse_date_with_patterns(text, self.date_patterns)
    
    def _parse_starbucks_amount(self, text: str) -> Optional[int]:
        """Parse amount with Starbucks specific logic."""
        # First try standard keywords
        amount = self._parse_amount_with_keywords(text, self.amount_keywords)
        if amount:
            return amount
        
        # Starbucks specific patterns
        lines = text.split('\n')
        
        # Look for tax-inclusive total (税込)
        for line in lines:
            if '税込' in line:
                amount_match = re.search(r'¥?\s*([0-9,]+)', line)
                if amount_match:
                    try:
                        amount_str = amount_match.group(1).replace(',', '')
                        amount = int(amount_str)
                        if 200 <= amount <= 3000:  # Typical Starbucks range
                            return amount
                    except ValueError:
                        continue
        
        return None
    
    def _generate_starbucks_description(self, text: str) -> str:
        """Generate coffee-specific description."""
        text_lower = text.lower()
        
        # Check for meeting context
        meeting_indicators = ['会議', '打合せ', 'ミーティング', '商談']
        has_meeting_context = any(ind in text_lower for ind in meeting_indicators)
        
        # Find drink types
        drinks_found = []
        for drink_type, patterns in self.drink_items.items():
            if any(pattern.lower() in text_lower for pattern in patterns):
                drinks_found.append(drink_type)
        
        # Find food items
        food_found = any(item.lower() in text_lower for item in self.food_items)
        
        # Generate description
        if has_meeting_context:
            if drinks_found:
                return f"coffee meeting - {', '.join(drinks_found)}"
            return "coffee meeting"
        else:
            if drinks_found:
                if len(drinks_found) == 1:
                    drink_desc = drinks_found[0]
                else:
                    drink_desc = "coffee drinks"
                
                if food_found:
                    return f"coffee & food - {drink_desc}"
                else:
                    return f"coffee - {drink_desc}"
            elif food_found:
                return "coffee shop - food"
            else:
                return "coffee purchase"
    
    def _extract_drinks(self, text: str) -> list:
        """Extract ordered drinks from receipt."""
        text_lower = text.lower()
        drinks_found = []
        
        for drink_type, patterns in self.drink_items.items():
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    # Look for size information
                    size_info = self._find_size_for_drink(text, pattern)
                    if size_info:
                        drinks_found.append(f"{size_info} {drink_type}")
                    else:
                        drinks_found.append(drink_type)
                    break
        
        return drinks_found
    
    def _find_size_for_drink(self, text: str, drink_pattern: str) -> Optional[str]:
        """Find size information for a specific drink."""
        # Look for size keywords near the drink name
        lines = text.split('\n')
        
        for line in lines:
            if drink_pattern.lower() in line.lower():
                for size in self.sizes:
                    if size.lower() in line.lower():
                        return size.lower()
        
        return None
    
    def _extract_time(self, text: str) -> Optional[str]:
        """Extract order time from receipt."""
        time_match = re.search(r'(\d{1,2}):(\d{2})', text)
        if time_match:
            return time_match.group()
        return None