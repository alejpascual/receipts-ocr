# PROJECT.md

This file provides development guidance and documentation for this repository.

## Project Overview

A Python CLI tool for batch-processing Japanese receipts using YomiToku OCR. Supports PDF and image files (PNG, JPG, JPEG). Extracts transaction data (date, amount, category, description) and exports to Excel with a review queue for uncertain items. Designed for ~700 receipt processing with Apple Silicon optimization.

## Common Commands

### Setup and Installation
```bash
# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
chmod +x receipts

# Install PyTorch with Metal support (Apple Silicon)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### Processing Receipts
```bash
# Standard processing with summary
./receipts run --in ./drive/receipts --out ./out --device mps --summary

# Performance options
./receipts run --in ./input --out ./output --device mps --lite --max-workers 8

# Regenerate Excel from existing OCR cache
python3 regenerate_clean.py
```

### Testing and Development
```bash
# Debug mode with detailed logging
export LOG_LEVEL=debug
./receipts run --in ./samples --out ./debug --device mps

# Check logs
tail -f logs/run.log
```

## Architecture Overview

### Core Pipeline (6 stages)
1. **File Discovery**: Hash-based duplicate detection, recursive search for PDF and image files (PNG/JPG/JPEG)
2. **Text Extraction**: Embedded text detection → OCR fallback (YomiToku)  
3. **Data Parsing**: Japanese date/amount/vendor extraction with 和暦 support
4. **Classification**: Rule-based categorization using fuzzy matching
5. **Review Queue**: Confidence-based filtering for manual review
6. **Excel Export**: Multi-sheet output (Transactions/Review/Summary)

### Key Components
- **`src/ocr.py`**: YomiToku wrapper with Apple Silicon (MPS) optimization
- **`src/parse.py`**: Japanese text parsing (dates, amounts, vendors) with priority scoring
- **`src/classify.py`**: Category classification using rules + heuristics 
- **`src/review.py`**: Quality assurance and confidence thresholds
- **`src/export.py`**: Excel generation with data validation
- **`src/cli.py`**: Main orchestration and CLI interface
- **`regenerate_clean.py`**: Reprocessing script using cached OCR results

### Configuration
- **`rules/categories.yml`**: 15 predefined business categories with Japanese/English keywords (including Software/Services for subscriptions)
- **`requirements.txt`**: Python dependencies including YomiToku, openpyxl, rapidfuzz
- **`setup.py`**: Package configuration and CLI entry point

## Japanese Text Processing Specifics

### Date Parsing
- Handles 和暦 (Japanese era): 令和6年7月12日 → 2024-07-12
- Multiple patterns: YYYY年MM月DD日, YYYY/MM/DD, YYYY-MM-DD
- OCR error tolerance: spaced versions like "2025年 6月 24日"

### Amount Extraction  
- Priority keywords: 合計 > 総合計 > 税込合計 > お買上げ
- Avoids: 小計, 税抜, お釣り, お預り, 内消費税
- Smart recovery for suspiciously low amounts (≤¥500)
- Checks adjacent lines for avoid keywords (e.g., "¥200" followed by "お釣り")

### Category Classification
- Geographic logic: Tokyo locations → entertainment (not travel)
- Context-aware: 居酒屋 + 会議 → meetings vs entertainment
- Fuzzy matching for OCR errors using rapidfuzz
- Conflict resolution with penalty/boost scoring

## Development Guidelines

### Adding New Categories
1. Edit `rules/categories.yml` with Japanese/English keywords
2. Test with sample receipts using debug mode
3. Adjust heuristics in `src/classify.py` if needed
4. Run full batch to validate accuracy

### Fixing Parsing Issues
- **Date problems**: Add patterns to `src/parse.py` date_patterns
- **Amount extraction**: Update total_keywords or avoid_keywords lists
- **Classification errors**: Check Tokyo detection logic and keyword conflicts
- Always test with `regenerate_clean.py` after changes

### Performance Considerations
- YomiToku model downloads ~2GB on first run
- Apple Silicon MPS significantly faster than CPU
- Parallel processing scales with --max-workers (default: 4)
- Use --lite for 2-3x speed with lower accuracy
- Memory usage: ~2-4GB during processing

### Quality Gates
- ≥95% accuracy for dates and amounts
- ≥80% accuracy for categories  
- Review queue handles uncertain items
- Never crash on individual receipt failures

### OCR Cache System
- `batch-results/ocr_json/` stores YomiToku results
- Hash-based duplicate detection prevents reprocessing
- `regenerate_clean.py` rebuilds Excel from cache without re-OCR
- Useful for iterating on parsing/classification logic

### Output Structure
```
out/
├── transactions_June_2025.xlsx  # Single consolidated sheet named by period
├── ocr_json/                   # Cached OCR JSON per PDF
└── logs/run.log               # Processing logs with warnings/errors
```

**Excel Format (Single Sheet):**
- **Filename**: Auto-detected from transaction dates (e.g., "transactions_June_2025.xlsx")
- **Fallback naming**: "transactions_Mixed_Months.xlsx" or "transactions_Unknown_Period.xlsx" 
- **Main Columns**: File Name, Date, Amount, Category, Description, Review Status, Review Reason, Raw Snippet
- **CRITICAL**: Use clean PDF filenames (e.g., "2025-06-14 19-48.pdf") NOT verbose OCR JSON names
- **Sorting**: Alphabetical by filename for cross-checking with original folder
- **Title**: Dynamic month/year in summary (e.g., "TRANSACTION SUMMARY - JUNE 2025")
- **Review Status**: "✓ OK" for normal transactions, "⚠ REVIEW" for items needing manual attention  
- **Review fields**: Only populated for transactions requiring review
- **Summary Section**: Key statistics included at the top of the sheet (total transactions, amounts, category breakdown)
- **Design Goal**: Single tab per month for easy integration into monthly tracking Excel

## Critical Fixes and Learnings

### Amount Parsing Issues Fixed (August 2025)

**Issue**: Keyword-based amounts being overridden by frequency detection
- **Problem**: Amounts near "合計" (total) had lower priority than frequent small amounts
- **Root Cause**: Frequency detection (300 points × count) beat keyword priority (1000-1500)
- **Fix**: Boosted keyword priorities: 合計 → 5000-6000, other totals → 4000+
- **Files Changed**: `src/parse.py` lines 200-218
- **Testing**: Verified with receipts extracting wrong totals (¥780 vs ¥8,580)

**Issue**: OCR spacing problems (e.g., "1, 738円" → ¥738 instead of ¥1,738)
- **Root Cause**: Amount patterns didn't handle OCR spaces in numbers
- **Fix**: Enhanced patterns with `\s*` tolerance, clean spaces in extraction
- **Files Changed**: `src/parse.py` lines 33-41, 350-355
- **Testing**: Verified with 2025-06-14 19-48.pdf and similar receipts

**Issue**: OCR digit misreading (e.g., "6" read as "8" giving ¥3,830 vs ¥3,630)
- **Root Cause**: OCR confidence issues with similar-looking digits
- **Fix**: Manual OCR JSON correction for specific cases
- **Files Changed**: Individual OCR JSON files as needed
- **Prevention**: Enhanced frequency detection helps catch obvious errors

### Excel Export Issues Fixed

**Issue**: Verbose OCR JSON filenames in Excel (e.g., "file_hash123.json")
- **Root Cause**: Review items used `Path(item.file_path).name` instead of clean names
- **Fix**: Added clean filename logic for review items in export
- **Files Changed**: `src/export.py` lines 264-269, `regenerate_clean.py` lines 90-96
- **Result**: All filenames now show as "2025-06-14 19-48.pdf" format

**Issue**: Random sorting order making cross-checking difficult
- **Fix**: Alphabetical sorting for both OK and review transactions
- **Files Changed**: `src/export.py` lines 172-173, 278-279
- **Result**: Consistent filename order matching original folder structure

**Issue**: Missing month/year in Excel title
- **Fix**: Dynamic period detection from transaction dates
- **Files Changed**: `src/export.py` _determine_period_from_transactions method
- **Result**: Titles like "TRANSACTION SUMMARY - JUNE 2025"

### File Processing Issues Fixed

**Issue**: Missing receipts from subfolders
- **Example**: Invoice(5830_4634).pdf not processed from "June 2025/" subfolder
- **Fix**: Manual processing of missed files and inclusion in OCR cache
- **Prevention**: Always verify file counts: input vs processed

**Issue**: Output file location confusion
- **Root Cause**: Hard-coded paths in regenerate_clean.py
- **Fix**: Environment variables (OCR_DIR, OUTPUT_DIR) with sensible defaults
- **Files Changed**: `regenerate_clean.py` lines 67, 157

### Development Workflow Lessons

**CRITICAL**: Always delete old Excel before regenerating to avoid confusion
**CRITICAL**: Apply systematic fixes to parsing logic, not one-off manual corrections
**CRITICAL**: Test fixes with multiple receipts to ensure no regressions

**Verification Process**:
1. Count input files vs OCR JSON files
2. Test parsing with debug scripts before regenerating
3. Check sample transactions in output logs
4. Verify Excel contains expected transaction count

### Known Edge Cases
- Very poor OCR quality (confidence < 0.5) may require manual review
- Receipts with unusual layouts may need category rule adjustments
- Frequency detection may still fail with highly repetitive amounts (>10 occurrences)

## Licensing and Legal
- YomiToku: CC BY-NC 4.0 (non-commercial use only)
- Commercial use requires separate YomiToku license
- Internal tool - do not redistribute without license clearance