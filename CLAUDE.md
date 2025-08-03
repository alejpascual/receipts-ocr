# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
- **Filename**: Auto-detected from transaction dates (e.g., "transactions_August_2024.xlsx")
- **Fallback naming**: "transactions_Mixed_Months.xlsx" or "transactions_Unknown_Period.xlsx" 
- **Main Columns**: File Name, Date, Amount, Category, Description, Review Status, Review Reason, Raw Snippet
- **Review Status**: "OK" for normal transactions, "REVIEW" for items needing manual attention  
- **Review fields**: Only populated for transactions requiring review
- **Summary Section**: Key statistics included at the top of the sheet (total transactions, amounts, category breakdown)
- **Design Goal**: Single tab per month for easy integration into monthly tracking Excel

## Licensing and Legal
- YomiToku: CC BY-NC 4.0 (non-commercial use only)
- Commercial use requires separate YomiToku license
- Internal tool - do not redistribute without license clearance