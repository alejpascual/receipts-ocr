# Critical Improvements Needed Based on Review Feedback

## 1. Amount Parsing Selection Logic

### Problem
System selecting wrong amounts when multiple candidates exist (e.g., choosing ¥1410 instead of ¥1111).

### Fix Needed
Enhance amount selection to:
- Prefer amounts that appear multiple times in the document
- Give higher priority to amounts near "合計" without other keywords
- Reduce priority for amounts near subtotals or intermediate calculations
- When multiple strong candidates exist, prefer the one that appears most frequently

### Implementation
```python
# In parse_amount(), add frequency analysis:
amount_frequency = Counter()
for line in lines:
    amounts = self._extract_amounts_from_line(line)
    for amount, _ in amounts:
        amount_frequency[amount] += 1

# Boost priority for frequently appearing amounts
for idx, (amount, priority, line) in enumerate(amount_candidates):
    frequency_boost = amount_frequency[amount] * 50  # 50 points per occurrence
    amount_candidates[idx] = (amount, priority + frequency_boost, line)
```

## 2. OCR Error Correction Too Aggressive

### Problem
The system is changing ALL May (05) dates to March (03) for high-value documents in 2025, causing May invoices to appear in March Excel.

### Current Broken Logic
```python
if month_int == 5 and '2025' in year:
    logger.warning(f"Potential OCR error detected: Month 05 in high-value document, checking if should be 03")
    # Check for additional context clues
    if 'march' in text.lower() or '03' in text or day_int == 31:
        logger.warning(f"OCR CORRECTION APPLIED: Month 05 → 03 in date {year}/{month}/{day}")
        month_int = 3
```

### Fix Needed
Remove or significantly restrict the OCR correction:
```python
# Only apply correction if there's STRONG evidence
if month_int == 5 and '2025' in year:
    # Only correct if we find explicit March text AND no May indicators
    march_indicators = ['march', '3月', 'mar', '三月']
    may_indicators = ['may', '5月', 'mai', '五月']
    
    has_march = any(ind in text.lower() for ind in march_indicators)
    has_may = any(ind in text.lower() for ind in may_indicators)
    
    if has_march and not has_may and day_int == 31:  # May has 31 days, so this alone isn't enough
        logger.warning(f"OCR CORRECTION APPLIED: Month 05 → 03 based on explicit March text")
        month_int = 3
```

## 3. Category Classification Improvements

### Problem
- Software/Services invoices going to "unknown" category
- Office equipment (desk, Slimblade trackball) not recognized

### Fixes Applied
Enhanced categories.yml with:
- Office supplies: Added "desk", "chair", "IKEA", "shelf", "file", "binder", etc.
- Equipment: Added "Kensington", "Slimblade", "trackball", "mouse", "keyboard", "monitor", etc.
- Software and Services: Added "Setapp", "subscription", "license", specific services like "Dropbox", "GitHub", "Slack", etc.

## 4. Better Description Generation

### Current Issue
Descriptions are too generic (e.g., "office equipment" for a specific Slimblade trackball purchase).

### Improvement Needed
Extract product names from receipts:
```python
def _get_equipment_description(self, text_lower: str, vendor: str) -> str:
    """Get specific equipment description based on product details."""
    # Look for specific product names
    products = {
        'slimblade': 'Slimblade trackball',
        'kensington': 'Kensington device',
        'mouse': 'mouse',
        'keyboard': 'keyboard',
        'monitor': 'monitor',
        'webcam': 'webcam',
        'desk': 'desk',
        'chair': 'office chair'
    }
    
    for keyword, description in products.items():
        if keyword in text_lower:
            return description
    
    return 'office equipment'
```

## 5. Review Queue Reasoning

### Improvement
Make review reasons more specific:
- Instead of "unknown category", specify "Could not determine between Software/Equipment"
- Instead of "low confidence", specify what aspect has low confidence

## Key Takeaways
1. **Conservative OCR Correction**: Only apply corrections with strong evidence
2. **Context-Aware Parsing**: Use frequency analysis and contextual clues
3. **Comprehensive Categories**: Keep expanding category keywords based on real receipts
4. **Specific Descriptions**: Extract actual product/service names when possible
5. **Clear Review Reasons**: Help users understand why items need review

## Summary of Fixes Applied

### 1. Fixed OCR Date Correction
**File**: `src/parse.py`
- Removed aggressive May→March conversion
- Now only corrects with explicit "March" text in document
- Prevents May invoices from appearing in March Excel

### 2. Enhanced Category Classifications
**File**: `rules/categories.yml`
- Added office supplies: desk, chair, IKEA, shelf, file, binder
- Added equipment: Kensington, Slimblade, trackball, mouse, keyboard
- Added software: Setapp, subscription, Dropbox, GitHub, Slack

### 3. Added Equipment Description Extraction
**File**: `src/parse.py`
- New `_get_equipment_description()` method
- Extracts specific product names (Slimblade trackball, desk, etc.)
- Provides more meaningful descriptions than generic "office equipment"

### 4. Enhanced Amount Selection Logic
**File**: `src/parse.py`
- Already has frequency analysis with 300 points per occurrence
- Added extra 500 point boost for most frequent amount
- Helps select ¥1111 over ¥1410 when ¥1111 appears more often

## Future Improvements Still Needed

1. **Smarter Amount Pattern Recognition**
   - Detect repeating digits (1111, 2222) as likely prices
   - Prefer "round" numbers in Japanese pricing patterns

2. **Better Review Reasons**
   - Instead of "unknown category", specify conflicting categories
   - Show confidence scores in review reasons

3. **Invoice-Specific Parsing**
   - Special handling for Amazon/online invoices
   - Better detection of invoice totals vs subtotals