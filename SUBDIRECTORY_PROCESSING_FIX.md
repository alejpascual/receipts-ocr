# Subdirectory Processing Fix - Critical Issue Resolution

## Problem Identified
Invoice files in subdirectories (e.g., `March 2025/invoice-slimblade.pdf`) were not being OCR'd initially, causing them to be completely missing from Excel output.

## Root Cause
The initial OCR processing may not have included all subdirectories, or files were added after the initial OCR run.

## Solution Implemented

### 1. Immediate Fix
Created `process_missing_invoices.py` to OCR the specific missing files:
- `/Users/alejpascual/Downloads/3. March 2025/March 2025/invoice-slimblade.pdf`
- `/Users/alejpascual/Downloads/3. March 2025/March 2025/invoice-desk.pdf`

Result: Both files now included in Excel output (sent to review queue for category determination).

### 2. Long-term Solution
Created `check_and_process_missing_ocr.py` that:
- Scans all source directories including subdirectories
- Compares against existing OCR JSON files using MD5 hashes
- Identifies any files missing OCR processing
- Allows batch processing of all missing files

## How to Use the Fix

### Check for Missing Files
```bash
python3 check_and_process_missing_ocr.py
```

### Process All PDFs in a Directory (Including Subdirectories)
The CLI already supports recursive scanning:
```bash
./receipts run --in "/Users/alejpascual/Downloads/3. March 2025" --out ./out --device mps
```

### Important Notes
1. The CLI's `find_receipt_files()` method uses `rglob()` which searches subdirectories
2. Always verify OCR JSON files exist before regenerating Excel
3. Files without dates go to REVIEW, not skipped entirely

## Prevention Checklist
1. After adding new PDFs, run `check_and_process_missing_ocr.py`
2. Verify OCR JSON count matches source PDF count
3. Check subdirectories explicitly when troubleshooting missing files
4. Use full paths when processing specific directories

## Key Insight
The difference between "file not found" and "file in review queue" is critical - always ensure files are processed even if they need manual review.