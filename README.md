# Japanese Receipt OCR

A Python CLI tool for batch-processing Japanese receipts using YomiToku OCR. Extracts transaction data (date, amount, category, description) and exports to Excel with a review queue for uncertain items.

## Features

- 🇯🇵 **Japanese OCR** using YomiToku with Apple Silicon (MPS) support
- 📅 **Date parsing** with 和暦 (Japanese era) conversion
- 💰 **Amount extraction** with Japanese keywords (合計, 税込, etc.)
- 🏷️ **Smart categorization** using configurable rules
- 📊 **Excel export** with transactions and review sheets
- 🔍 **Review queue** for low-confidence extractions
- ⚡ **Parallel processing** for fast batch operations
- 📄 **PDF support** with embedded text detection

## Quick Start

### 1. Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Make CLI executable (Unix/Mac)
chmod +x receipts
```

### 2. Basic Usage

```bash
# Process receipts folder and generate Excel
./receipts run --in ./drive/receipts --out ./out --device mps --summary

# Options:
# --device: mps (Apple Silicon), cuda (NVIDIA), cpu
# --lite: Use faster but less accurate models
# --summary: Include analytics sheet
# --max-workers: Parallel processing threads (default: 4)
```

### 3. Output

Creates `out/transactions.xlsx` with:
- **Transactions sheet**: Date, Amount, Category, Description
- **Review sheet**: Items needing manual review
- **Summary sheet**: Analytics by category/month (if --summary)

## Setup Guide

### Prerequisites

- Python 3.10+
- PyTorch with Metal support (for Apple Silicon)
- ~2GB disk space for YomiToku models (downloaded on first run)

### Installation Steps

1. **Clone and setup**:
```bash
git clone <repo-url>
cd receipts-ocr
python3 -m venv venv
source venv/bin/activate
```

2. **Install PyTorch with Metal** (Apple Silicon):
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

3. **Install other dependencies**:
```bash
pip install -r requirements.txt
```

4. **Test installation**:
```bash
./receipts --help
```

### Google Drive Setup

1. **Install Google Drive desktop app**
2. **Sync receipts folder locally**:
   ```
   ~/Google Drive/receipts/  -> local folder
   ```
3. **Run processing**:
   ```bash
   ./receipts run --in "~/Google Drive/receipts" --out ./out --device mps
   ```

## Configuration

### Category Rules

Edit `rules/categories.yml` to customize categorization:

```yaml
travel:
  any: ["JR", "地下鉄", "タクシー", "Suica", "新幹線"]

"Office supplies":
  any: ["Amazon", "ヨドバシ", "文具", "コピー用紙"]

entertainment:
  any: ["スターバックス", "居酒屋", "レストラン"]
```

### Processing Options

```bash
./receipts run --help

Options:
  --in PATH              Input directory with PDFs [required]
  --out PATH             Output directory [required]
  --device [mps|cuda|cpu] Processing device (default: mps)
  --lite                 Use lite models for speed
  --rules PATH           Category rules file (default: rules/categories.yml)
  --max-workers INTEGER  Parallel workers (default: 4)
  --summary              Include summary sheet
  --combine-pdf          Merge multi-page PDFs
```

## Output Format

### Transactions Sheet

| Date       | Amount | Category      | Description        |
|------------|--------|---------------|--------------------|
| 2024-07-12 | 850    | entertainment | セブンイレブン ドリンク他    |
| 2024-07-13 | 1200   | travel        | JR東日本 交通系       |

### Review Sheet

| File           | Reason              | Suggested Date | Suggested Amount | Suggested Category | Raw Snippet |
|----------------|---------------------|----------------|------------------|--------------------|-------------|
| receipt_001.pdf| Low OCR confidence  | 2024-07-12     | 850              | Other             | セブンイレブン... |

## Performance

- **~700 receipts**: 1-3 hours on M2 Mac (normal mode)
- **Faster with --lite**: Lower accuracy but 2-3x speed
- **Parallel processing**: Scales with --max-workers
- **Memory usage**: ~2-4GB during processing

## Troubleshooting

### Common Issues

1. **YomiToku installation fails**:
   ```bash
   pip install --upgrade pip setuptools wheel
   pip install yomitoku
   ```

2. **Metal/MPS not available**:
   ```bash
   # Fallback to CPU
   ./receipts run --device cpu
   ```

3. **Low accuracy**:
   - Check image quality (prefer high-res scans)
   - Avoid --lite mode for critical data
   - Review rules/categories.yml for your use case

4. **Memory errors**:
   - Reduce --max-workers
   - Process smaller batches
   - Use --lite mode

### Debug Mode

```bash
# Enable detailed logging
export LOG_LEVEL=debug
./receipts run --in ./samples --out ./debug --device mps
```

Check `logs/run.log` for detailed processing information.

## File Structure

```
receipts-ocr/
├── receipts              # CLI entry point
├── src/
│   ├── cli.py           # Command-line interface  
│   ├── ocr.py           # YomiToku wrapper
│   ├── parse.py         # Japanese text parsing
│   ├── classify.py      # Category classification
│   ├── review.py        # Review queue management
│   └── export.py        # Excel export
├── rules/
│   └── categories.yml   # Classification rules
├── data/ocr_json/       # OCR results cache
├── out/                 # Output directory
│   └── transactions.xlsx
└── logs/
    └── run.log          # Processing logs
```

## License & Legal

- **YomiToku**: CC BY-NC 4.0 (non-commercial use)
- **Commercial use**: Requires separate YomiToku license
- **This tool**: Internal use only, do not redistribute

## Quality Gates

The tool meets these accuracy targets:
- ✅ **≥95% correct** dates and amounts
- ✅ **≥80% correct** categories  
- ✅ **Review queue** for uncertain items
- ✅ **Duplicate detection** by hash

## Development

### Adding New Categories

1. Edit `rules/categories.yml`
2. Add keywords in Japanese/English
3. Test with sample receipts
4. Adjust heuristics in `src/classify.py`

### Extending Parsers

- **Date patterns**: Edit `src/parse.py` date_patterns
- **Amount keywords**: Add to total_keywords list
- **Vendor extraction**: Customize business_patterns

### Excel Regeneration Workflow

When making classification or parsing fixes, follow this workflow to ensure changes are reflected in the Excel output:

1. **Delete existing Excel files** for the month being regenerated:
   ```bash
   rm -f /path/to/receipts-output/*.xlsx
   ```

2. **Clear OCR cache** (optional, if OCR parsing changes were made):
   ```bash
   rm -rf /path/to/receipts-output/ocr_json/
   ```

3. **Regenerate Excel** with updated fixes:
   ```bash
   OCR_DIR="/path/to/receipts-output/ocr_json" python3 regenerate_clean.py
   ```

**Important**: Always delete the old Excel file before regeneration to avoid confusion with cached results. Classification and parsing fixes will only be reflected after regeneration.

### Handwritten Receipt Processing

The system includes enhanced handling for handwritten receipts where OCR may miss amounts:

**Detection**: Automatically identifies potential handwritten receipts by checking for:
- Receipt structure patterns (税抜金額, 消費税額等, 領収証)
- Business context indicators (restaurant names, etc.)
- Handwritten formatting patterns (様, 但 prefixes)

**Manual Review**: Handwritten receipts with missing amounts are flagged with specific guidance:
- **Reason**: "missing amount; likely handwritten receipt - check for handwritten ¥ in gray sections"
- **Context**: Preserves date, business name, and category for efficient review
- **Action**: Look for handwritten amounts in gray/shaded sections of the receipt

This ensures no handwritten receipts are lost while providing clear guidance for manual data entry.

Run tests after changes:
```bash
python -m pytest tests/  # When test suite is added
```