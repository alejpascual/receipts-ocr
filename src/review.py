"""Review queue generator for uncertain or low-confidence extractions."""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ReviewItem:
    """Represents an item that needs manual review."""
    file_path: str
    reason: str
    suggested_date: Optional[str] = None
    suggested_amount: Optional[int] = None
    suggested_category: Optional[str] = None
    raw_snippet: str = ""
    confidence_scores: Optional[Dict[str, float]] = None


class ReviewQueue:
    """Manages items that need manual review."""
    
    def __init__(self, confidence_thresholds: Optional[Dict[str, float]] = None):
        """
        Initialize review queue.
        
        Args:
            confidence_thresholds: Minimum confidence scores for each field
        """
        self.items: List[ReviewItem] = []
        self.thresholds = confidence_thresholds or {
            'date': 0.7,
            'amount': 0.7,
            'category': 0.3,  # Less aggressive - only flag very poor category confidence
            'ocr': 0.3        # Less aggressive - only flag very poor OCR quality
        }
    
    def should_review(self, 
                     date: Optional[str], 
                     amount: Optional[int], 
                     category: str, 
                     category_confidence: float,
                     ocr_confidence: float,
                     file_path: str,
                     ocr_text: str = "") -> bool:
        """
        Determine if a receipt should be sent to review.
        
        Args:
            date: Extracted date
            amount: Extracted amount  
            category: Assigned category
            category_confidence: Confidence score for category
            ocr_confidence: Overall OCR confidence
            file_path: Path to the file
            
        Returns:
            True if item should be reviewed
        """
        reasons = []
        
        # Check missing critical fields
        if not date:
            reasons.append("No valid date found")
        
        if not amount:
            # Check if this might be a handwritten receipt with missing OCR
            handwritten_indicators = [
                # Text content indicators
                any(indicator in ocr_text.lower() for indicator in ['curry', '様', '但', '領収証', '税抜金額']),
                # File path indicators  
                any(indicator in file_path.lower() for indicator in ['curry', 'restaurant']),
                # OCR confidence indicators
                ocr_confidence < 0.9  # Higher threshold since handwritten receipts can have mixed confidence
            ]
            
            if date and any(handwritten_indicators):
                reasons.append("missing amount; likely handwritten receipt - check for handwritten ¥ in gray sections")
            else:
                reasons.append("missing amount")
        
        # Check confidence thresholds
        if category_confidence < self.thresholds['category']:
            reasons.append(f"Low category confidence ({category_confidence:.2f})")
        
        if ocr_confidence < self.thresholds['ocr']:
            reasons.append(f"Low OCR confidence ({ocr_confidence:.2f})")
        
        # Special handling for very low OCR confidence (likely handwritten)
        if ocr_confidence < 0.3:
            reasons.append("Likely handwritten receipt")
        
        # Check for conflicting data
        if category == "Other":
            reasons.append("Category could not be determined")
        
        if reasons:
            logger.info(f"Sending {Path(file_path).name} to review: {'; '.join(reasons)}")
            return True
        
        return False
    
    def add_item(self, 
                file_path: str,
                reason: str,
                suggested_date: Optional[str] = None,
                suggested_amount: Optional[int] = None,
                suggested_category: Optional[str] = None,
                raw_snippet: str = "",
                confidence_scores: Optional[Dict[str, float]] = None):
        """Add an item to the review queue."""
        
        item = ReviewItem(
            file_path=file_path,
            reason=reason,
            suggested_date=suggested_date,
            suggested_amount=suggested_amount,
            suggested_category=suggested_category,
            raw_snippet=raw_snippet,
            confidence_scores=confidence_scores
        )
        
        self.items.append(item)
        logger.debug(f"Added to review queue: {Path(file_path).name} - {reason}")
    
    def add_from_extraction(self,
                          file_path: str,
                          date: Optional[str],
                          amount: Optional[int],
                          category: str,
                          category_confidence: float,
                          ocr_confidence: float,
                          raw_text: str):
        """
        Add item to review if extraction is uncertain.
        
        Args:
            file_path: Path to the processed file
            date: Extracted date
            amount: Extracted amount
            category: Assigned category
            category_confidence: Category confidence score
            ocr_confidence: OCR confidence score
            raw_text: Raw OCR text for snippet
        """
        if not self.should_review(date, amount, category, category_confidence, ocr_confidence, file_path):
            return
        
        # Generate reason summary
        reasons = []
        if not date:
            reasons.append("missing date")
        if not amount:
            reasons.append("missing amount")
        if category_confidence < self.thresholds['category']:
            reasons.append("low category confidence")
        if ocr_confidence < self.thresholds['ocr']:
            reasons.append("low OCR quality")
        if category == "Other":
            reasons.append("unknown category")
        
        reason = "; ".join(reasons)
        
        # Create snippet from raw text (first 200 chars), clean for Excel
        snippet = raw_text.replace('\\n', ' ')[:200]
        # Remove characters that Excel doesn't like
        snippet = ''.join(char for char in snippet if ord(char) >= 32 or char in '\\t\\n\\r')
        if len(raw_text) > 200:
            snippet += "..."
        
        confidence_scores = {
            'category': category_confidence,
            'ocr': ocr_confidence
        }
        
        self.add_item(
            file_path=file_path,
            reason=reason,
            suggested_date=date,
            suggested_amount=amount,
            suggested_category=category,
            raw_snippet=snippet,
            confidence_scores=confidence_scores
        )
    
    def detect_conflicts(self, extractions: List[Dict[str, Any]]) -> List[ReviewItem]:
        """
        Detect conflicts across multiple receipts.
        
        Args:
            extractions: List of extraction results
            
        Returns:
            List of additional review items for conflicts
        """
        conflicts = []
        
        # Group by vendor and date to find potential duplicates
        by_vendor_date = {}
        for extraction in extractions:
            key = (extraction.get('vendor', ''), extraction.get('date', ''))
            if key not in by_vendor_date:
                by_vendor_date[key] = []
            by_vendor_date[key].append(extraction)
        
        # Check for potential duplicates
        for (vendor, date), group in by_vendor_date.items():
            if len(group) > 1:
                # Check if amounts are very similar (within 3%)
                amounts = [item.get('amount', 0) for item in group if item.get('amount')]
                if len(amounts) > 1:
                    max_amount = max(amounts)
                    min_amount = min(amounts)
                    
                    if max_amount > 0 and (max_amount - min_amount) / max_amount <= 0.03:
                        # Potential duplicates
                        for item in group:
                            conflicts.append(ReviewItem(
                                file_path=item.get('file_path', ''),
                                reason="Potential duplicate receipt",
                                suggested_date=date,
                                suggested_amount=item.get('amount'),
                                suggested_category=item.get('category'),
                                raw_snippet=f"Similar to {len(group)-1} other receipts: {vendor} on {date}"
                            ))
        
        return conflicts
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the review queue."""
        if not self.items:
            return {"total": 0}
        
        reason_counts = {}
        category_issues = 0
        ocr_issues = 0
        missing_data = 0
        
        for item in self.items:
            # Count reason types
            reasons = item.reason.split(';')
            for reason in reasons:
                reason = reason.strip()
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            
            # Categorize issue types
            if 'category' in item.reason.lower():
                category_issues += 1
            if 'ocr' in item.reason.lower():
                ocr_issues += 1
            if 'missing' in item.reason.lower():
                missing_data += 1
        
        return {
            "total": len(self.items),
            "category_issues": category_issues,
            "ocr_issues": ocr_issues,
            "missing_data": missing_data,
            "reason_breakdown": reason_counts
        }
    
    def clear(self):
        """Clear all items from the review queue."""
        self.items.clear()
        logger.info("Review queue cleared")