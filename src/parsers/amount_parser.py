"""Amount parsing with intelligent prioritization and tax detection."""

import re
import logging
from typing import Optional, List, Dict, Tuple
from .base import BaseParser, ParseResult, ReceiptContext

logger = logging.getLogger(__name__)


class AmountParser(BaseParser):
    """Specialized parser for extracting amounts from Japanese receipts."""
    
    def __init__(self):
        super().__init__()
        
        # Amount patterns in priority order (pattern, priority_score)
        self.amount_patterns = [
            (r'合計\s*¥?([0-9,\s]+)', 100),     # 合計 - highest priority
            (r'¥\s*([0-9,\s]+)\s*(?=\s|$|\n|円)', 80),  # Clean yen amounts
            (r'([0-9,\s]+)円', 70),             # Numbers with 円
            (r'¥\s*([0-9,\s]+)-?', 60),         # Yen with optional dash
            (r'(?:総計|総合計|お買上げ|税込合計)\s*:?\s*¥?\s*([0-9,\s]+)', 90),
            (r'([0-9,\s]+)(?=\s*(?:合計|総計|総合計|お買上げ))', 85),
            (r'([0-9,\s]+)\)?', 40),            # Numbers with optional parenthesis
            (r'\b([1-9][0-9,\s]{2,8})\b', 20), # Standalone numbers (lowest)
        ]
        
        # Total keywords in preference order
        self.total_keywords = [
            ('お支払い金額', 2000), ('お支払金額', 2000),  # Payment amount
            ('支払い金額', 1800), ('支払金額', 1800),
            ('利用金額', 2000), ('利用額', 2000), ('入金額', 2000), ('領収金額', 2000),
            ('合計', 5000), ('合 計', 5000),      # Total
            ('総合計', 4000), ('総 合 計', 4000),  # Grand total
            ('税込合計', 4000),                    # Tax-inclusive total
            ('お買上げ', 3000), ('総計', 3000),    # Purchase total
            ('税込', 2000), ('言十', 1000), ('合', 800)
        ]
        
        # Keywords to avoid (tax, change, etc.)
        self.avoid_keywords = [
            '小計', '税抜', '本体価格', '内税', '消費税', '税額', '税金',
            'おつり', 'お釣り', '釣り', '預り', 'お預り', 'お預り金額',
            '内消費税', '内消費費税', '手数料', '残高', '年', '月', '日'
        ]
        
        # Tax context patterns for exclusion
        self.tax_patterns = [
            r'消費税等.*¥?([0-9,\s]+)',
            r'([0-9,\s]+).*消費税等',
            r'10%.*¥?([0-9,\s]+)',
            r'([0-9,\s]+).*10%',
            r'税額.*¥?([0-9,\s]+)',
        ]
    
    def parse(self, context: ReceiptContext) -> Optional[ParseResult]:
        """
        Extract total amount from Japanese receipt text.
        
        Args:
            context: Receipt context with full text and lines
            
        Returns:
            ParseResult with amount in JPY and confidence
        """
        amount_candidates = []
        
        # First pass: Look for amounts near total keywords
        self._find_keyword_amounts(context, amount_candidates)
        
        # Second pass: Add standalone amounts if no keyword amounts
        if not amount_candidates:
            self._find_standalone_amounts(context, amount_candidates)
        
        # Third pass: Add high-frequency amounts for validation
        self._add_frequency_amounts(context, amount_candidates)
        
        if not amount_candidates:
            self.logger.warning("No amount candidates found")
            return None
        
        # Smart recovery for suspiciously low amounts
        best_candidate = self._select_best_amount(amount_candidates, context)
        if not best_candidate:
            return None
        
        amount, priority, source_line, metadata = best_candidate
        confidence = min(0.95, priority / 10000.0)  # Normalize to 0-1
        
        result = ParseResult(
            value=amount,
            confidence=confidence,
            source_text=source_line[:50] + "...",
            metadata=metadata
        )
        
        self._log_result(result, context)
        return result
    
    def _find_keyword_amounts(self, context: ReceiptContext, candidates: List):
        """Find amounts near total keywords."""
        for line_idx, line in enumerate(context.lines):
            for keyword, keyword_priority in self.total_keywords:
                if keyword not in line:
                    continue
                
                # Search current line and adjacent lines
                search_lines = [
                    (line, line_idx, 'current'),
                    (context.lines[line_idx - 1] if line_idx > 0 else '', line_idx - 1, 'previous'),
                    (context.lines[line_idx + 1] if line_idx < len(context.lines) - 1 else '', line_idx + 1, 'next')
                ]
                
                for search_line, search_idx, position in search_lines:
                    if not search_line:
                        continue
                    
                    for amount, confidence in self._extract_amounts_from_line(search_line):
                        if self._is_tax_amount(amount, search_line, context.lines, search_idx):
                            continue
                        
                        # Calculate priority based on keyword and position
                        priority = self._calculate_keyword_priority(
                            keyword, keyword_priority, position, amount, search_line, line
                        )
                        
                        # Apply penalties for avoid keywords
                        priority = self._apply_avoid_penalties(
                            priority, search_line, context.lines, search_idx
                        )
                        
                        candidates.append((
                            amount, priority, search_line,
                            {'keyword': keyword, 'position': position, 'type': 'keyword'}
                        ))
    
    def _find_standalone_amounts(self, context: ReceiptContext, candidates: List):
        """Find standalone amounts when no keyword amounts exist."""
        for line in context.lines:
            for amount, confidence in self._extract_amounts_from_line(line):
                candidates.append((
                    amount, confidence, line,
                    {'type': 'standalone'}
                ))
    
    def _add_frequency_amounts(self, context: ReceiptContext, candidates: List):
        """Add high-frequency amounts that might be the correct total."""
        frequency_map = {}
        all_amounts = []
        
        # Count non-tax amounts
        for line_idx, line in enumerate(context.lines):
            for amount, confidence in self._extract_amounts_from_line(line):
                if not self._is_tax_amount(amount, line, context.lines, line_idx):
                    frequency_map[amount] = frequency_map.get(amount, 0) + 1
                    all_amounts.append((amount, confidence, line))
        
        # Add high-frequency amounts with boosted priority
        for amount, confidence, line in all_amounts:
            frequency = frequency_map.get(amount, 0)
            if frequency >= 2:
                priority = confidence + (frequency * 300)
                
                # Extra boost for most frequent amount
                max_frequency = max(frequency_map.values()) if frequency_map else 0
                if frequency == max_frequency:
                    priority += 500
                
                candidates.append((
                    amount, priority, line,
                    {'type': 'frequency', 'frequency': frequency}
                ))
    
    def _extract_amounts_from_line(self, line: str) -> List[Tuple[int, int]]:
        """Extract potential amounts from a line with confidence scores."""
        amounts = []
        
        # Skip pure tax rate lines
        if re.match(r'^\s*\d+\s*[8|10]%\s*$', line.strip()):
            return []
        
        for pattern, base_confidence in self.amount_patterns:
            for match in re.finditer(pattern, line):
                try:
                    amount_str = match.group(1)
                    cleaned = amount_str.replace(',', '').replace(' ', '').strip()
                    
                    if not cleaned.isdigit():
                        continue
                    
                    amount = int(cleaned)
                    if not (10 <= amount <= 1000000):  # Reasonable range
                        continue
                    
                    # Check for parentheses (usually tax/negative amounts)
                    if '(' in match.group() or ')' in match.group():
                        base_confidence -= 300
                    
                    amounts.append((amount, base_confidence))
                    
                except (ValueError, IndexError):
                    continue
        
        return amounts
    
    def _calculate_keyword_priority(self, keyword: str, base_priority: int, 
                                   position: str, amount: int, amount_line: str, keyword_line: str) -> int:
        """Calculate priority based on keyword type and position."""
        priority = base_priority
        
        # Special handling for 合計 (total)
        if keyword in ['合計', '合 計']:
            if position == 'next':
                priority = 7000  # Highest for amount after 合計
            elif position == 'current':
                priority = 5000
            else:
                priority = 3000
        
        # Ultra-high priority keywords
        elif keyword in ['利用金額', '利用額', '入金額', '領収金額']:
            if self._validate_amount_for_keyword(amount, keyword, amount_line, keyword_line, position):
                priority = 2000 + (500 if position == 'current' else 100)
            else:
                priority = 50  # Failed validation
        
        # Position bonuses
        if position == 'current':
            priority += 800
        elif position == 'previous':
            priority += 400
        
        return priority
    
    def _apply_avoid_penalties(self, priority: int, line: str, all_lines: List[str], line_idx: int) -> int:
        """Apply penalties for avoid keywords in context."""
        penalty = 0
        
        # Check current line
        if any(avoid_kw in line for avoid_kw in self.avoid_keywords):
            penalty += 50
        
        # Check previous line
        if line_idx > 0:
            prev_line = all_lines[line_idx - 1]
            if any(avoid_kw in prev_line for avoid_kw in self.avoid_keywords):
                penalty += 180
        
        # Check next line
        if line_idx < len(all_lines) - 1:
            next_line = all_lines[line_idx + 1]
            if any(avoid_kw in next_line for avoid_kw in self.avoid_keywords):
                penalty += 150
        
        return max(0, priority - penalty)
    
    def _is_tax_amount(self, amount: int, line: str, all_lines: List[str], line_idx: int) -> bool:
        """Check if amount is likely a tax amount to exclude."""
        # Check for tax indicators in line
        tax_indicators = ['消費税等', '消費税', '税額', '税金', '内税', '10%', '8%']
        
        # Check for total indicators that override tax detection
        total_indicators = ['税込', '合計', '総計', '小計', 'total']
        if any(indicator in line for indicator in total_indicators):
            return False
        
        # Check for final total indicators (- suffix)
        if line.strip().endswith('-') or f'¥{amount}-' in line:
            return False
        
        # Check for tax context patterns
        for pattern in self.tax_patterns:
            if re.search(pattern, line):
                return True
        
        # Check adjacent lines for tax context
        if line_idx > 0:
            prev_line = all_lines[line_idx - 1]
            if any(indicator in prev_line for indicator in ['消費税等', '消費税', '税額']):
                return True
        
        return False
    
    def _validate_amount_for_keyword(self, amount: int, keyword: str, 
                                   amount_line: str, keyword_line: str, position: str) -> bool:
        """Validate that amount is genuinely associated with high-priority keyword."""
        # Basic size validation
        if amount < 100 and position != 'current':
            return False
        
        # Check for suspicious indicators
        suspicious = ['登録番号', '取引番号', 'id:', 'tel:', '電話', '番号']
        if any(indicator in amount_line.lower() for indicator in suspicious):
            return False
        
        # Proximity validation for same line
        if position == 'current':
            keyword_pos = keyword_line.find(keyword)
            amount_str = str(amount)
            if keyword_pos >= 0 and amount_str not in keyword_line[keyword_pos:keyword_pos + 50]:
                return False
        
        return True
    
    def _select_best_amount(self, candidates: List, context: ReceiptContext) -> Optional[Tuple]:
        """Select the best amount with smart recovery for low amounts."""
        if not candidates:
            return None
        
        best = max(candidates, key=lambda x: x[1])  # x[1] is priority
        
        # Smart recovery for suspiciously low amounts
        if best[0] <= 800:  # Amount is suspiciously low
            better_candidates = [
                c for c in candidates 
                if c[0] > 500 and c[1] > best[1] * 0.7
            ]
            
            if better_candidates:
                alternative = max(better_candidates, key=lambda x: x[1])
                self.logger.info(f"Smart recovery: switching from ¥{best[0]} to ¥{alternative[0]}")
                return alternative
        
        return best