# Receipt OCR Processing System - Change Log

## 2025-08-05 - Classification and Filename Fixes

### 🎯 Major Classification Improvements

#### Suica/Train Receipt Classification Fix
- **Problem**: Suica train receipts being misclassified as "Software and Services" instead of "travel"
- **Solution**: Enhanced `rules/categories.yml` travel category with Japanese transport patterns:
  ```yaml
  travel:
    keywords:
      - "◇利用日"      # Usage date marker
      - "◇利用金額"    # Usage amount marker  
      - "利用日"
      - "利用金額"
      - "入金額"
      - "支払い方法:Apple Pay"
  ```
- **Files Changed**: `rules/categories.yml`

#### Coffee Receipt Classification Fix
- **Problem**: Coffee purchases misclassified as other categories instead of "entertainment"
- **Solution**: Enhanced entertainment category with comprehensive coffee keywords:
  ```yaml
  entertainment:
    keywords:
      - "ドリップ"     # Drip coffee
      - "ブレンド"     # Blend
      - "モカ"         # Mocha
      - "アメリカーノ"   # Americano
      - "カプチーノ"    # Cappuccino
      - "ラテ"         # Latte
      - "エスプレッソ"  # Espresso
  ```
- **Files Changed**: `rules/categories.yml`

#### ChatGPT Invoice Description Fix
- **Problem**: ChatGPT invoices not showing "ChatGPT" in description field
- **Solution**: Added high-priority ChatGPT detection in `src/parse.py`:
  ```python
  # ChatGPT/AI Service patterns (high priority)
  if any(keyword in text_lower for keyword in ['chatgpt', 'openai', 'gpt-4', 'gpt-3']):
      return "ChatGPT"
  ```
- **Files Changed**: `src/parse.py`

### 📁 Filename Preservation Fix

#### IMG File Extension Issue
- **Problem**: IMG files (like `IMG_FC53181AF2A9-1.jpeg`) being converted to `.pdf` extensions in Excel output
- **Root Cause**: Filename cleaning logic in `src/export.py` defaulting all files to `.pdf` extension
- **Solution**: Enhanced filename preservation logic:
  ```python
  if base_name.startswith('IMG_'):
      if '.' in base_name:
          file_name = base_name  # Already has extension
      else:
          file_name = base_name + '.jpeg'  # Default IMG files to .jpeg
  elif any(base_name.lower().endswith(ext) for ext in ['.jpeg', '.jpg', '.png', '.gif', '.bmp']):
      file_name = base_name  # Keep image extension
  else:
      file_name = base_name + '.pdf'  # Default to PDF for non-images
  ```
- **Files Changed**: `src/export.py`
- **Testing**: Verified with October 2024 processing - IMG files now maintain proper `.jpeg` extension

### 📊 Processing Results

#### Monthly Excel Generation Completed
- **February 2025**: 33 transactions processed (reprocessed with --force-ocr to capture all receipts)
- **January 2025**: Fixed date filtering to exclude April/May invoices, proper incorporation docs included
- **December 2024**: 8 transactions processed with classification fixes applied
- **November 2024**: Successfully processed with enhanced classification
- **October 2024**: 33 transactions processed with filename preservation fix

### 🔧 Technical Enhancements

#### Enhanced Description Context Extraction
- Added `_get_software_description()` method for software service descriptions
- Enhanced `_get_travel_description()` with Suica-specific patterns
- Improved category-aware description generation in `extract_description_context()`

#### Review Queue Improvements
- Better confidence thresholds for classification accuracy
- Enhanced category conflict detection
- Improved high-value transaction flagging

### 🚀 Git Commits Made

1. **c4313d8**: Document critical fixes and lessons learned
2. **2395429**: Enhance Japanese receipt processing system  
3. **65f5c0f**: Fix filename display and enhance amount parsing logic
4. **c525fbe**: Excel Design Makeover: Professional styling with beautiful colors
5. **2bf51c2**: Major enhancements: PNG support, amount parsing fixes, and category updates
6. **b87ebb3**: Fix filename preservation for image files in Excel export

### 📋 Files Modified in This Session

**Core Processing Files**:
- `src/export.py` - Filename preservation logic
- `src/parse.py` - ChatGPT description detection
- `rules/categories.yml` - Enhanced travel and entertainment categories

**Generation Scripts Created**:
- `regenerate_february_only.py` - February 2025 processing
- `regenerate_january_fixed.py` - January 2025 with date filtering
- `regenerate_january_only.py` - Initial January processing

**Documentation**:
- `CLAUDE.md` - Development notes and technical details
- `CRITICAL_FIXES_NEEDED.md` - Priority fix documentation
- `FIX_IMPROVEMENTS.md` - System improvement tracking

### ⚡ Performance Impact

- **Classification Accuracy**: Significant improvement in Suica/travel and coffee/entertainment categorization
- **Filename Display**: Fixed missing filenames in Excel output, now showing proper extensions
- **Processing Speed**: Maintained with enhanced classification rules
- **Data Integrity**: Better handling of Japanese receipt patterns and edge cases

### 🔍 Validation Methods

- Cross-checked classification results against user corrections
- Tested filename preservation with actual IMG files from October 2024
- Verified ChatGPT description extraction with real invoice data
- Confirmed proper date filtering to prevent cross-month contamination

---

## Previous Changes (Pre-2025-08-05)

See `CLAUDE.md` for earlier development notes including:
- Date parsing OCR error correction (2025-08-04)
- High-value transaction protection (2025-08-04) 
- Amount parsing お支払金額 support (2025-08-04)
- Excel export filename display fixes (2025-08-04)