"""Modernized Japanese receipt parsing using modular components."""

import logging
from typing import Optional, Dict, Any
from .parsers import DateParser, AmountParser, VendorParser, DescriptionGenerator
from .parsers.base import ReceiptContext
from .templates import TemplateEngine

logger = logging.getLogger(__name__)


class JapaneseReceiptParser:
    """
    Modernized receipt parser using specialized components and templates.
    
    This replaces the monolithic parse.py with focused, maintainable parsers
    plus template-based parsing for major chains.
    """
    
    def __init__(self, use_templates: bool = True):
        """Initialize with specialized parser components and template engine."""
        self.date_parser = DateParser()
        self.amount_parser = AmountParser()
        self.vendor_parser = VendorParser()
        self.description_generator = DescriptionGenerator()
        
        # Template engine for major chains
        self.template_engine = TemplateEngine() if use_templates else None
        
        logger.info(f"Initialized modernized receipt parser with modular components"
                   f"{' and template engine' if use_templates else ''}")
    
    def parse_receipt(self, text: str) -> Dict[str, Any]:
        """
        Parse a complete receipt using templates first, then fallback to general parsing.
        
        Args:
            text: Raw OCR text from receipt
            
        Returns:
            Dictionary with parsed fields and metadata
        """
        # Try template-based parsing first (high accuracy for known chains)
        if self.template_engine:
            template_result = self.template_engine.parse_with_template(text)
            if template_result:
                logger.info(f"Template parsing successful: {template_result.template_name}")
                return {
                    'date': template_result.date,
                    'amount': template_result.amount,
                    'vendor': template_result.vendor,
                    'description': template_result.description,
                    'confidence_scores': {
                        'date': template_result.confidence if template_result.date else 0.0,
                        'amount': template_result.confidence if template_result.amount else 0.0,
                        'vendor': template_result.confidence if template_result.vendor else 0.0,
                        'overall': template_result.confidence,
                    },
                    'metadata': {
                        'parsing_method': 'template',
                        'template_name': template_result.template_name,
                        'template_meta': template_result.metadata,
                    }
                }
        
        # Fallback to general component-based parsing
        logger.info("Using general component-based parsing")
        return self._parse_with_components(text)
    
    def _parse_with_components(self, text: str) -> Dict[str, Any]:
        """Parse using individual parser components."""
        # Create context for all parsers
        context = ReceiptContext(full_text=text)
        
        # Parse individual fields
        date_result = self.date_parser.parse(context)
        amount_result = self.amount_parser.parse(context)
        vendor_result = self.vendor_parser.parse(context)
        
        # Extract values
        date = date_result.value if date_result else None
        amount = amount_result.value if amount_result else None
        vendor = vendor_result.value if vendor_result else None
        
        # Generate description (doesn't use parse() method)
        description = self.description_generator.generate_description(
            text=text,
            vendor=vendor,
            amount=amount
        )
        
        # Compile results
        result = {
            'date': date,
            'amount': amount,
            'vendor': vendor,
            'description': description,
            'confidence_scores': {
                'date': date_result.confidence if date_result else 0.0,
                'amount': amount_result.confidence if amount_result else 0.0,
                'vendor': vendor_result.confidence if vendor_result else 0.0,
            },
            'metadata': {
                'parsing_method': 'components',
                'date_meta': date_result.metadata if date_result else {},
                'amount_meta': amount_result.metadata if amount_result else {},
                'vendor_meta': vendor_result.metadata if vendor_result else {},
            }
        }
        
        logger.info(f"Parsed receipt: date={date}, amount=¥{amount}, vendor={vendor}")
        return result
    
    # Legacy compatibility methods (for gradual migration)
    def parse_date(self, text: str) -> Optional[str]:
        """Legacy compatibility for date parsing."""
        context = ReceiptContext(full_text=text)
        result = self.date_parser.parse(context)
        return result.value if result else None
    
    def parse_amount(self, text: str) -> Optional[int]:
        """Legacy compatibility for amount parsing."""
        context = ReceiptContext(full_text=text)
        result = self.amount_parser.parse(context)
        return result.value if result else None
    
    def parse_vendor(self, text: str) -> Optional[str]:
        """Legacy compatibility for vendor parsing."""
        context = ReceiptContext(full_text=text)
        result = self.vendor_parser.parse(context)
        return result.value if result else None
    
    def extract_description_context(self, text: str, vendor: Optional[str], 
                                   amount: Optional[int], category: str = None) -> str:
        """Legacy compatibility for description generation."""
        return self.description_generator.generate_description(
            text=text, vendor=vendor, amount=amount, category=category
        )
    
    def should_flag_for_high_value_review(self, text: str, amount: Optional[int], 
                                        date: Optional[str], category: Optional[str] = None, 
                                        category_confidence: Optional[float] = None) -> bool:
        """
        Determine if transaction should be flagged for high-value review.
        
        Args:
            text: OCR text
            amount: Parsed amount
            date: Parsed date
            category: Classified category
            category_confidence: Classification confidence
            
        Returns:
            True if should be reviewed
        """
        if not amount:
            return False
        
        # Skip review for well-classified high-confidence transactions
        if (category and category_confidence and 
            category_confidence >= 0.8 and 
            category in ['Rent', 'Utilities', 'Equipment'] and 
            date and amount):
            logger.info(f"High-value ¥{amount:,} skipping review - well-classified as {category}")
            return False
            
        # High-value threshold
        if amount >= 50000:
            logger.warning(f"High-value transaction flagged: ¥{amount:,}")
            return True
            
        return False