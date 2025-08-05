#!/usr/bin/env python3
"""Process specific missing invoice files that weren't OCR'd."""

import sys
import os
from pathlib import Path

sys.path.append('src')
from ocr import OCRProcessor

def main():
    # Initialize OCR processor
    ocr_processor = OCRProcessor(device="mps", lite=False)
    
    # Output directory for OCR JSON files
    output_dir = Path(os.environ.get('OCR_DIR', '/Users/alejpascual/Downloads/receipts-output/ocr_json'))
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # List of missing invoice files
    missing_files = [
        "/Users/alejpascual/Downloads/3. March 2025/March 2025/invoice-slimblade.pdf",
        "/Users/alejpascual/Downloads/3. March 2025/March 2025/invoice-desk.pdf",
        "/Users/alejpascual/Downloads/Non-food receipts 2025/March 2025/invoice-slimblade.pdf",
        "/Users/alejpascual/Downloads/Non-food receipts 2025/March 2025/invoice-desk.pdf"
    ]
    
    print(f"Processing {len(missing_files)} missing invoice files...")
    print(f"Output directory: {output_dir}")
    
    processed = 0
    failed = 0
    
    for file_path in missing_files:
        pdf_path = Path(file_path)
        if pdf_path.exists():
            try:
                print(f"\nProcessing: {pdf_path}")
                ocr_result = ocr_processor.extract_text_from_pdf(pdf_path, output_dir)
                print(f"✅ Successfully processed: {pdf_path.name}")
                print(f"   - Confidence: {ocr_result['confidence']:.2f}")
                print(f"   - Text preview: {ocr_result['full_text'][:100]}...")
                processed += 1
            except Exception as e:
                print(f"❌ Failed to process {pdf_path}: {e}")
                failed += 1
        else:
            print(f"⚠️  File not found: {pdf_path}")
    
    print(f"\n{'='*50}")
    print(f"Processing complete!")
    print(f"✅ Processed: {processed}")
    print(f"❌ Failed: {failed}")
    print(f"\nNow re-run the March Excel generation to include these invoices.")

if __name__ == "__main__":
    main()