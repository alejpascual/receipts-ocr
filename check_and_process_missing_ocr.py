#!/usr/bin/env python3
"""Check for missing OCR files and process them automatically."""

import sys
import os
from pathlib import Path
import hashlib

sys.path.append('src')
from ocr import OCRProcessor
from cli import ReceiptProcessor

def get_file_hash(file_path: Path) -> str:
    """Generate hash for file to detect duplicates."""
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def find_missing_ocr_files(source_dirs, ocr_dir):
    """Find PDF/image files that haven't been OCR'd yet."""
    # Get all existing OCR JSON files
    ocr_dir = Path(ocr_dir)
    existing_hashes = set()
    
    for json_file in ocr_dir.glob('*.json'):
        # Extract hash from filename (format: filename_hash.json)
        parts = json_file.stem.split('_')
        if parts:
            hash_part = parts[-1]
            if len(hash_part) == 32:  # MD5 hash length
                existing_hashes.add(hash_part)
    
    print(f"Found {len(existing_hashes)} existing OCR JSON files")
    
    # Find all PDF and image files in source directories
    missing_files = []
    patterns = ['*.pdf', '*.PDF', '*.png', '*.PNG', '*.jpg', '*.JPG', '*.jpeg', '*.JPEG']
    
    for source_dir in source_dirs:
        source_path = Path(source_dir)
        if not source_path.exists():
            print(f"⚠️  Source directory not found: {source_dir}")
            continue
            
        for pattern in patterns:
            # Search in directory and all subdirectories
            for file_path in source_path.rglob(pattern):
                file_hash = get_file_hash(file_path)
                if file_hash not in existing_hashes:
                    missing_files.append(file_path)
    
    return missing_files

def main():
    # Configure paths
    source_dirs = [
        "/Users/alejpascual/Downloads/3. March 2025",
        "/Users/alejpascual/Downloads/4. April 2025", 
        "/Users/alejpascual/Downloads/5. May 2025",
        "/Users/alejpascual/Downloads/Non-food receipts 2025"
    ]
    
    ocr_dir = os.environ.get('OCR_DIR', '/Users/alejpascual/Downloads/receipts-output/ocr_json')
    
    print("=== Checking for Missing OCR Files ===")
    print(f"OCR directory: {ocr_dir}")
    print(f"Source directories: {source_dirs}")
    print()
    
    # Find missing files
    missing_files = find_missing_ocr_files(source_dirs, ocr_dir)
    
    if not missing_files:
        print("✅ All files have been OCR'd!")
        return
    
    print(f"❌ Found {len(missing_files)} files missing OCR:")
    for i, file_path in enumerate(missing_files[:10]):  # Show first 10
        print(f"  {i+1}. {file_path}")
    if len(missing_files) > 10:
        print(f"  ... and {len(missing_files) - 10} more")
    
    # Ask user if they want to process
    print()
    response = input(f"Process {len(missing_files)} missing files? [y/N]: ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    # Process missing files
    print(f"\n=== Processing {len(missing_files)} Missing Files ===")
    
    # Initialize OCR processor
    ocr_processor = OCRProcessor(device="mps", lite=False)
    ocr_output_dir = Path(ocr_dir)
    ocr_output_dir.mkdir(parents=True, exist_ok=True)
    
    processed = 0
    failed = 0
    
    for i, file_path in enumerate(missing_files):
        try:
            print(f"\n[{i+1}/{len(missing_files)}] Processing: {file_path.name}")
            
            if file_path.suffix.lower() == '.pdf':
                ocr_result = ocr_processor.extract_text_from_pdf(file_path, ocr_output_dir)
            else:
                # Image file
                ocr_result = ocr_processor.extract_text_from_image(file_path, ocr_output_dir)
            
            print(f"✅ Success - Confidence: {ocr_result['confidence']:.2f}")
            processed += 1
            
        except Exception as e:
            print(f"❌ Failed: {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Processing complete!")
    print(f"✅ Processed: {processed}")
    print(f"❌ Failed: {failed}")
    
    if processed > 0:
        print(f"\nNow you can regenerate Excel files to include these newly OCR'd receipts.")

if __name__ == "__main__":
    main()