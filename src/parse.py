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
            r'(\d{2})/(\d{1,2})/(\d{1,2})',         # YY/MM/DD (IKEA format)
            r'(令和|平成|昭和)(\d+)年\s*(\d{1,2})月\s*(\d{1,2})日',  # 和暦 (with optional spaces)
        ]
        
        # Amount patterns - Japanese specific, prioritized order
        # Enhanced to handle OCR spacing issues like "1, 738円" → "1,738円"
        self.amount_patterns = [
            r'合計\s*¥?([0-9,\s]+)',  # 合計 followed by amount (highest priority) - with space tolerance
            r'¥\s*([0-9,\s]+)\s*(?=\s|$|\n|円)',   # Clean yen amounts with space tolerance
            r'([0-9,\s]+)円',  # Numbers with 円 - with space tolerance
            r'¥\s*([0-9,\s]+)-?',   # Yen symbol with optional trailing dash - with space tolerance
            r'(?:総計|総合計|お買上げ|税込合計)\s*:?\s*¥?\s*([0-9,\s]+)',  # Other total keywords - with space tolerance
            r'([0-9,\s]+)(?=\s*(?:合計|総計|総合計|お買上げ))',  # Numbers before total keywords - with space tolerance
            r'\b([1-9][0-9\s]{2,8})\b',  # Standalone numbers (lowest priority) - with space tolerance
        ]
        
        # Total keywords (in order of preference) - 合計 is highest priority
        # Include spaced versions for OCR variations
        self.total_keywords = [
            '利用金額', '利用額', '入金額', '領収金額', '合計', '合 計', '総合計', '総 合 計', '税込合計', 'お買上げ', '総計', '税込', '言十', '合'
        ]
        
        # Keywords to avoid (tax, subtotal, change, etc.)
        self.avoid_keywords = [
            '小計', '税抜', '本体価格', '内税', '消費税', '税額', '税金', 
            '対象額', '課税', 'おつり', 'お釣り', '釣り', '預り', 'お預り', 
            '内消費税', '内消費費税', '内消費費税等', '消費費税', '消費税等',
            '税込計', '税込合計', '軽減税率',
            'ATM手数料', 'ATM利用手数料', '手数料', '振込手数料',
            '入金後残高', '残高', '現在残高', '利用可能残高', 'ポイント残高',
            '年', '月', '日', '時', '分', '秒', '取引番号', '登録番号', '電話番号'
        ]
        
        # CRITICAL: Tax context patterns - these indicate tax amounts that should never be the main total
        self.tax_context_patterns = [
            r'消費税等.*¥?([0-9,\s]+)',  # 消費税等 followed by amount
            r'([0-9,\s]+).*消費税等',    # Amount followed by 消費税等
            r'10%.*¥?([0-9,\s]+)',      # 10% tax rate followed by amount
            r'([0-9,\s]+).*10%',        # Amount followed by 10% tax rate
            r'税額.*¥?([0-9,\s]+)',     # 税額 followed by amount
            r'([0-9,\s]+).*税額',       # Amount followed by 税額
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
            # ENHANCED: Better phone number detection for patterns like "TEL 080-3917-8881"
            r'TEL\s*[0-9-]*([0-9]+)(?:\s*-|$)',  # Numbers at end of phone numbers after TEL
            r'電話\s*[0-9-]*([0-9]+)(?:\s*-|$)', # Numbers at end of phone numbers after 電話
            r'([0-9]{3})-([0-9]{4})-([0-9]{4})', # Standard phone format like 080-3917-8881
            r'([0-9]{4})-([0-9]{4})',    # Partial phone numbers like 3917-8881
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
        
        # Date context keywords - prioritize invoice dates over service period dates
        self.date_keywords = [
            # High priority - actual transaction/invoice dates
            'invoice date', 'invoice', '発行', '領収', '日付', '年月日', '取引日',
            # Lower priority - service/due dates
            'due date', 'to date', 'from date'
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
                            
                            # Handle YY/MM/DD format (convert 2-digit year to 4-digit)
                            if len(year) == 2:
                                year_int = int(year)
                                # Assume years 00-30 are 2000s, 31-99 are 1900s
                                if year_int <= 30:
                                    year = f"20{year}"
                                else:
                                    year = f"19{year}"
                            
                            date_str = f"{year}-{int(month):02d}-{int(day):02d}"
                        
                        # Validate date
                        parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
                        
                        # Check if date is reasonable (not too far in future/past)
                        current_year = datetime.now().year
                        if 2000 <= parsed_date.year <= current_year + 1:
                            # Calculate priority based on proximity to date keywords (including adjacent lines)
                            line_idx = lines.index(line) if line in lines else 0
                            priority = self._calculate_date_priority_with_context(lines, line_idx, match.start())
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
        
        # High priority keywords for actual transaction dates
        high_priority_keywords = ['invoice date', 'invoice', '発行', '領収', '日付', '年月日', '取引日']
        
        for keyword in self.date_keywords:
            if keyword in line_lower:
                # Calculate base priority based on keyword type
                if keyword in high_priority_keywords:
                    base_priority = 50  # Very high priority for invoice/transaction dates
                else:
                    base_priority = 10  # Lower priority for service period/due dates
                
                # Higher priority if keyword is close to the match
                keyword_pos = line_lower.find(keyword)
                distance = abs(keyword_pos - match_pos)
                priority += base_priority - min(distance // 5, base_priority - 1)
        
        return priority
    
    def _calculate_date_priority_with_context(self, lines: List[str], line_idx: int, match_pos: int) -> int:
        """Calculate priority score for date including adjacent lines for keywords."""
        priority = 0
        
        # Check current line
        priority += self._calculate_date_priority(lines[line_idx], match_pos)
        
        # Check previous lines (keywords often appear before dates in invoices)
        for i in range(max(0, line_idx - 2), line_idx):
            line_priority = self._calculate_date_priority(lines[i], 0)
            # Reduce priority for distance from date line
            priority += line_priority * (0.8 ** (line_idx - i))
        
        # Check next lines (less common but possible)
        for i in range(line_idx + 1, min(len(lines), line_idx + 2)):
            line_priority = self._calculate_date_priority(lines[i], 0)
            # Reduce priority for distance from date line
            priority += line_priority * (0.6 ** (i - line_idx))
        
        return int(priority)
    
    def _is_likely_handwritten_receipt_with_missing_amount(self, text: str) -> bool:
        """
        Detect if this appears to be a handwritten receipt where OCR failed to detect the amount.
        
        Indicators:
        - Has receipt structure (tax fields, etc.)
        - Has valid business name 
        - Has valid date
        - Missing amount despite receipt structure
        """
        text_lower = text.lower()
        
        # Check for receipt structure indicators
        receipt_structure_indicators = [
            '領収証', '領収', '税抜金額', '消費税額', '内訳', '上記正に領収',
            'receipt', 'tax', 'total', 'amount'
        ]
        
        has_receipt_structure = any(indicator in text_lower for indicator in receipt_structure_indicators)
        
        # Check for business indicators
        has_business_name = any(business_type in text_lower for business_type in [
            'curry', 'restaurant', 'cafe', 'カフェ', 'レストラン', '食堂', '居酒屋'
        ])
        
        # Check for date (handwritten receipts often have readable dates)
        has_date = bool(self.parse_date(text))
        
        # Check for common handwritten receipt patterns
        handwritten_indicators = [
            '様',  # Common on handwritten receipts
            '但',  # Item description prefix on handwritten receipts
            'tel',  # Phone numbers are often printed even on handwritten receipts
        ]
        
        has_handwritten_pattern = any(indicator in text_lower for indicator in handwritten_indicators)
        
        # If we have receipt structure, business context, date, and handwritten patterns
        # but no amount, it's likely a handwritten receipt with OCR issues
        if has_receipt_structure and has_date and (has_business_name or has_handwritten_pattern):
            logger.info("Detected likely handwritten receipt with missing amount - flagging for manual review with context")
            return True
            
        return False
    
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
                            # CRITICAL: Check if this amount is a tax amount that should be excluded
                            if self._is_tax_amount(amount, search_line, lines, search_idx):
                                logger.debug(f"Excluding tax amount ¥{amount} from line: {search_line.strip()}")
                                continue
                            
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
                                # CRITICAL FIX: For 合計, prefer amounts on previous lines over same line
                                # This handles cases where tax appears on same line as 合計
                                if position == 'previous':
                                    keyword_priority = 6000  # ULTRA high priority for previous line
                                elif position == 'current':
                                    # Check if this could be a tax amount by examining the full line
                                    if self._could_be_tax_on_total_line(amount, search_line):
                                        keyword_priority = 1000  # Lower priority for potential tax on 合計 line
                                        logger.debug(f"合計 amount ¥{amount} might be tax - giving lower priority")
                                    else:
                                        keyword_priority = 5000  # Standard high priority
                                else:
                                    # CRITICAL: Check if amount after 合計 could be tax (common pattern)
                                    # Look at the line after the amount for tax indicators
                                    next_line_has_tax = False
                                    if search_idx < len(lines) - 1:
                                        next_line = lines[search_idx + 1]
                                        next_line_has_tax = any(tax_ind in next_line for tax_ind in ['消費税', '税額', '10%', '8%'])
                                    
                                    if next_line_has_tax or self._is_tax_amount(amount, search_line, lines, search_idx):
                                        keyword_priority = 1000  # Lower priority for potential tax after 合計
                                        logger.debug(f"合計 next line amount ¥{amount} might be tax - giving lower priority")
                                    else:
                                        keyword_priority = 4000  # High priority for next line
                            # HIGH priority for other total keywords
                            elif keyword in ['総合計', '総 合 計', '税込合計']:
                                keyword_priority = 4000  # Very high priority
                                if position == 'current':
                                    keyword_priority += 800
                                elif position == 'previous':
                                    keyword_priority += 400
                            else:
                                # Standard priority for other keywords, but still boosted to beat frequency
                                base_priority = len(self.total_keywords) - self.total_keywords.index(keyword)
                                keyword_priority = base_priority * 100  # Boost by 100x to compete with frequency
                            
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
        
        # ENHANCED: Even if we found keyword-based amounts, also add standalone amounts for frequency analysis
        # This helps when the main amount appears multiple times but not always near keywords
        all_standalone_amounts = []
        for line in lines:
            amounts = self._extract_amounts_from_line(line)
            for amount, confidence in amounts:
                all_standalone_amounts.append((amount, confidence, line))
        
        # For each standalone amount, check if it appears frequently and boost its priority
        # But EXCLUDE tax amounts from frequency analysis to prevent tax amounts from winning
        standalone_frequency = {}
        non_tax_amounts = []
        
        for amount, confidence, line in all_standalone_amounts:
            line_idx = None
            # Find the line index for tax detection
            for i, text_line in enumerate(lines):
                if text_line.strip() == line.strip():
                    line_idx = i
                    break
            
            # Check if this amount is from a tax line - if so, don't count it in frequency
            if line_idx is not None and not self._is_tax_amount(amount, line, lines, line_idx):
                standalone_frequency[amount] = standalone_frequency.get(amount, 0) + 1
                non_tax_amounts.append((amount, confidence, line))
            else:
                logger.debug(f"Excluding tax amount ¥{amount} from frequency analysis: {line.strip()}")
        
        # Add high-frequency NON-TAX amounts to candidates with boosted priority
        for amount, confidence, line in non_tax_amounts:
            frequency = standalone_frequency.get(amount, 0)
            if frequency >= 2:  # Lowered from 3 since we're excluding tax amounts now
                # Calculate a very high priority based on frequency - this should usually win
                frequency_priority = confidence + (frequency * 300)  # 300 points per occurrence
                
                # EXTRA BOOST for amounts with total indicators (税込, -, etc.)
                total_indicators = ['税込', '合計', '総計', '小計']
                if any(indicator in line for indicator in total_indicators) or line.strip().endswith('-'):
                    frequency_priority += 500  # Major boost for total context
                    logger.debug(f"Major boost for total context: {line.strip()}")
                
                # Always add frequent amounts, even if they exist from keyword search
                # This gives them a chance to override any penalties from avoid keywords
                amount_candidates.append((amount, frequency_priority, line))
                logger.debug(f"Added high-frequency non-tax amount ¥{amount} (appears {frequency} times, priority: {frequency_priority})")
        
        if not amount_candidates:
            # Check if this might be a handwritten receipt with missing OCR
            if self._is_likely_handwritten_receipt_with_missing_amount(text):
                logger.warning("Potential handwritten receipt detected with missing amount - needs manual review")
                return None
            else:
                logger.warning("No amount found in text")
                return None
        
        # SMART RECOVERY: If the best amount is suspiciously low (≤800), try to find a better one
        best_amount = max(amount_candidates, key=lambda x: x[1])
        
        if best_amount[0] <= 800:
            logger.info(f"Detected suspiciously low amount ¥{best_amount[0]}, trying to find better candidate...")
            
            # Look for amounts that are reasonable multiples or similar patterns
            better_candidates = []
            for amount, priority, line in amount_candidates:
                if amount > 500:  # Only consider amounts > 500
                    # Boost priority for amounts that appear multiple times (including format variations)
                    amount_frequency = sum(1 for a, _, _ in amount_candidates if a == amount)
                    
                    # Also count format variations in the full text (strong signal for correct amount)
                    text_lower = '\n'.join([line for _, _, line in amount_candidates]).lower()
                    format_variations = [
                        f'¥{amount}', f'{amount}円', f'¥{amount:,}', f'{amount:,}円',
                        f'¥{amount}-', f'{amount}-', f'¥ {amount}', f'{amount} '
                    ]
                    format_frequency = sum(text_lower.count(var.lower()) for var in format_variations)
                    
                    frequency_boost = (amount_frequency * 50) + (format_frequency * 30)
                    
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
                threshold = best_amount[1] * 0.7
                logger.debug(f"Smart recovery: best=¥{best_amount[0]} (priority:{best_amount[1]}), better=¥{better_amount[0]} (priority:{better_amount[1]}), threshold={threshold}")
                if better_amount[1] > threshold:  # If alternative is reasonably competitive
                    logger.info(f"Switching from ¥{best_amount[0]} to ¥{better_amount[0]} (better candidate found)")
                    best_amount = better_amount
                else:
                    logger.debug(f"Not switching: {better_amount[1]} <= {threshold}")
        
        logger.info(f"Extracted amount: ¥{best_amount[0]} from line: {best_amount[2][:50]}...")
        return best_amount[0]
    
    def _extract_amounts_from_line(self, line: str) -> List[Tuple[int, int]]:
        """Extract all potential amounts from a line with confidence scores."""
        amounts = []
        
        # CRITICAL: Skip pure tax rate lines entirely - they should not generate any amounts
        # Lines like "647 8%" are tax rate indicators, not amounts
        # BUT lines like "10%対象(税込) ¥2,800-" are totals and should be processed
        if re.match(r'^\s*\d+\s*[8|10]%\s*$', line.strip()):
            logger.debug(f"Skipping pure tax rate line entirely: {line.strip()}")
            return []
        
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
                    # Remove commas, spaces, and convert to int
                    # This handles OCR spacing issues like "1, 738" → "1738"
                    cleaned_amount_str = amount_str.replace(',', '').replace(' ', '').strip()
                    if not cleaned_amount_str.isdigit():
                        continue
                    amount = int(cleaned_amount_str)
                    
                    # Skip obviously wrong amounts
                    if amount < 10 or amount > 1000000:  # ¥10 to ¥1M reasonable range
                        continue
                    
                    # CRITICAL: Skip if this number was identified as a non-amount
                    if amount in non_amount_numbers:
                        logger.debug(f"Skipping amount {amount} - identified as non-amount number in line: {line.strip()}")
                        continue
                    
                    # ENHANCED: Check if this is part of a phone number
                    if self._is_likely_phone_number_part(amount, line):
                        logger.debug(f"Skipping amount {amount} - appears to be part of phone number in line: {line.strip()}")
                        continue
                    
                    # CRITICAL: Skip amounts that appear in system/metadata contexts
                    if self._is_likely_system_metadata(amount, line):
                        logger.debug(f"Skipping amount {amount} - appears to be system metadata in line: {line.strip()}")
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
                        confidence -= 300  # Ultra strong penalty for parentheses (tax amounts)
                    
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
        elif any(keyword in text_lower for keyword in ['rakuten mobile', '楽天モバイル', 'rakuten mobile usage']):
            return "rakuten mobile"
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
        
        # Medical patterns
        elif any(keyword in text_lower for keyword in ['クリニック', 'clinic', '病院', '医院', '診療所']):
            return "medical expense"
        elif any(keyword in text_lower for keyword in ['歯科', '歯医者']):
            return "dental expense"
        elif any(keyword in text_lower for keyword in ['薬局', 'ドラッグストア', '処方箋', '薬代']):
            return "pharmacy"
        elif any(keyword in text_lower for keyword in ['健康診断', '人間ドック']):
            return "health checkup"
        elif '点' in text_lower and any(keyword in text_lower for keyword in ['保険', '医療']):
            return "medical expense"
        
        # Education/Books patterns
        elif any(keyword in text_lower for keyword in ['アラビア語', '英語', '中国語', 'フランス語', 'スペイン語', 'ドイツ語', '韓国語']):
            return "language learning"
        elif any(keyword in text_lower for keyword in ['有隣堂', '紀伊國屋', 'tsutaya', '本', '書籍', '教科書', '参考書']):
            return "books"
        elif any(keyword in text_lower for keyword in ['語学', '学習', '勉強', '教育', '研修', 'セミナー', '講座']):
            return "education"
        
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
            'Education': self._get_education_description(text_lower),
            'Medical': self._get_medical_description(text_lower),
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
        if any(keyword in text_lower for keyword in ['rakuten mobile', '楽天モバイル', 'rakuten mobile usage']):
            return "rakuten mobile"
        elif any(keyword in text_lower for keyword in ['インターネット', 'wi-fi', 'wifi']):
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
    
    def _get_education_description(self, text_lower: str) -> str:
        """Get specific education description based on context."""
        if any(keyword in text_lower for keyword in ['アラビア語', '英語', '中国語', 'フランス語', 'スペイン語', 'ドイツ語', '韓国語']):
            return "language learning"
        elif any(keyword in text_lower for keyword in ['有隣堂', '紀伊國屋', 'tsutaya', '本', '書籍']):
            return "books"
        elif any(keyword in text_lower for keyword in ['教科書', '参考書', '辞書', '辞典']):
            return "reference materials"
        elif any(keyword in text_lower for keyword in ['研修', 'セミナー', '講座']):
            return "training"
        elif any(keyword in text_lower for keyword in ['資格', '試験', '検定']):
            return "certification"
        else:
            return "education"
    
    def _get_medical_description(self, text_lower: str) -> str:
        """Get specific medical description based on context."""
        if any(keyword in text_lower for keyword in ['クリニック', 'clinic', '病院', '医院', '診療所']):
            return "medical expense"
        elif any(keyword in text_lower for keyword in ['歯科', '歯医者']):
            return "dental expense"
        elif any(keyword in text_lower for keyword in ['薬局', 'ドラッグストア', '処方箋', '薬代']):
            return "pharmacy"
        elif any(keyword in text_lower for keyword in ['健康診断', '人間ドック']):
            return "health checkup"
        elif any(keyword in text_lower for keyword in ['予防接種', 'ワクチン']):
            return "vaccination"
        elif '点' in text_lower and any(keyword in text_lower for keyword in ['保険', '医療']):
            return "medical expense"
        else:
            return "medical expense"
    
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
            '口座', '取引', '参照', '郵便', '〒', '#', '第',
            # ENHANCED: Better phone number context detection
            '080-', '090-', '070-', '050-', # Common mobile prefixes
            '03-', '06-', '011-', '052-', '092-'  # Common area codes
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
    
    def _is_likely_phone_number_part(self, amount: int, line: str) -> bool:
        """Check if an amount appears to be part of a phone number."""
        
        line_lower = line.lower()
        amount_str = str(amount)
        
        # Check if line contains phone indicators
        phone_indicators = ['tel', '電話', 'phone', 'fax', 'ファックス']
        has_phone_indicator = any(indicator in line_lower for indicator in phone_indicators)
        
        if not has_phone_indicator:
            return False
        
        # Check for phone number patterns
        phone_patterns = [
            r'tel\s*[0-9\-\s]*' + re.escape(amount_str) + r'(?:\s*\-|$)',  # TEL...amount at end or followed by dash
            r'電話\s*[0-9\-\s]*' + re.escape(amount_str) + r'(?:\s*\-|$)', # 電話...amount at end or followed by dash
            r'[0-9]{2,3}\-[0-9]{3,4}\-' + re.escape(amount_str) + r'(?:\s*\-|$)',  # Phone format ending with amount
            r'[0-9]{3,4}\-' + re.escape(amount_str) + r'(?:\s*\-|$)',  # Partial phone ending with amount
        ]
        
        for pattern in phone_patterns:
            if re.search(pattern, line_lower):
                return True
        
        # Check if amount appears immediately after phone number prefixes
        phone_prefixes = ['080-', '090-', '070-', '050-', '03-', '06-']
        for prefix in phone_prefixes:
            if prefix in line_lower:
                # Look for the amount appearing after this prefix
                prefix_pos = line_lower.find(prefix)
                if prefix_pos >= 0:
                    after_prefix = line_lower[prefix_pos:]
                    # Check if our amount appears shortly after the prefix
                    if amount_str in after_prefix[:20]:  # Within 20 characters
                        return True
        
        return False
    
    def _is_likely_system_metadata(self, amount: int, line: str) -> bool:
        """Check if an amount appears to be system metadata (transaction IDs, etc.) rather than money."""
        
        # System/metadata keywords that indicate non-monetary numbers
        system_keywords = [
            # POS system terms
            'POS', '取引', '証学書', 'システム', 'system',
            # Transaction/ID terms  
            'ID', 'No', 'NO', 'id', 'no', '番号', '注文番号', '伝票', '端末',
            # Technical terms
            'バージョン', 'version', 'Ver', 'ver', 'code', 'コード',
            # Receipt metadata that's not amounts
            '時間', '店舗', '取引', '証学書'
        ]
        
        # Check if the line contains system keywords
        line_lower = line.lower()
        if any(keyword.lower() in line_lower for keyword in system_keywords):
            return True
        
        # Check if the amount is a standalone large number (likely an ID)
        # IDs are typically 4+ digits and appear alone on a line
        if amount >= 1000 and line.strip().isdigit():
            return True
        
        # Check if the amount appears within alphanumeric codes/IDs
        # Pattern: letters/numbers-digits-amount.digits or similar technical formats
        import re
        technical_pattern = r'^[A-Za-z0-9\-\.]+$'
        if re.match(technical_pattern, line.strip()) and len(line.strip()) > 10:
            # This looks like a technical ID/code containing the amount as part of it
            return True
            
        return False
    
    def _is_tax_amount(self, amount: int, line: str, all_lines: List[str], line_idx: int) -> bool:
        """Check if an amount is likely a tax amount that should be excluded from main total selection."""
        
        line_lower = line.lower()
        
        # Check for direct tax indicators in the same line
        tax_indicators = ['消費税等', '消費税', '税額', '税金', '10%', '8%', '内税']
        
        # But first check if this line contains total amount indicators that override tax detection
        total_amount_indicators = ['税込', '合計', '総計', '小計', 'total', 'subtotal']
        if any(total_indicator in line_lower for total_indicator in total_amount_indicators):
            logger.debug(f"Amount NOT tax - line contains total indicator: {line.strip()}")
            return False
        
        # CRITICAL: Check for final total indicators that override tax detection
        # The "-" suffix is commonly used to indicate final total amounts
        if line.strip().endswith('-') or '¥' + str(amount) + '-' in line:
            logger.debug(f"Amount NOT tax - line has final total indicator (-): {line.strip()}")
            return False
            
        if any(indicator in line for indicator in tax_indicators):
            logger.debug(f"Tax amount detected by direct indicator in line: {line.strip()}")
            return True
        
        # Check for tax context patterns
        for pattern in self.tax_context_patterns:
            match = re.search(pattern, line)
            if match:
                # Extract the amount from the pattern and see if it matches our amount
                try:
                    pattern_amount_str = match.group(1).replace(',', '').replace(' ', '').strip()
                    if pattern_amount_str.isdigit() and int(pattern_amount_str) == amount:
                        logger.debug(f"Tax amount detected by pattern '{pattern}' in line: {line.strip()}")
                        return True
                except (ValueError, IndexError):
                    continue
        
        # Check adjacent lines for tax context - but be smarter about total vs tax
        if line_idx > 0:
            prev_line = all_lines[line_idx - 1]
            # Check if previous line mentions tax rate (like 10%消費税) but current context is about totals
            if any(indicator in prev_line for indicator in ['消費税等', '消費税', '税額', '税金']):
                # Check if the next line or current line indicates this is a total, not tax
                total_indicators_in_context = ['税込合計', '合計', '小計', '総計', 'total']
                context_lines = [line]
                if line_idx < len(all_lines) - 1:
                    context_lines.append(all_lines[line_idx + 1])
                
                if any(any(total_ind in context_line for total_ind in total_indicators_in_context) for context_line in context_lines):
                    logger.debug(f"NOT tax amount - previous line mentions tax but context indicates total: {prev_line.strip()} -> {line.strip()}")
                    return False
                else:
                    # If previous line mentions tax and this line has amount with no total context, it's likely tax
                    logger.debug(f"Tax amount detected by previous line context: {prev_line.strip()} -> {line.strip()}")
                    return True
        
        if line_idx < len(all_lines) - 1:
            next_line = all_lines[line_idx + 1]
            if any(indicator in next_line for indicator in ['消費税等', '消費税', '税額', '税金']):
                # If next line mentions tax and this line has the amount, it's likely tax
                logger.debug(f"Tax amount detected by next line context: {line.strip()} -> {next_line.strip()}")
                return True
        
        # Check if amount appears to be tax based on size relative to total
        # Small amounts that appear multiple times might be tax
        if amount <= 200:  # Tax amounts are typically small
            # Count how many times this amount appears in nearby lines
            occurrences = 0
            for i in range(max(0, line_idx - 2), min(len(all_lines), line_idx + 3)):
                if str(amount) in all_lines[i]:
                    occurrences += 1
            
            # If small amount appears multiple times, it might be tax being repeated
            if occurrences >= 2:
                # Additional check: see if there are tax keywords in the vicinity
                context_lines = all_lines[max(0, line_idx - 2):min(len(all_lines), line_idx + 3)]
                context_text = ' '.join(context_lines)
                if any(indicator in context_text for indicator in tax_indicators):
                    logger.debug(f"Small amount ¥{amount} appears {occurrences} times with tax context - likely tax")
                    return True
        
        return False
    
    def _could_be_tax_on_total_line(self, amount: int, line: str) -> bool:
        """Check if an amount on a 合計 line could actually be a tax amount."""
        
        # If the amount is small (typical tax amount) and appears on 合計 line with tax indicators
        if amount <= 300:  # Typical tax amounts
            tax_indicators = ['消費税', '税', '10%', '8%']
            if any(indicator in line for indicator in tax_indicators):
                return True
        
        # Check if the line has both 合計 and tax-related text
        if '合計' in line and any(indicator in line for indicator in ['消費税', '税額', '10%']):
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