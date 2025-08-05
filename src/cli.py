"""Command-line interface for Japanese receipt OCR processing."""

import logging
import click
from pathlib import Path
from typing import List, Dict, Any
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import sys
from datetime import datetime
from collections import Counter

from .ocr import OCRProcessor
from .parse import JapaneseReceiptParser
from .classify import CategoryClassifier
from .review import ReviewQueue
from .export import ExcelExporter

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class FileAuditTracker:
    """Track what happens to every file during processing."""
    
    def __init__(self):
        self.files = {}  # filename -> status info
        
    def add_file(self, filepath: Path):
        """Register a file found in the input directory."""
        self.files[str(filepath)] = {
            'status': 'found',
            'ocr': None,
            'date': None,
            'amount': None,
            'category': None,
            'reason': None
        }
    
    def update_file(self, filepath: Path, **kwargs):
        """Update file status with processing results."""
        key = str(filepath)
        if key in self.files:
            self.files[key].update(kwargs)
    
    def get_summary(self) -> Dict[str, int]:
        """Get summary counts by status."""
        summary = Counter()
        for file_info in self.files.values():
            summary[file_info['status']] += 1
        return dict(summary)
    
    def get_missing_files(self) -> List[str]:
        """Get list of files that were not processed successfully."""
        missing = []
        for filepath, info in self.files.items():
            if info['status'] not in ['processed', 'review']:
                missing.append(f"{Path(filepath).name} - {info['status']}: {info.get('reason', 'unknown')}")
        return missing


def determine_month_year_from_transactions(transactions: List[Dict[str, Any]]) -> str:
    """
    Determine the most common month/year from transaction dates.
    
    Args:
        transactions: List of transaction dictionaries with date fields
        
    Returns:
        String in format "August 2024" or "Mixed Months" if no clear majority
    """
    if not transactions:
        return "Unknown Period"
    
    # Extract month/year from valid dates
    month_years = []
    for transaction in transactions:
        date_str = transaction.get('date')
        if date_str:
            try:
                # Parse ISO date format (YYYY-MM-DD)
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                month_year = date_obj.strftime('%B %Y')  # e.g., "August 2024"
                month_years.append(month_year)
            except ValueError:
                continue
    
    if not month_years:
        return "Unknown Period"
    
    # Find most common month/year
    month_year_counts = Counter(month_years)
    most_common = month_year_counts.most_common(1)[0]
    
    # If the most common month/year represents >50% of transactions, use it
    if most_common[1] / len(month_years) > 0.5:
        return most_common[0]
    else:
        return "Mixed Months"


class ReceiptProcessor:
    """Main processor for batch receipt OCR and extraction."""
    
    def __init__(self, 
                 device: str = "mps",
                 lite: bool = False,
                 rules_path: str = "rules/categories.yml",
                 max_workers: int = 4,
                 force_ocr: bool = False,
                 debug: bool = False):
        """
        Initialize the receipt processor.
        
        Args:
            device: OCR device ('mps', 'cuda', 'cpu')
            lite: Use lite models for speed
            rules_path: Path to category rules file
            max_workers: Number of parallel workers
            force_ocr: Force OCR even if embedded text exists
            debug: Enable debug output
        """
        self.device = device
        self.lite = lite
        self.max_workers = max_workers
        self.force_ocr = force_ocr
        self.debug = debug
        
        # Initialize components
        self.ocr_processor = OCRProcessor(device=device, lite=lite)
        self.parser = JapaneseReceiptParser()
        self.classifier = CategoryClassifier(Path(rules_path))
        self.review_queue = ReviewQueue()
        
        # Track processing stats
        self.stats = {
            'total_files': 0,
            'processed': 0,
            'failed': 0,
            'skipped_duplicates': 0,
            'review_items': 0
        }
        
        # Initialize file audit tracker
        self.audit = FileAuditTracker()
    
    def find_receipt_files(self, input_dir: Path) -> List[Path]:
        """Find all receipt files (PDF and image formats) in the input directory."""
        receipt_files = []
        
        # Support for PDFs and image formats
        patterns = ['*.pdf', '*.PDF', '*.png', '*.PNG', '*.jpg', '*.JPG', '*.jpeg', '*.JPEG']
        
        # Log directory structure for debugging
        logger.info(f"Searching for receipt files in: {input_dir}")
        if input_dir.exists():
            subdirs = [d for d in input_dir.iterdir() if d.is_dir()]
            if subdirs:
                logger.info(f"Found subdirectories: {[d.name for d in subdirs]}")
        
        for pattern in patterns:
            # Search current directory
            current_files = list(input_dir.glob(pattern))
            receipt_files.extend(current_files)
            
            # Search subdirectories recursively
            subdir_files = list(input_dir.glob(f'**/{pattern}'))
            receipt_files.extend(subdir_files)
            
            # Log findings for debugging
            if current_files or subdir_files:
                logger.info(f"Pattern {pattern}: {len(current_files)} in root, {len(subdir_files)} in subdirs")
        
        # Remove duplicates and sort
        receipt_files = sorted(list(set(receipt_files)))
        logger.info(f"Found {len(receipt_files)} total receipt files (PDF/PNG/JPG) in {input_dir}")
        
        # Log each file found for complete audit trail
        for receipt_file in receipt_files:
            logger.info(f"  Found: {receipt_file.relative_to(input_dir)}")
        
        # Register all files with audit tracker
        for receipt_file in receipt_files:
            self.audit.add_file(receipt_file)
        
        return receipt_files
    
    def process_single_file(self, 
                          receipt_path: Path, 
                          output_dir: Path) -> Dict[str, Any]:
        """
        Process a single receipt file (PDF or image).
        
        Args:
            receipt_path: Path to receipt file (PDF/PNG/JPG)
            output_dir: Output directory for OCR JSON
            
        Returns:
            Dictionary with extraction results
        """
        try:
            logger.debug(f"Processing {receipt_path.name}")
            
            # Determine if this is a PDF or image file
            is_pdf = receipt_path.suffix.lower() == '.pdf'
            
            # Check for embedded text first (only for PDFs, unless force_ocr is enabled)
            if is_pdf and not self.force_ocr and self.ocr_processor.has_embedded_text(receipt_path):
                text = self.ocr_processor.extract_embedded_text(receipt_path)
                ocr_confidence = 0.95  # High confidence for embedded text
                if self.debug:
                    logger.debug(f"Using embedded text for {receipt_path.name}")
            else:
                # Use OCR (for PDFs without embedded text or for image files)
                if self.debug:
                    logger.debug(f"Using OCR for {receipt_path.name} (force_ocr={self.force_ocr}, is_pdf={is_pdf})")
                
                if is_pdf:
                    ocr_result = self.ocr_processor.extract_text_from_pdf(receipt_path, output_dir)
                else:
                    # For image files, use direct OCR
                    ocr_result = self.ocr_processor.extract_text_from_image(receipt_path, output_dir)
                text = ocr_result['full_text']
                ocr_confidence = ocr_result['confidence']
            
            # Update audit: OCR successful
            self.audit.update_file(receipt_path, ocr='success', status='ocr_complete')
            
            # Extract structured data
            date = self.parser.parse_date(text)
            amount = self.parser.parse_amount(text)
            vendor = self.parser.parse_vendor(text)
            
            # Classify category first
            category, category_confidence = self.classifier.classify(vendor, "", text)
            
            # Update audit with parsed data
            self.audit.update_file(receipt_path, 
                                 date=date, 
                                 amount=amount, 
                                 category=category)
            
            # Generate description using category information
            description = self.parser.extract_description_context(text, vendor, amount, category)
            
            # Check if needs review
            self.review_queue.add_from_extraction(
                file_path=str(receipt_path),
                date=date,
                amount=amount,
                category=category,
                category_confidence=category_confidence,
                ocr_confidence=ocr_confidence,
                raw_text=text
            )
            
            result = {
                'file_path': str(receipt_path),
                'date': date,
                'amount': amount,
                'category': category,
                'description': description,
                'vendor': vendor,
                'ocr_confidence': ocr_confidence,
                'category_confidence': category_confidence,
                'needs_review': len(self.review_queue.items) > self.stats['review_items']
            }
            
            # Update audit with final status
            if result['needs_review']:
                self.audit.update_file(receipt_path, status='review')
            else:
                self.audit.update_file(receipt_path, status='processed')
            
            self.stats['processed'] += 1
            return result
            
        except Exception as e:
            logger.error(f"Failed to process {receipt_path}: {e}")
            self.stats['failed'] += 1
            
            # Update audit with failure
            self.audit.update_file(receipt_path, 
                                 status='failed', 
                                 reason=str(e))
            
            # Add to review queue as failed item
            self.review_queue.add_item(
                file_path=str(receipt_path),
                reason=f"Processing failed: {str(e)}",
                raw_snippet=f"Error: {str(e)}"
            )
            
            return {
                'file_path': str(receipt_path),
                'date': None,
                'amount': None,
                'category': 'Other',
                'description': 'Processing failed',
                'vendor': None,
                'ocr_confidence': 0.0,
                'category_confidence': 0.0,
                'needs_review': True,
                'error': str(e)
            }
    
    def process_batch(self, 
                     input_dir: Path, 
                     output_dir: Path) -> List[Dict[str, Any]]:
        """
        Process all PDF files in the input directory.
        
        Args:
            input_dir: Directory containing PDF files
            output_dir: Output directory for results
            
        Returns:
            List of extraction results
        """
        # Find all PDF files
        receipt_files = self.find_receipt_files(input_dir)
        self.stats['total_files'] = len(receipt_files)
        
        if not receipt_files:
            logger.warning("No receipt files found!")
            return []
        
        # Create output directory
        ocr_output_dir = output_dir / 'ocr_json'
        ocr_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Process files with progress bar
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all jobs
            future_to_file = {
                executor.submit(self.process_single_file, receipt_file, ocr_output_dir): receipt_file
                for receipt_file in receipt_files
            }
            
            # Process results with progress bar
            with tqdm(total=len(receipt_files), desc="Processing receipts") as pbar:
                for future in as_completed(future_to_file):
                    receipt_file = future_to_file[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Exception processing {receipt_file}: {e}")
                        self.stats['failed'] += 1
                    
                    pbar.update(1)
                    pbar.set_postfix({
                        'processed': self.stats['processed'],
                        'failed': self.stats['failed']
                    })
        
        self.stats['review_items'] = len(self.review_queue.items)
        
        # Validate that all found files were processed
        processed_files = len(results)
        if processed_files != len(receipt_files):
            missing_count = len(receipt_files) - processed_files
            logger.warning(f"⚠️  File processing mismatch! Found {len(receipt_files)} files but only processed {processed_files}")
            logger.warning(f"   {missing_count} files may have been skipped or failed processing")
            
            # Log which files might be missing from results
            result_paths = {r.get('file_path', '') for r in results if r}
            for receipt_file in receipt_files:
                if str(receipt_file) not in result_paths and receipt_file.name not in {Path(p).name for p in result_paths}:
                    logger.warning(f"   Potentially missed: {receipt_file}")
        
        logger.info(f"Batch processing complete. Processed: {self.stats['processed']}, "
                   f"Failed: {self.stats['failed']}, Review items: {self.stats['review_items']}")
        
        return results


@click.group()
def cli():
    """Japanese Receipt OCR - Process receipts and extract transaction data."""
    pass


@cli.command()
@click.option('--in', 'input_dir', required=True, type=click.Path(exists=True, path_type=Path),
              help='Input directory containing PDF receipts')
@click.option('--out', 'output_dir', required=True, type=click.Path(path_type=Path),
              help='Output directory for results')
@click.option('--device', default='mps', type=click.Choice(['mps', 'cuda', 'cpu']),
              help='Device for OCR processing')
@click.option('--lite', is_flag=True, help='Use lite models for faster processing')
@click.option('--rules', default='rules/categories.yml', type=click.Path(path_type=Path),
              help='Path to category rules file')
@click.option('--max-workers', default=4, type=int,
              help='Maximum number of parallel workers')
@click.option('--summary', is_flag=True, help='Include summary sheet in Excel output')
@click.option('--combine-pdf', is_flag=True, help='Combine multi-page PDFs before processing')
@click.option('--encoding', default='utf-8-sig', help='Text encoding for output')
@click.option('--force-ocr', is_flag=True, help='Force OCR even if embedded text exists')
@click.option('--debug', is_flag=True, help='Enable debug output')
def run(input_dir: Path, 
        output_dir: Path, 
        device: str,
        lite: bool,
        rules: Path,
        max_workers: int,
        summary: bool,
        combine_pdf: bool,
        encoding: str,
        force_ocr: bool,
        debug: bool):
    """
    Process a folder of PDF receipts and generate Excel output.
    
    Example:
        receipts run --in ./drive/receipts --out ./out --device mps --summary
    """
    try:
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logs directory
        Path('logs').mkdir(exist_ok=True)
        
        logger.info(f"Starting receipt processing...")
        logger.info(f"Input directory: {input_dir}")
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"Device: {device}, Lite mode: {lite}")
        logger.info(f"Max workers: {max_workers}")
        
        # Set debug logging if requested
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
            # Also enable debug for parse module to show amount selection details
            logging.getLogger('parse').setLevel(logging.DEBUG)
            logging.getLogger('classify').setLevel(logging.DEBUG)
            click.echo("🔍 Debug mode enabled - detailed parsing logs will be shown")
        
        # Initialize processor
        processor = ReceiptProcessor(
            device=device,
            lite=lite,
            rules_path=str(rules),
            max_workers=max_workers,
            force_ocr=force_ocr,
            debug=debug
        )
        
        # Process all files
        results = processor.process_batch(input_dir, output_dir)
        
        if not results:
            logger.error("No files were processed successfully!")
            return
        
        # Filter successful extractions for Excel export
        transactions = []
        for result in results:
            if result.get('date') and result.get('amount'):
                transaction = ExcelExporter.create_transaction_dict(
                    date=result['date'],
                    amount=result['amount'],
                    category=result['category'],
                    description=result['description'],
                    file_path=result['file_path']
                )
                transactions.append(transaction)
        
        # Determine month/year for filename
        month_year = determine_month_year_from_transactions(transactions)
        
        # Create filename with month/year
        if month_year in ["Unknown Period", "Mixed Months"]:
            filename = f"transactions_{month_year.replace(' ', '_')}.xlsx"
        else:
            # Convert "August 2024" to "transactions_August_2024.xlsx"
            filename = f"transactions_{month_year.replace(' ', '_')}.xlsx"
        
        # Export to Excel
        excel_path = output_dir / filename
        exporter = ExcelExporter(excel_path)
        exporter.export_transactions(
            transactions=transactions,
            review_items=processor.review_queue.items,
            include_summary=summary
        )
        
        # Print summary
        click.echo("\\n" + "="*50)
        click.echo("PROCESSING SUMMARY")
        click.echo("="*50)
        click.echo(f"Total files found: {processor.stats['total_files']}")
        click.echo(f"Successfully processed: {processor.stats['processed']}")
        click.echo(f"Failed: {processor.stats['failed']}")
        click.echo(f"Exported transactions: {len(transactions)}")
        click.echo(f"Items needing review: {len(processor.review_queue.items)}")
        click.echo(f"Period detected: {month_year}")
        click.echo(f"\\nOutput files:")
        click.echo(f"  - Excel: {excel_path}")
        click.echo(f"  - OCR JSON: {output_dir / 'ocr_json'}")
        click.echo(f"  - Logs: logs/run.log")
        
        if processor.review_queue.items:
            click.echo(f"\\n⚠️  {len(processor.review_queue.items)} items need manual review!")
            click.echo("Check the 'Review' sheet in the Excel file.")
        
        success_rate = (processor.stats['processed'] / processor.stats['total_files']) * 100 if processor.stats['total_files'] > 0 else 0
        click.echo(f"\\nSuccess rate: {success_rate:.1f}%")
        
        # Display audit report
        click.echo("\\n" + "="*50)
        click.echo("FILE PROCESSING AUDIT")
        click.echo("="*50)
        
        audit_summary = processor.audit.get_summary()
        for status, count in sorted(audit_summary.items()):
            click.echo(f"{status}: {count} files")
        
        # Show missing/failed files if any
        missing_files = processor.audit.get_missing_files()
        if missing_files:
            click.echo(f"\\n❌ FILES NOT PROCESSED ({len(missing_files)}):")
            for missing in missing_files[:10]:  # Show first 10
                click.echo(f"  - {missing}")
            if len(missing_files) > 10:
                click.echo(f"  ... and {len(missing_files) - 10} more")
        
        # Save detailed audit report
        audit_file = output_dir / f'audit_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        with open(audit_file, 'w', encoding='utf-8') as f:
            f.write("=== RECEIPT PROCESSING AUDIT REPORT ===\\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n")
            f.write(f"Input directory: {input_dir}\\n\\n")
            
            f.write("=== SUMMARY ===\\n")
            for status, count in sorted(audit_summary.items()):
                f.write(f"{status}: {count} files\\n")
            
            f.write("\\n=== DETAILED FILE STATUS ===\\n")
            for filepath, info in sorted(processor.audit.files.items()):
                f.write(f"\\nFile: {Path(filepath).name}\\n")
                f.write(f"  Status: {info['status']}\\n")
                if info['date']:
                    f.write(f"  Date: {info['date']}\\n")
                if info['amount']:
                    f.write(f"  Amount: ¥{info['amount']}\\n")
                if info['category']:
                    f.write(f"  Category: {info['category']}\\n")
                if info['reason']:
                    f.write(f"  Reason: {info['reason']}\\n")
        
        click.echo(f"\\n📋 Detailed audit report saved: {audit_file}")
        
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()