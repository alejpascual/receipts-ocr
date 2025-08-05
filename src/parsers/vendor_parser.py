"""Vendor/business name extraction from Japanese receipts."""

import re
import logging
from typing import Optional, List, Tuple
from .base import BaseParser, ParseResult, ReceiptContext

logger = logging.getLogger(__name__)


class VendorParser(BaseParser):
    """Specialized parser for extracting vendor/store names from receipts."""
    
    def __init__(self):
        super().__init__()
        
        # Business entity patterns in priority order
        self.business_patterns = [
            (r'株式会社[^\n]+', 'corporation', 90),
            (r'有限会社[^\n]+', 'limited_company', 85),
            (r'[^\n]*店[^\n]*', 'store', 80),
            (r'[^\n]*支店[^\n]*', 'branch', 75),
            (r'[^\n]*堂[^\n]*', 'dou', 70),
            (r'[^\n]*屋[^\n]*', 'ya', 65),
            (r'セブン.*イレブン', 'seven_eleven', 95),
            (r'JR[^\n]*', 'jr', 60),
            (r'スターバックス[^\n]*', 'starbucks', 95),
        ]
        
        # Known major chains with high confidence
        self.major_chains = {
            'セブンイレブン': 'Seven-Eleven',
            'ファミリーマート': 'FamilyMart', 
            'ローソン': 'Lawson',
            'スターバックス': 'Starbucks',
            'ドトール': 'Doutor',
            'イケア': 'IKEA',
            'マクドナルド': "McDonald's",
            'ケンタッキー': 'KFC',
            'ヨドバシカメラ': 'Yodobashi Camera',
            'ビックカメラ': 'Bic Camera',
        }
        
        # Patterns to exclude (not business names)
        self.exclude_patterns = [
            r'\d{4}年|\d{4}/|\d{4}-',  # Dates
            r'[0-9,]+円',              # Amounts  
            r'領収|レシート',           # Receipt labels
            r'合計|小計',              # Total labels
            r'税込|税抜',              # Tax labels
        ]
    
    def parse(self, context: ReceiptContext) -> Optional[ParseResult]:
        """
        Extract vendor/store name from receipt text.
        
        Args:
            context: Receipt context with full text and lines
            
        Returns:
            ParseResult with vendor name and confidence
        """
        vendor_candidates = []
        
        # First pass: Look for known major chains
        major_chain = self._find_major_chain(context)
        if major_chain:
            return ParseResult(
                value=major_chain,
                confidence=0.95,
                source_text="major_chain_detection",
                metadata={'type': 'major_chain'}
            )
        
        # Second pass: Look for business entity patterns
        self._find_business_patterns(context, vendor_candidates)
        
        # Third pass: Use heuristic fallback for first meaningful line
        if not vendor_candidates:
            fallback = self._find_fallback_vendor(context)
            if fallback:
                vendor_candidates.append(fallback)
        
        if not vendor_candidates:
            self.logger.warning("No vendor name found")
            return None
        
        # Select best candidate
        best_candidate = max(vendor_candidates, key=lambda x: x[1])
        vendor, confidence, source_text, metadata = best_candidate
        
        result = ParseResult(
            value=vendor,
            confidence=min(0.9, confidence),
            source_text=source_text,
            metadata=metadata
        )
        
        self._log_result(result, context)
        return result
    
    def _find_major_chain(self, context: ReceiptContext) -> Optional[str]:
        """Look for known major chain indicators."""
        text_lower = context.full_text.lower()
        
        for japanese_name, english_name in self.major_chains.items():
            if japanese_name.lower() in text_lower:
                self.logger.info(f"Found major chain: {english_name}")
                return english_name
        
        # Check for English chain names
        english_chains = ['starbucks', 'ikea', 'seven-eleven', 'familymart', 'lawson']
        for chain in english_chains:
            if chain in text_lower:
                return chain.title()
        
        return None
    
    def _find_business_patterns(self, context: ReceiptContext, candidates: List):
        """Find vendors using business entity patterns."""
        # Check first 5 lines (vendor usually at top)
        for line_idx, line in enumerate(context.lines[:5]):
            if not line.strip():
                continue
            
            # Skip lines that match exclude patterns
            if any(re.search(pattern, line) for pattern, in self.exclude_patterns):
                continue
            
            for pattern, pattern_type, base_confidence in self.business_patterns:
                match = re.search(pattern, line)
                if match:
                    vendor = match.group().strip()
                    if len(vendor) > 2:  # Reasonable length
                        # Position bonus (earlier lines get higher confidence)
                        position_bonus = max(0, 10 - line_idx * 2)
                        confidence = (base_confidence + position_bonus) / 100.0
                        
                        candidates.append((
                            vendor, confidence, line,
                            {'type': 'business_pattern', 'pattern': pattern_type, 'line_idx': line_idx}
                        ))
    
    def _find_fallback_vendor(self, context: ReceiptContext) -> Optional[Tuple]:
        """Fallback method using first meaningful line."""
        for line_idx, line in enumerate(context.lines[:3]):
            line = line.strip()
            if not line:
                continue
            
            # Skip lines that look like metadata
            if any(re.search(pattern, line) for pattern in self.exclude_patterns):
                continue
            
            # Skip very short or very long lines
            if not (3 <= len(line) <= 50):
                continue
            
            # Basic heuristic: first non-excluded line is likely vendor
            confidence = max(0.3, 0.7 - (line_idx * 0.2))  # Decrease with position
            
            return (
                line, confidence, line,
                {'type': 'fallback', 'line_idx': line_idx}
            )
        
        return None
    
    def _clean_vendor_name(self, vendor: str) -> str:
        """Clean up vendor name for consistency."""
        # Remove extra whitespace
        vendor = ' '.join(vendor.split())
        
        # Remove common prefixes/suffixes that add noise
        prefixes_to_remove = ['株式会社', '有限会社']
        for prefix in prefixes_to_remove:
            if vendor.startswith(prefix):
                vendor = vendor[len(prefix):].strip()
        
        return vendor