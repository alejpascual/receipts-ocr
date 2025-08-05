# Audit System Enhancements

## Overview
Enhanced the receipt processing system with comprehensive audit tracking to understand why files go missing during processing. This addresses the user's frustration with missing documents by providing complete visibility into what happens to every file.

## Key Features Added

### 1. FileAuditTracker Class
- Tracks every file from discovery through processing
- Records status at each stage: found → ocr_complete → processed/review/failed
- Captures reason for failures or filtering
- Located in `src/cli.py`

### 2. Enhanced Debug Mode
- `--debug` flag enables detailed parsing logs
- Shows amount selection decisions
- Shows category classification reasoning
- Shows date parsing attempts
- Logs from all modules (parse, classify, ocr)

### 3. Audit Report Generation
- Terminal display shows file counts by status
- Lists files that failed or were filtered with reasons
- Saves detailed audit report file with timestamp
- Shows exactly why files don't appear in final output

## Usage

### Running with Audit and Debug
```bash
python3 -m src.cli run --in "./receipts" --out "./output" --debug --summary
```

### Output Includes
1. **Terminal Summary**: Quick overview of file processing status
2. **Audit Report File**: `audit_report_YYYYMMDD_HHMMSS.txt` with detailed status for every file
3. **Debug Logs**: Detailed parsing decisions when --debug is used

## What This Solves

1. **"Why are files missing?"** - Audit report shows exactly what happened to each file
2. **"Why did parsing fail?"** - Debug logs show detailed parsing attempts
3. **"What needs manual review?"** - Clear status tracking for review items
4. **No more separate debug scripts** - Everything integrated into main CLI

## Technical Implementation

The audit system hooks into the existing processing pipeline:
- `find_receipt_files()`: Registers all discovered files
- `process_single_file()`: Updates status at each processing stage
- `process_batch()`: Generates final audit report

No existing functionality was broken - all tests pass and the system maintains backward compatibility.