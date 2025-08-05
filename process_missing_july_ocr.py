#!/usr/bin/env python3
"""Process missing July 2024 OCR files that were not processed initially."""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.append('src')

from ocr import OCRProcessor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # Paths
    july_folder = Path('/Users/alejpascual/Downloads/7. July 2024')
    ocr_output = Path('/Users/alejpascual/Downloads/receipts-output/ocr_json')
    
    # Get all source files
    source_files = []
    for f in july_folder.iterdir():
        if f.is_file() and f.suffix.lower() == '.pdf':
            source_files.append(f)
    
    # Get existing JSON files (to avoid reprocessing)
    existing_jsons = set()
    for f in ocr_output.glob('2024-07*.json'):
        # Remove hash suffix to get base name
        base_name = '_'.join(f.stem.split('_')[:-1])
        existing_jsons.add(base_name)
    
    # Find missing files
    missing_files = []
    for source_file in source_files:
        if source_file.stem not in existing_jsons:
            missing_files.append(source_file)
    
    print(f'Found {len(source_files)} total July files')
    print(f'Found {len(existing_jsons)} existing JSON files')
    print(f'Need to process {len(missing_files)} missing files')
    
    if not missing_files:
        print('✅ All files already processed!')
        return
    
    # Initialize OCR processor
    print('Initializing OCR processor...')
    try:
        ocr_processor = OCRProcessor(device="mps")  # Use Metal Performance Shaders on Mac
    except Exception as e:
        print(f'Failed to initialize OCR: {e}')
        print('Trying with CPU...')
        ocr_processor = OCRProcessor(device="cpu")
    
    # Process missing files
    print(f'\\nProcessing {len(missing_files)} missing files...')
    success_count = 0
    error_count = 0
    
    for i, pdf_file in enumerate(missing_files, 1):
        try:
            print(f'[{i}/{len(missing_files)}] Processing {pdf_file.name}...')
            
            # Process with OCR
            result = ocr_processor.extract_text_from_pdf(pdf_file, ocr_output)
            
            # Quick validation
            if result.get('full_text', '').strip():
                success_count += 1
                print(f'  ✅ Success - extracted {len(result["full_text"])} characters')
            else:
                error_count += 1
                print(f'  ⚠️  No text extracted')
                
        except Exception as e:
            error_count += 1
            print(f'  ❌ Error: {e}')
            continue
    
    print(f'\\n=== OCR PROCESSING COMPLETE ===')
    print(f'✅ Successfully processed: {success_count} files')
    print(f'❌ Failed: {error_count} files')
    print(f'📊 Success rate: {success_count/(success_count+error_count)*100:.1f}%')
    
    # Now verify total JSON files
    total_jsons = len(list(ocr_output.glob('2024-07*.json')))
    print(f'\\n📁 Total July 2024 JSON files now: {total_jsons}')
    print(f'🎯 Target was: {len(source_files)} (all source files)')

if __name__ == '__main__':
    main()