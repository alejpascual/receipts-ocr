"""Japanese receipt parsing logic for dates, amounts, and vendors."""

import re
import logging
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from dateutil.parser import parse as date_parse

logger = logging.getLogger(__name__)


class JapaneseReceiptParser:
    """Parser for extracting structured data from Japanese receipts."""
    
    def __init__(self):
        self.wareki_map = {
            '令和': 2018,  # Reiwa era started in 2019, but 令和1年 = 2019
            '平成': 1988,  # Heisei era started in 1989, but 平成1年 = 1989
            '昭和': 1925   # Showa era started in 1926, but 昭和1年 = 1926
        }
        
        # Date patterns
        self.date_patterns = [
            r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日',  # YYYY年MM月DD日 (with optional spaces)
            r'(\d{4})年(\d{2})月(\d{2})日',           # YYYY年MMDD日 (no spaces, 2-digit month/day)
            r'(\d{4})/(\d{1,2})/(\d{1,2})',         # YYYY/MM/DD
            r'(\d{4})-(\d{1,2})-(\d{1,2})',         # YYYY-MM-DD
            r'(令和|平成|昭和)(\d+)年\s*(\d{1,2})月\s*(\d{1,2})日',  # 和暦 (with optional spaces)
        ]
        
        # Amount patterns - Japanese specific, prioritized order
        self.amount_patterns = [
            r'合計\s*¥?([0-9,]+)',  # 合計 followed by amount (highest priority)
            r'¥([0-9,]+)\s*(?=\s|$|\n)',   # Clean yen amounts
            r'([0-9,]+)円',  # Numbers with 円
            r'¥([0-9,]+)-?',   # Yen symbol with optional trailing dash  
            r'(?:総計|総合計|お買上げ|税込合計)\s*:?\s*¥?([0-9,]+)',  # Other total keywords
            r'([0-9,]+)(?=\s*(?:合計|総計|総合計|お買上げ))',  # Numbers before total keywords
            r'\b([1-9][0-9]{2,6})\b',  # Standalone numbers (lowest priority)
        ]
        
        # Total keywords (in order of preference) - 合計 is highest priority
        # Include spaced versions for OCR variations
        self.total_keywords = [
            '利用金額', '利用額', '入金額', '領収金額', '合計', '合 計', '総合計', '総 合 計', '税込合計', 'お買上げ', '総計', '税込', '言十', '合'
        ]
        
        # Keywords to avoid (tax, subtotal, change, etc.)
        self.avoid_keywords = [
            '小計', '税抜', '本体価格', '内税', '消費税', '税額', '税金', 
            '対象額', '課税', 'おつり', 'お釣り', '釣り', '預り', 'お預り', '内消費税',
            'ATM手数料', 'ATM利用手数料', '手数料', '振込手数料',
            '入金後残高', '残高', '現在残高', '利用可能残高', 'ポイント残高',
            '年', '月', '日', '時', '分', '秒', '取引番号', '登録番号', '電話番号'
        ]
        
        # Specific patterns for non-amount numeric data
        self.non_amount_patterns = [
            r'登録番号[：:]?\s*([0-9]+)',  # Registration numbers
            r'登録No[：:]?\s*([0-9]+)',    # Registration No
            r'取引番号[：:]?\s*([0-9]+)',  # Transaction numbers
            r'ID[：:]?\s*([0-9]+)',       # ID numbers
            r'番号[：:]?\s*([0-9]+)',     # Generic numbers
            r'TEL[：:]?\s*([0-9-]+)',     # Phone numbers
            r'電話[：:]?\s*([0-9-]+)',    # Phone numbers
            r'Phone[：:]?\s*([0-9-]+)',   # Phone numbers
            r'口座[：:]?\s*([0-9]+)',     # Account numbers
            r'参照[：:]?\s*([0-9]+)',     # Reference numbers
            r'郵便番号[：:]?\s*([0-9-]+)', # Postal codes
            r'〒\s*([0-9-]+)',           # Postal codes with symbol
            r'([0-9]+)時([0-9]+)分',      # Time patterns
            r'([0-9]+):[0-9]+',          # Time patterns with colon
            r'第([0-9]+)号',             # Issue/number patterns
            r'No\.([0-9]+)',            # Number patterns
            r'#([0-9]+)',                # Hash number patterns
        ]
        
        # Date context keywords
        self.date_keywords = [
            '発行', '領収', '日付', '年月日', '取引日'
        ]
        
    def parse_date(self, text: str) -> Optional[str]:
        """
        Extract and normalize date from Japanese text.
        
        Args:
            text: Raw text from OCR
            
        Returns:
            ISO date string (YYYY-MM-DD) or None
        """
        lines = text.split('\n')
        date_candidates = []
        
        for line in lines:
            for pattern in self.date_patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    try:
                        if '令和' in match.group() or '平成' in match.group() or '昭和' in match.group():
                            # Handle 和暦 (Japanese era)
                            era, year, month, day = match.groups()
                            base_year = self.wareki_map.get(era, 0)
                            if base_year:
                                western_year = base_year + int(year)
                                date_str = f"{western_year}-{int(month):02d}-{int(day):02d}"
                            else:
                                continue
                        else:
                            # Handle western dates
                            year, month, day = match.groups()
                            date_str = f"{year}-{int(month):02d}-{int(day):02d}"
                        
                        # Validate date
                        parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
                        
                        # Check if date is reasonable (not too far in future/past)
                        current_year = datetime.now().year
                        if 2000 <= parsed_date.year <= current_year + 1:
                            # Calculate priority based on proximity to date keywords
                            priority = self._calculate_date_priority(line, match.start())
                            date_candidates.append((date_str, priority, line))
                            
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Invalid date found: {match.group()}")
                        continue
        
        if not date_candidates:
            logger.warning("No valid date found in text")
            return None
        
        # Return date with highest priority
        best_date = max(date_candidates, key=lambda x: x[1])
        logger.info(f"Extracted date: {best_date[0]} from line: {best_date[2][:50]}...")
        return best_date[0]
    
    def _calculate_date_priority(self, line: str, match_pos: int) -> int:
        """Calculate priority score for date based on context keywords."""
        priority = 0
        line_lower = line.lower()
        
        for keyword in self.date_keywords:
            if keyword in line:
                # Higher priority if keyword is close to the match
                keyword_pos = line.find(keyword)
                distance = abs(keyword_pos - match_pos)
                priority += max(10 - distance // 5, 1)
        
        return priority
    
    def parse_amount(self, text: str) -> Optional[int]:
        """
        Extract total amount from Japanese text.
        
        Args:
            text: Raw text from OCR
            
        Returns:
            Amount in JPY (integer) or None
        """
        lines = text.split('\n')
        amount_candidates = []
        
        for line_idx, line in enumerate(lines):
            # Look for amounts near total keywords
            for keyword in self.total_keywords:
                if keyword in line:
                    # Search in current line and adjacent lines
                    search_lines = []
                    search_lines.append((line, line_idx, 'current'))
                    if line_idx > 0:
                        search_lines.append((lines[line_idx - 1], line_idx - 1, 'previous'))
                    if line_idx < len(lines) - 1:
                        search_lines.append((lines[line_idx + 1], line_idx + 1, 'next'))
                    
                    for search_line, search_idx, position in search_lines:
                        amounts = self._extract_amounts_from_line(search_line)
                        for amount, confidence in amounts:
                            # ULTRA HIGH priority for specific transaction amounts - with enhanced validation
                            if keyword in ['利用金額', '利用額', '入金額', '領収金額']:
                                # Enhanced validation for ultra-high priority keywords
                                if self._validate_amount_for_keyword(amount, keyword, search_line, line, position):
                                    keyword_priority = 2000  # Highest priority for specific amounts
                                    # Bonus if amount is on same line as keyword
                                    if position == 'current':
                                        keyword_priority += 500
                                    # Higher bonus if amount is on previous line 
                                    elif position == 'previous':
                                        keyword_priority += 100
                                    logger.debug(f"High-priority keyword '{keyword}' validated for amount ¥{amount} (priority: {keyword_priority})")
                                else:
                                    # Failed validation - give low priority instead of ultra-high
                                    keyword_priority = 50  # Low priority
                                    logger.debug(f"High-priority keyword '{keyword}' validation FAILED for amount ¥{amount} in line: {search_line.strip()}")
                            # VERY HIGH priority for 合計 (total) - with or without space
                            elif keyword in ['合計', '合 計']:
                                keyword_priority = 1000  # Extremely high priority
                                # Bonus if amount is on same line as 合計
                                if position == 'current':
                                    keyword_priority += 500
                                # Higher bonus if amount is on previous line (common pattern)
                                elif position == 'previous':
                                    keyword_priority += 100
                            else:
                                keyword_priority = len(self.total_keywords) - self.total_keywords.index(keyword)
                            
                            # Check for avoid keywords in the specific line and also the line before it (for tax amounts)
                            line_has_avoid_keyword = any(avoid_kw in search_line for avoid_kw in self.avoid_keywords)
                            
                            # Also check the line before the amount for tax keywords (common pattern: "内消費税" followed by "¥204")
                            prev_line_has_tax_keyword = False
                            if search_idx > 0:
                                prev_line = lines[search_idx - 1]
                                prev_line_has_tax_keyword = any(tax_kw in prev_line for tax_kw in ['内消費税', '消費税', '税額', '税金'])
                            
                            # IMPORTANT: Also check the line AFTER the amount for avoid keywords (common pattern: "¥200" followed by "お釣り")
                            next_line_has_avoid_keyword = False
                            if search_idx < len(lines) - 1:
                                next_line = lines[search_idx + 1]
                                next_line_has_avoid_keyword = any(avoid_kw in next_line for avoid_kw in self.avoid_keywords)
                            
                            if line_has_avoid_keyword or prev_line_has_tax_keyword or next_line_has_avoid_keyword:
                                # Only penalize if it's not the 合計 line itself (with or without space)
                                if keyword not in ['合計', '合 計'] or position != 'current':
                                    # Determine penalty type and amount
                                    if prev_line_has_tax_keyword:
                                        penalty = 200  # Extra strong penalty for tax amounts
                                        reason = 'tax keyword in previous line'
                                    elif next_line_has_avoid_keyword:
                                        penalty = 150  # Strong penalty for avoid keyword in next line (like change)
                                        reason = 'avoid keyword in next line'
                                    else:
                                        penalty = 50  # Standard penalty for avoid keyword
                                        reason = 'avoid keyword'
                                    
                                    keyword_priority -= penalty
                                    logger.debug(f"Penalizing amount {amount} by {penalty} due to {reason}: {search_line.strip()}")
                            
                            amount_candidates.append((amount, keyword_priority + confidence, search_line))
        
        # Also look for standalone amounts if no keyword-based amounts found
        if not amount_candidates:
            for line in lines:
                amounts = self._extract_amounts_from_line(line)
                for amount, confidence in amounts:
                    amount_candidates.append((amount, confidence, line))
        
        if not amount_candidates:
            logger.warning("No amount found in text")
            return None
        
        # SMART RECOVERY: If the best amount is suspiciously low (≤500), try to find a better one
        best_amount = max(amount_candidates, key=lambda x: x[1])
        
        if best_amount[0] <= 500:
            logger.info(f"Detected suspiciously low amount ¥{best_amount[0]}, trying to find better candidate...")
            
            # Look for amounts that are reasonable multiples or similar patterns
            better_candidates = []
            for amount, priority, line in amount_candidates:
                if amount > 500:  # Only consider amounts > 500
                    # Boost priority for amounts that appear multiple times
                    amount_frequency = sum(1 for a, _, _ in amount_candidates if a == amount)
                    frequency_boost = amount_frequency * 50
                    
                    # Boost priority for amounts near 小計 (subtotal) which is often the real total
                    if '小計' in line:
                        subtotal_boost = 200
                    else:
                        subtotal_boost = 0
                    
                    # Check if this amount appears in multiple contexts (strong signal it's correct)
                    contexts_found = len([l for _, _, l in amount_candidates if f'¥{amount}' in l or f'{amount}円' in l])
                    context_boost = contexts_found * 30
                    
                    adjusted_priority = priority + frequency_boost + subtotal_boost + context_boost
                    better_candidates.append((amount, adjusted_priority, line))
                    logger.debug(f"Better candidate: ¥{amount} (priority: {adjusted_priority}, freq: {amount_frequency}, contexts: {contexts_found})")
            
            if better_candidates:
                # Use the best alternative if it has reasonable priority
                better_amount = max(better_candidates, key=lambda x: x[1])
                if better_amount[1] > best_amount[1] * 0.7:  # If alternative is reasonably competitive
                    logger.info(f"Switching from ¥{best_amount[0]} to ¥{better_amount[0]} (better candidate found)")
                    best_amount = better_amount
        
        logger.info(f"Extracted amount: ¥{best_amount[0]} from line: {best_amount[2][:50]}...")
        return best_amount[0]
    
    def _extract_amounts_from_line(self, line: str) -> List[Tuple[int, int]]:
        """Extract all potential amounts from a line with confidence scores."""
        amounts = []
        
        # First check if this line contains non-amount patterns
        non_amount_numbers = set()
        for pattern in self.non_amount_patterns:
            for match in re.finditer(pattern, line):
                try:
                    # Extract the numeric part and convert to int
                    number_str = match.group(1).replace('-', '').replace(',', '')
                    if number_str.isdigit():
                        non_amount_numbers.add(int(number_str))
                except (ValueError, IndexError):
                    continue
        
        for pattern_idx, pattern in enumerate(self.amount_patterns):
            matches = re.finditer(pattern, line)
            for match in matches:
                try:
                    amount_str = match.group(1)
                    # Remove commas and convert to int
                    amount = int(amount_str.replace(',', ''))
                    
                    # Skip obviously wrong amounts
                    if amount < 10 or amount > 1000000:  # ¥10 to ¥1M reasonable range
                        continue
                    
                    # CRITICAL: Skip if this number was identified as a non-amount
                    if amount in non_amount_numbers:
                        logger.debug(f"Skipping amount {amount} - identified as non-amount number in line: {line.strip()}")
                        continue
                    
                    # Skip years that look like amounts (2020-2030 range)
                    if 2020 <= amount <= 2030:
                        # Check if this number appears in a date context
                        if any(date_indicator in line for date_indicator in ['年', '月', '日', '-', '/', '時', '分']):
                            continue
                    
                    # Additional validation for suspicious standalone numbers
                    if pattern_idx == 6:  # Standalone number pattern (highest risk)
                        # Extra validation for standalone numbers
                        if self._is_suspicious_standalone_number(amount, line, match.start(), match.end()):
                            logger.debug(f"Skipping suspicious standalone number {amount} in line: {line.strip()}")
                            continue
                    
                    # Calculate confidence based on pattern priority and context
                    confidence = 20 - pattern_idx * 2  # Higher priority patterns get higher confidence
                    
                    # VERY high confidence for 合計 pattern (first pattern)
                    if pattern_idx == 0:  # 合計 pattern
                        confidence = 100
                    
                    # Higher confidence if amount has proper formatting
                    if ',' in amount_str and len(amount_str) > 3:
                        confidence += 5
                    
                    # Check if amount is in parentheses (usually negative/change/tax)
                    # Look at the surrounding context in the line, not just the match
                    match_start = match.start()
                    match_end = match.end()
                    before_match = line[:match_start] if match_start > 0 else ""
                    after_match = line[match_end:] if match_end < len(line) else ""
                    
                    if ('(' in before_match or ')' in after_match or 
                        '(' in match.group() or ')' in match.group()):
                        confidence -= 200  # Very strong penalty for parentheses (tax amounts)
                    
                    amounts.append((amount, confidence))
                    
                except (ValueError, IndexError):
                    continue
        
        return amounts
    
    def parse_vendor(self, text: str) -> Optional[str]:
        """
        Extract vendor/store name from receipt text.
        
        Args:
            text: Raw text from OCR
            
        Returns:
            Vendor name string or None
        """
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not lines:
            return None
        
        # Common Japanese business entity patterns
        business_patterns = [
            r'株式会社[^\\n]+',
            r'有限会社[^\\n]+',
            r'[^\\n]*店[^\\n]*',
            r'[^\\n]*支店[^\\n]*',
            r'[^\\n]*堂[^\\n]*',
            r'[^\\n]*屋[^\\n]*',
            r'セブン.*イレブン',
            r'JR[^\\n]*',
            r'スターバックス[^\\n]*',
        ]
        
        # Look for business entity patterns first
        for line in lines[:5]:  # Check first 5 lines
            for pattern in business_patterns:
                match = re.search(pattern, line)
                if match:
                    vendor = match.group().strip()
                    if len(vendor) > 2:  # Reasonable length
                        logger.info(f"Extracted vendor: {vendor}")
                        return vendor
        
        # Fallback: use first non-empty line that looks like a business name
        for line in lines[:3]:
            # Skip lines that look like dates, amounts, or generic text
            if not re.search(r'\\d{4}年|\\d{4}/|\\d{4}-|[0-9,]+円|領収|レシート', line):
                if len(line) > 2 and len(line) < 50:
                    logger.info(f"Extracted vendor (fallback): {line}")
                    return line
        
        logger.warning("No vendor name found")
        return None
    
    def extract_description_context(self, text: str, vendor: Optional[str], amount: Optional[int], category: str = None) -> str:
        """
        Generate concise business description based on category and context patterns.
        
        Args:
            text: Raw text from OCR
            vendor: Extracted vendor name (mostly ignored due to poor quality)
            amount: Extracted amount
            category: Pre-classified category
            
        Returns:
            Concise description string (like "client meeting", "taxi")
        """
        text_lower = text.lower()
        
        # If we have a pre-classified category, use it as primary guide
        if category:
            category_descriptions = self._get_category_description(category, text_lower)
            if category_descriptions:
                return category_descriptions
        
        # Specific pattern matching (regardless of category)
        
        # Transportation patterns
        if any(keyword in text_lower for keyword in ['タクシー', 'taxi']):
            return "taxi"
        elif any(keyword in text_lower for keyword in ['suica', 'pasmo', '電車', '地下鉄', '駅']):
            return "train"
        elif any(keyword in text_lower for keyword in ['バス']):
            return "bus"
        elif any(keyword in text_lower for keyword in ['駐車', 'parking']):
            return "parking"
        elif any(keyword in text_lower for keyword in ['ガソリン', '燃料']):
            return "fuel"
        elif any(keyword in text_lower for keyword in ['高速', '料金', 'toll']):
            return "toll"
        
        # Food/Restaurant patterns
        elif any(keyword in text_lower for keyword in ['居酒屋', 'レストラン', '鍋', '火鍋', '食堂']):
            if any(keyword in text_lower for keyword in ['会議', '打合せ', 'ミーティング', '商談']):
                return "client meeting"
            elif any(keyword in text_lower for keyword in ['懇親会', '歓送迎会', 'チーム']):
                return "team dinner"
            else:
                return "business meal"
        
        # Coffee/Cafe patterns
        elif any(keyword in text_lower for keyword in ['スターバックス', 'ドトール', 'コーヒー', '珈琲', 'カフェ']):
            return "coffee"
        
        # Communications patterns
        elif any(keyword in text_lower for keyword in ['wi-fi', 'wifi', 'インターネット', '通信']):
            return "internet"
        elif any(keyword in text_lower for keyword in ['電話', 'phone', 'tel']):
            return "phone"
        
        # Office supplies patterns
        elif any(keyword in text_lower for keyword in ['文具', 'ペン', 'ノート', '用紙']):
            return "office supplies"
        elif any(keyword in text_lower for keyword in ['pc', 'パソコン', 'プリンタ', 'printer']):
            return "equipment"
        
        # Utilities patterns  
        elif any(keyword in text_lower for keyword in ['電力', '電気']):
            return "electricity"
        elif any(keyword in text_lower for keyword in ['ガス']):
            return "gas"
        elif any(keyword in text_lower for keyword in ['水道']):
            return "water"
        
        # Entertainment patterns
        elif any(keyword in text_lower for keyword in ['映画', 'movie']):
            return "movie"
        elif any(keyword in text_lower for keyword in ['カラオケ']):
            return "karaoke"
        
        # Hotel patterns
        elif any(keyword in text_lower for keyword in ['ホテル', 'hotel', '宿泊']):
            return "hotel"
        
        # Professional services patterns
        elif any(keyword in text_lower for keyword in ['弁護士', 'lawyer']):
            return "legal fees"
        elif any(keyword in text_lower for keyword in ['税理士', 'accountant']):
            return "accounting"
        elif any(keyword in text_lower for keyword in ['コンサル']):
            return "consulting"
        
        # Advertising patterns
        elif any(keyword in text_lower for keyword in ['google', 'facebook', 'meta', '広告']):
            return "advertising"
        
        # Meeting context
        elif any(keyword in text_lower for keyword in ['会議', '打合せ', 'ミーティング', '商談']):
            return "business meeting"
        
        # Default fallback based on category if no specific patterns found
        return "business expense"
    
    def _get_category_description(self, category: str, text_lower: str) -> Optional[str]:
        """
        Get appropriate description based on category and context.
        
        Args:
            category: The classified category
            text_lower: Lowercase text for additional context
            
        Returns:
            Category-appropriate description or None
        """
        category_mappings = {
            'travel': self._get_travel_description(text_lower),
            'entertainment': self._get_entertainment_description(text_lower),
            'communications (phone, internet, postage)': self._get_communications_description(text_lower),
            'meetings': 'client meeting',
            'Office supplies': 'office supplies',
            'Equipment': 'office equipment',
            'Utilities': self._get_utilities_description(text_lower),
            'Professional fees': 'professional services',
            'outsourced fees': 'consulting fees',
            'Rent': 'office rent',
            'Advertising': 'advertising expense',
            'Memberships': 'membership fees',
            'Other': 'business expense'
        }
        
        return category_mappings.get(category, None)
    
    def _get_travel_description(self, text_lower: str) -> str:
        """Get specific travel description based on context."""
        if any(keyword in text_lower for keyword in ['タクシー', 'taxi']):
            return "taxi"
        elif any(keyword in text_lower for keyword in ['電車', '地下鉄', 'suica', 'pasmo', '駅']):
            return "train fare"
        elif any(keyword in text_lower for keyword in ['バス']):
            return "bus fare"
        elif any(keyword in text_lower for keyword in ['ガソリン', '燃料']):
            return "fuel"
        elif any(keyword in text_lower for keyword in ['駐車']):
            return "parking"
        elif any(keyword in text_lower for keyword in ['ホテル', 'hotel', '宿泊']):
            return "hotel"
        elif any(keyword in text_lower for keyword in ['居酒屋', 'レストラン', '鍋', '食堂']):
            return "business meal (out of town)"
        elif any(keyword in text_lower for keyword in ['高速', 'toll']):
            return "toll"
        else:
            return "travel expense"
    
    def _get_entertainment_description(self, text_lower: str) -> str:
        """Get specific entertainment description based on context."""
        if any(keyword in text_lower for keyword in ['居酒屋']):
            return "business dinner"
        elif any(keyword in text_lower for keyword in ['レストラン', '鍋', '食堂']):
            return "business meal"
        elif any(keyword in text_lower for keyword in ['スターバックス', 'ドトール']):
            return "coffee meeting"
        elif any(keyword in text_lower for keyword in ['コーヒー', '珈琲', 'カフェ']):
            return "coffee"
        elif any(keyword in text_lower for keyword in ['映画']):
            return "movie"
        elif any(keyword in text_lower for keyword in ['カラオケ']):
            return "karaoke"
        elif any(keyword in text_lower for keyword in ['会議', '打合せ', 'ミーティング']):
            return "client meeting"
        else:
            return "client entertainment"
    
    def _get_communications_description(self, text_lower: str) -> str:
        """Get specific communications description based on context."""
        if any(keyword in text_lower for keyword in ['インターネット', 'wi-fi', 'wifi']):
            return "internet service"
        elif any(keyword in text_lower for keyword in ['電話', 'phone']):
            return "phone bill"
        else:
            return "communications"
    
    def _get_utilities_description(self, text_lower: str) -> str:
        """Get specific utilities description based on context."""
        if any(keyword in text_lower for keyword in ['電力', '電気']):
            return "electricity bill"
        elif any(keyword in text_lower for keyword in ['ガス']):
            return "gas bill"
        elif any(keyword in text_lower for keyword in ['水道']):
            return "water bill"
        else:
            return "utility bill"
    
    def _extract_context_keywords(self, line: str) -> List[str]:
        """Extract meaningful keywords from a line for description."""
        # Common product/service keywords
        product_keywords = [
            'ドリンク', 'コーヒー', '珈琲', '弁当', 'パン', 'お茶',
            '交通', '乗車', 'タクシー', 'バス', '電車',
            '文具', '用紙', 'ペン', 'ノート',
            'ガソリン', '燃料', '駐車',
            '会議', '打合せ', '懇親会'
        ]
        
        found_keywords = []
        for keyword in product_keywords:
            if keyword in line:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def _is_suspicious_standalone_number(self, amount: int, line: str, start_pos: int, end_pos: int) -> bool:
        """Check if a standalone number is suspicious (likely not an amount)."""
        
        # Check context around the number
        before_context = line[:start_pos].lower()
        after_context = line[end_pos:].lower()
        full_context = line.lower()
        
        # Suspicious if preceded by these patterns
        suspicious_prefixes = [
            '登録', 'id', 'no.', 'no:', 'tel', '電話', 'phone', '番号', 
            '口座', '取引', '参照', '郵便', '〒', '#', '第'
        ]
        
        # Suspicious if followed by these patterns
        suspicious_suffixes = [
            '号', '番', 'id', 'no', 'tel', '時', '分', '秒'
        ]
        
        # Check prefixes (within 10 characters before)
        for prefix in suspicious_prefixes:
            if prefix in before_context[-10:]:
                return True
        
        # Check suffixes (within 5 characters after)
        for suffix in suspicious_suffixes:
            if suffix in after_context[:5]:
                return True
        
        # Suspicious if the line contains registration/ID indicators
        id_indicators = ['登録番号', '取引番号', 'registration', 'id:', 'tel:', '電話番号']
        if any(indicator in full_context for indicator in id_indicators):
            return True
        
        # Suspicious if it's a small number (< 1000) without clear amount context
        if amount < 1000:
            # Allow small amounts only if they have clear amount context
            amount_context = ['円', '¥', '合計', '税込', '料金', '代金', '金額']
            if not any(context in full_context for context in amount_context):
                return True
        
        # Suspicious if it looks like a year (but outside 2020-2030 range)
        if 1900 <= amount <= 2100:
            # Check if it appears in a date-like context
            if any(date_indicator in full_context for date_indicator in ['年', '月', '日']):
                return True
        
        return False
    
    def _validate_amount_for_keyword(self, amount: int, keyword: str, amount_line: str, keyword_line: str, position: str) -> bool:
        """Validate that an amount is genuinely associated with a high-priority keyword."""
        
        amount_line_lower = amount_line.lower()
        keyword_line_lower = keyword_line.lower()
        
        # For ultra-high priority keywords, apply strict validation
        if keyword in ['利用金額', '利用額', '入金額', '領収金額']:
            
            # 1. Check if amount appears in proper format near keyword
            if position == 'current':
                # On same line - check proximity and format
                keyword_pos = keyword_line.find(keyword)
                amount_str = str(amount)
                formatted_amounts = [f'¥{amount}', f'{amount}円', f'{amount:,}', f'¥{amount:,}']
                
                # Look for the amount in various formats near the keyword
                found_proper_format = False
                for fmt_amount in formatted_amounts:
                    amount_pos = amount_line.find(fmt_amount)
                    if amount_pos >= 0:
                        # Check if amount is within reasonable distance of keyword (within 50 characters)
                        if abs(amount_pos - keyword_pos) <= 50:
                            found_proper_format = True
                            break
                
                if not found_proper_format:
                    # Check if at least the raw number appears near keyword with colon/space
                    keyword_context = amount_line[max(0, keyword_pos):keyword_pos + len(keyword) + 30]
                    if not any(sep in keyword_context for sep in [':', '：', ' ']) or str(amount) not in keyword_context:
                        logger.debug(f"Amount {amount} not in proper format near keyword '{keyword}' on same line")
                        return False
            
            # 2. Reject if amount line contains suspicious indicators
            suspicious_indicators = ['登録番号', '取引番号', 'id:', 'tel:', '電話', '番号']
            if any(indicator in amount_line_lower for indicator in suspicious_indicators):
                logger.debug(f"Amount {amount} rejected - suspicious indicators in line: {amount_line.strip()}")
                return False
            
            # 3. Size validation - amounts for these keywords should typically be reasonable
            if amount < 100:  # Very small amounts are suspicious for transaction totals
                # Allow small amounts only if they appear in very clear format
                if position != 'current' or not any(fmt in amount_line for fmt in [f'¥{amount}', f'{amount}円']):
                    logger.debug(f"Amount {amount} rejected - too small and not in clear format")
                    return False
            
            # 4. For amounts on adjacent lines, ensure no competing context
            if position in ['previous', 'next']:
                # Check if the amount line has its own keyword that would compete
                competing_keywords = ['小計', '税抜', '消費税', '手数料', 'お釣り', '残高']
                if any(comp_kw in amount_line for comp_kw in competing_keywords):
                    logger.debug(f"Amount {amount} rejected - competing keyword in amount line: {amount_line.strip()}")
                    return False
                
                # For adjacent lines, prefer formatted amounts
                if not any(fmt in amount_line for fmt in [f'¥{amount}', f'{amount}円', f'{amount:,}']):
                    # Raw numbers on adjacent lines are risky - apply extra validation
                    if amount < 1000:  # Extra suspicious for small raw numbers
                        logger.debug(f"Amount {amount} rejected - raw small number on adjacent line")
                        return False
        
        return True