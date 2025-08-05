"""Base template class for receipt parsing."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class TemplateMatch:
    """Result of template matching."""
    confidence: float
    vendor: str
    template_name: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TemplateResult:
    """Complete parsing result from template."""
    date: Optional[str] = None
    amount: Optional[int] = None
    vendor: Optional[str] = None
    description: str = ""
    confidence: float = 0.0
    template_name: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseTemplate(ABC):
    """Base class for receipt templates."""
    
    def __init__(self, name: str, vendor_patterns: List[str], confidence_threshold: float = 0.7):
        """
        Initialize template.
        
        Args:
            name: Template name
            vendor_patterns: Patterns to identify this vendor
            confidence_threshold: Minimum confidence to use this template
        """
        self.name = name
        self.vendor_patterns = vendor_patterns
        self.confidence_threshold = confidence_threshold
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def matches(self, text: str) -> Optional[TemplateMatch]:
        """
        Check if this template matches the receipt text.
        
        Args:
            text: Raw receipt text
            
        Returns:
            TemplateMatch if template applies, None otherwise
        """
        text_lower = text.lower()
        
        # Check for vendor patterns
        best_match = None
        max_confidence = 0.0
        
        for pattern in self.vendor_patterns:
            if isinstance(pattern, str):
                if pattern.lower() in text_lower:
                    confidence = 0.9  # High confidence for exact match
                    if confidence > max_confidence:
                        max_confidence = confidence
                        best_match = TemplateMatch(
                            confidence=confidence,
                            vendor=self._extract_vendor_name(text, pattern),
                            template_name=self.name,
                            metadata={'matched_pattern': pattern}
                        )
            else:  # Regex pattern (already compiled)
                match = pattern.search(text)
                if match:
                    confidence = 0.8  # Slightly lower for regex
                    if confidence > max_confidence:
                        max_confidence = confidence
                        best_match = TemplateMatch(
                            confidence=confidence,
                            vendor=self._extract_vendor_name(text, match.group()),
                            template_name=self.name,
                            metadata={'matched_pattern': pattern, 'regex_match': match.group()}
                        )
        
        if best_match and best_match.confidence >= self.confidence_threshold:
            self.logger.info(f"Template {self.name} matched with confidence {best_match.confidence:.2f}")
            return best_match
        
        return None
    
    @abstractmethod
    def parse(self, text: str, match: TemplateMatch) -> TemplateResult:
        """
        Parse receipt using this template.
        
        Args:
            text: Raw receipt text
            match: Template match result
            
        Returns:
            Complete parsing result
        """
        pass
    
    def _extract_vendor_name(self, text: str, pattern: str) -> str:
        """Extract clean vendor name from text."""
        # Default implementation - subclasses can override
        return pattern.title()
    
    def _parse_date_with_patterns(self, text: str, patterns: List[str]) -> Optional[str]:
        """Parse date using template-specific patterns."""
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                try:
                    # Extract date components
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
        
        return None
    
    def _parse_amount_with_keywords(self, text: str, keywords: List[str]) -> Optional[int]:
        """Parse amount using template-specific keywords."""
        lines = text.split('\n')
        
        for keyword in keywords:
            for line_idx, line in enumerate(lines):
                if keyword not in line:
                    continue
                
                # Look for amount in current line and adjacent lines
                search_lines = [
                    line,
                    lines[line_idx - 1] if line_idx > 0 else '',
                    lines[line_idx + 1] if line_idx < len(lines) - 1 else ''
                ]
                
                for search_line in search_lines:
                    if not search_line:
                        continue
                    
                    # Extract amount from line
                    amount_match = re.search(r'¥?\s*([0-9,\s]+)', search_line)
                    if amount_match:
                        try:
                            amount_str = amount_match.group(1)
                            cleaned = amount_str.replace(',', '').replace(' ', '').strip()
                            
                            if cleaned.isdigit():
                                amount = int(cleaned)
                                if 10 <= amount <= 1000000:  # Reasonable range
                                    return amount
                        except ValueError:
                            continue
        
        return None
    
    def _calculate_confidence(self, parsed_fields: Dict[str, Any], 
                            base_confidence: float) -> float:
        """Calculate overall confidence based on parsed fields."""
        field_weights = {
            'date': 0.3,
            'amount': 0.4,
            'vendor': 0.2,
            'description': 0.1
        }
        
        confidence = base_confidence
        
        for field, weight in field_weights.items():
            if field in parsed_fields and parsed_fields[field]:
                confidence += weight * 0.5  # Boost for successfully parsed fields
        
        return min(1.0, confidence)