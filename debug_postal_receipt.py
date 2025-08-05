#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, '/Users/alejpascual/Coding/Current/receipts-ocr/src')

from parse import JapaneseReceiptParser
import json

def debug_postal_receipt():
    """Debug the postal receipt ¥230 vs ¥250 issue."""
    
    # Find the postal receipt from OCR data
    ocr_dir = "/Users/alejpascual/Downloads/receipts-output/ocr_json"
    
    # Look for postal-related files
    postal_files = []
    for filename in os.listdir(ocr_dir):
        if 'postal' in filename.lower() or 'post' in filename.lower() or '郵' in filename:
            postal_files.append(filename)
    
    if not postal_files:
        print("No postal receipts found. Looking for recent files with ¥250 or ¥230...")
        # Look for files that might contain these amounts
        for filename in os.listdir(ocr_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(ocr_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if '250' in content and '230' in content:
                            postal_files.append(filename)
                except:
                    continue
    
    print(f"Found potential postal receipt files: {postal_files}")
    
    parser = JapaneseReceiptParser()
    
    for filename in postal_files[:3]:  # Check first 3 files
        filepath = os.path.join(ocr_dir, filename)
        print(f"\n=== DEBUGGING {filename} ===")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract text
            text = ""
            if 'full_text' in data:
                text = data['full_text']
            elif 'pages' in data:
                # New format with pages
                for page in data['pages']:
                    if 'text' in page:
                        text += page['text'] + '\n'
            elif isinstance(data, list):
                # YomiToku format
                for page in data:
                    if 'text' in page:
                        text += page['text'] + '\n'
            elif 'text' in data:
                text = data['text']
            else:
                print(f"Unknown format: {type(data)}")
                continue
            
            print("OCR TEXT:")
            print("=" * 50)
            print(text)
            print("=" * 50)
            
            # Parse amount
            amount = parser.parse_amount(text)
            print(f"\nPARSED AMOUNT: ¥{amount}")
            
            # Let's also manually check what amounts are found
            lines = text.split('\n')
            print(f"\nMANUAL AMOUNT ANALYSIS:")
            for i, line in enumerate(lines):
                if '250' in line or '230' in line:
                    print(f"Line {i}: {line.strip()}")
                    
                    # Check if this line has avoid keywords
                    avoid_found = []
                    for avoid_kw in parser.avoid_keywords:
                        if avoid_kw in line:
                            avoid_found.append(avoid_kw)
                    
                    if avoid_found:
                        print(f"  AVOID KEYWORDS: {avoid_found}")
                    
                    # Check if this line has total keywords
                    total_found = []
                    for total_kw in parser.total_keywords:
                        if total_kw in line:
                            total_found.append(total_kw)
                    
                    if total_found:
                        print(f"  TOTAL KEYWORDS: {total_found}")
                    
                    print()
            
            # Check if this is the postal receipt we want (with ¥230 and ¥250)
            if '¥230' in text and '¥250' in text and 'お預り金額' in text and '合計' in text:
                print("*** This is the postal receipt we want to fix! ***")
                break  # Found the right file
            else:
                print("This is not the postal receipt with ¥230/¥250 issue, continuing...")
        
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            continue

if __name__ == "__main__":
    debug_postal_receipt()