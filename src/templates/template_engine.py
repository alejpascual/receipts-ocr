"""Template engine for receipt parsing."""

import logging
from typing import List, Optional, Dict, Any
from .base_template import BaseTemplate, TemplateResult
from .seven_eleven import SevenElevenTemplate
from .starbucks import StarbucksTemplate

logger = logging.getLogger(__name__)


class TemplateEngine:
    """Engine for managing and applying receipt templates."""
    
    def __init__(self):
        """Initialize with built-in templates."""
        self.templates: List[BaseTemplate] = []
        self._load_builtin_templates()
        
        logger.info(f"Initialized TemplateEngine with {len(self.templates)} templates")
    
    def _load_builtin_templates(self):
        """Load built-in templates for major chains."""
        try:
            # Add major chain templates
            self.templates.extend([
                SevenElevenTemplate(),
                StarbucksTemplate(),
                # IKEATemplate(),    # TODO: Implement
                # JRTemplate(),      # TODO: Implement  
                # FamilyMartTemplate(), # TODO: Implement
            ])
            
            logger.info("Loaded built-in templates: " + 
                       ", ".join(t.name for t in self.templates))
                       
        except Exception as e:
            logger.error(f"Error loading built-in templates: {e}")
    
    def parse_with_template(self, text: str) -> Optional[TemplateResult]:
        """
        Try to parse receipt using the best matching template.
        
        Args:
            text: Raw receipt text
            
        Returns:
            TemplateResult if a template matches, None otherwise
        """
        best_template = None
        best_match = None
        best_confidence = 0.0
        
        # Try each template
        for template in self.templates:
            try:
                match = template.matches(text)
                if match and match.confidence > best_confidence:
                    best_template = template
                    best_match = match
                    best_confidence = match.confidence
                    
            except Exception as e:
                logger.warning(f"Error matching template {template.name}: {e}")
                continue
        
        if not best_template or not best_match:
            logger.info("No template matched the receipt")
            return None
        
        # Parse with the best template
        try:
            result = best_template.parse(text, best_match)
            logger.info(f"Successfully parsed with template {result.template_name} "
                       f"(confidence: {result.confidence:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing with template {best_template.name}: {e}")
            return None
    
    def get_template_by_name(self, name: str) -> Optional[BaseTemplate]:
        """Get template by name."""
        for template in self.templates:
            if template.name == name:
                return template
        return None
    
    def add_template(self, template: BaseTemplate):
        """Add a custom template."""
        if not isinstance(template, BaseTemplate):
            raise ValueError("Template must inherit from BaseTemplate")
        
        self.templates.append(template)
        logger.info(f"Added custom template: {template.name}")
    
    def get_supported_vendors(self) -> Dict[str, List[str]]:
        """Get list of supported vendors by template."""
        vendors = {}
        for template in self.templates:
            vendors[template.name] = template.vendor_patterns
        return vendors
    
    def get_template_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded templates."""
        return {
            'total_templates': len(self.templates),
            'template_names': [t.name for t in self.templates],
            'average_confidence_threshold': sum(t.confidence_threshold for t in self.templates) / len(self.templates) if self.templates else 0,
            'supported_vendors': sum(len(t.vendor_patterns) for t in self.templates)
        }
    
    def test_template_coverage(self, test_texts: List[str]) -> Dict[str, Any]:
        """Test template coverage against sample texts."""
        results = {
            'total_tests': len(test_texts),
            'matched': 0,
            'unmatched': 0,
            'template_usage': {},
            'coverage_percentage': 0.0
        }
        
        for text in test_texts:
            result = self.parse_with_template(text)
            if result:
                results['matched'] += 1
                template_name = result.template_name
                results['template_usage'][template_name] = results['template_usage'].get(template_name, 0) + 1
            else:
                results['unmatched'] += 1
        
        results['coverage_percentage'] = (results['matched'] / results['total_tests']) * 100 if results['total_tests'] > 0 else 0
        
        return results