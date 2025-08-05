"""Base classes for receipt parsers."""

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result of a parsing operation with confidence and metadata."""
    value: Any
    confidence: float
    source_text: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ReceiptContext:
    """Context information about a receipt for parsing."""
    full_text: str
    lines: List[str] = None
    vendor_hints: List[str] = None
    amount_hints: List[int] = None
    date_hints: List[str] = None
    
    def __post_init__(self):
        if self.lines is None:
            self.lines = self.full_text.split('\n') if self.full_text else []
        if self.vendor_hints is None:
            self.vendor_hints = []
        if self.amount_hints is None:
            self.amount_hints = []
        if self.date_hints is None:
            self.date_hints = []


class BaseParser(ABC):
    """Base class for all receipt parsers."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def parse(self, context: ReceiptContext) -> Optional[ParseResult]:
        """
        Parse the specific field from receipt context.
        
        Args:
            context: Receipt context with text and hints
            
        Returns:
            ParseResult with value and confidence, or None if parsing failed
        """
        pass
    
    def _log_result(self, result: Optional[ParseResult], context: ReceiptContext):
        """Log parsing result for debugging."""
        if result:
            self.logger.info(f"Parsed: {result.value} (confidence: {result.confidence:.2f})")
        else:
            self.logger.warning("Parsing failed - no result")
    
    def _calculate_base_confidence(self, match_strength: float, context_strength: float) -> float:
        """Calculate base confidence from match and context strength."""
        return min(1.0, (match_strength * 0.7) + (context_strength * 0.3))