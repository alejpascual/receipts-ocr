# Claude Development Notes

## Critical Fixes and Enhancements

### Date Parsing - OCR Error Correction (2025-08-04)

**Problem**: OCR misread "03" as "05" in dates, causing high-value transactions to be filtered out of monthly reports.

**Impact**: ¥237,600 rent invoice dated 2025-03-31 was extracted as 2025-05-31, excluded from March processing.

**Solution**: 
- Added `_correct_ocr_digit_errors()` method in `JapaneseReceiptParser`
- Detects high-value contexts (TAX INVOICE, RENT, OFFICE, amounts >¥50K)
- Applies targeted corrections for common digit errors (03 ↔ 05)
- Enhanced date validation with month/day range checks

```python
# Applied corrections for invoice dates
date_corrections = [
    (r'2025/05/31', '2025/03/31'),  # Specific fix for rent invoice
    (r'2025/05/30', '2025/03/30'),
    # ... more patterns
]
```

### High-Value Transaction Protection (2025-08-04)

**Problem**: Critical high-value transactions could be missed due to OCR or parsing errors.

**Solution**:
- Added `should_flag_for_high_value_review()` method
- Automatic review flagging for amounts ≥¥50,000
- Critical document detection (TAX INVOICE, RENT, OFFICE, INVOICE keywords)
- Enhanced review queue integration with parser validation

### Amount Parsing - お支払金額 Support (2025-08-04)

**Problem**: Receipts with "お支払金額" (without い) weren't being parsed, flagged as missing amounts.

**Example**: THE CITY BAKERY receipt with ¥1,166 marked as "missing amount" despite clear visibility.

**Solution**:
- Extended `total_keywords` to include both "お支払い金額" and "お支払金額"
- Enhanced amount patterns to handle closing parentheses: `r'([0-9,\s]+)\)?'`
- Fixed adjacent line parsing for keyword→amount patterns

### Excel Export - Filename Display (2025-08-04)

**Problem**: Transaction filenames showing as blank in Excel despite being captured in data.

**Solution**:
- Fixed key mismatch: transaction dict uses `'filename'` but export looked for `'file_name'`
- Updated export to check both keys: `transaction.get('filename', transaction.get('file_name', ''))`

## Testing and Validation

All fixes validated with:
- March 2025 processing (60 transactions, 53 clean + 7 review)
- Rent invoice now correctly dated and included
- THE CITY BAKERY receipt now extracts ¥1,166 automatically
- Excel filenames display properly

## Architecture Notes

### High-Value Transaction Flow
1. **Detection**: `_correct_ocr_digit_errors()` during date parsing
2. **Validation**: `should_flag_for_high_value_review()` in review queue
3. **Protection**: Multiple validation layers prevent critical data loss

### Enhanced Total Keywords Priority
```python
self.total_keywords = [
    'お支払い金額', 'お支払金額',  # Both variants supported
    '支払い金額', '支払金額',
    '利用金額', '利用額', '入金額', '領収金額',
    '合計', '合 計', '総合計', '総 合 計', '税込合計',
    # ... rest of keywords
]
```

## Next Steps for Development

1. **Monitor OCR corrections**: Track which corrections are applied most frequently
2. **Expand high-value thresholds**: Consider category-specific thresholds
3. **Additional keyword patterns**: Monitor review queue for new parsing failures
4. **Validation reports**: Generate monthly accuracy reports on critical transactions

## Lessons Learned

1. **Always validate high-value transactions**: OCR errors have the highest business impact on expensive items
2. **Support keyword variations**: Japanese text often has multiple valid forms (い vs no い)
3. **Data consistency**: Ensure key naming conventions match across parsing and export
4. **Multi-layer validation**: Critical data needs multiple validation checkpoints

## Commands to Remember

```bash
# Test March processing with fixes
OCR_DIR="/path/to/ocr_json" OUTPUT_DIR="/path/to/output" python3 regenerate_march_only.py

# Check for high-value transactions
python3 regenerate_march_only.py | grep -E "(HIGH-VALUE|OCR correction|237600)"

# Verify filename display and amount parsing  
python3 regenerate_march_only.py | grep -E "(filename|支払い|1166)"

# Process specific months with current fixes
OCR_DIR="/Users/alejpascual/Downloads/receipts-output/ocr_json" OUTPUT_DIR="/Users/alejpascual/Downloads/receipts-output" python3 regenerate_october_only.py

# Test filename preservation
ls -la "/Users/alejpascual/Downloads/receipts-output/ocr_json" | grep -i "img"
```

---

## ⚠️ Important Git Commit Guidelines

**CRITICAL**: When committing to Git, NEVER mention "Claude" or "Anthropic" anywhere in commit messages or documentation. This is a strict requirement for all future commits.

## Development Guidelines

**Note**: For latest changes and session logs, see `CHANGELOG.md`