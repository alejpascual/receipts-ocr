"""Command-line interface for Japanese receipt OCR processing."""

import logging
import click
from pathlib import Path
from typing import List, Dict, Any
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import sys

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
    
    def find_pdf_files(self, input_dir: Path) -> List[Path]:
        """Find all PDF files in the input directory."""
        pdf_files = []
        
        for pattern in ['*.pdf', '*.PDF']:
            pdf_files.extend(input_dir.glob(pattern))
            # Also search subdirectories
            pdf_files.extend(input_dir.glob(f'**/{pattern}'))
        
        # Remove duplicates and sort
        pdf_files = sorted(list(set(pdf_files)))
        logger.info(f"Found {len(pdf_files)} PDF files in {input_dir}")
        
        return pdf_files
    
    def process_single_file(self, 
                          pdf_path: Path, 
                          output_dir: Path) -> Dict[str, Any]:
        """
        Process a single PDF file.
        
        Args:
            pdf_path: Path to PDF file
            output_dir: Output directory for OCR JSON
            
        Returns:
            Dictionary with extraction results
        """
        try:
            logger.debug(f"Processing {pdf_path.name}")
            
            # Check for embedded text first (unless force_ocr is enabled)
            if not self.force_ocr and self.ocr_processor.has_embedded_text(pdf_path):
                text = self.ocr_processor.extract_embedded_text(pdf_path)
                ocr_confidence = 0.95  # High confidence for embedded text
                if self.debug:
                    logger.debug(f"Using embedded text for {pdf_path.name}")
            else:
                # Use OCR
                if self.debug:
                    logger.debug(f"Using OCR for {pdf_path.name} (force_ocr={self.force_ocr})")
                ocr_result = self.ocr_processor.extract_text_from_pdf(pdf_path, output_dir)
                text = ocr_result['full_text']
                ocr_confidence = ocr_result['confidence']
            
            # Extract structured data
            date = self.parser.parse_date(text)
            amount = self.parser.parse_amount(text)
            vendor = self.parser.parse_vendor(text)
            
            # Classify category first
            category, category_confidence = self.classifier.classify(vendor, "", text)
            
            # Generate description using category information
            description = self.parser.extract_description_context(text, vendor, amount, category)
            
            # Check if needs review
            self.review_queue.add_from_extraction(
                file_path=str(pdf_path),
                date=date,
                amount=amount,
                category=category,
                category_confidence=category_confidence,
                ocr_confidence=ocr_confidence,
                raw_text=text
            )
            
            result = {
                'file_path': str(pdf_path),
                'date': date,
                'amount': amount,
                'category': category,
                'description': description,
                'vendor': vendor,
                'ocr_confidence': ocr_confidence,
                'category_confidence': category_confidence,
                'needs_review': len(self.review_queue.items) > self.stats['review_items']
            }
            
            self.stats['processed'] += 1
            return result
            
        except Exception as e:
            logger.error(f"Failed to process {pdf_path}: {e}")
            self.stats['failed'] += 1
            
            # Add to review queue as failed item
            self.review_queue.add_item(
                file_path=str(pdf_path),
                reason=f"Processing failed: {str(e)}",
                raw_snippet=f"Error: {str(e)}"
            )
            
            return {
                'file_path': str(pdf_path),
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
        pdf_files = self.find_pdf_files(input_dir)
        self.stats['total_files'] = len(pdf_files)
        
        if not pdf_files:
            logger.warning("No PDF files found!")
            return []
        
        # Create output directory
        ocr_output_dir = output_dir / 'ocr_json'
        ocr_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Process files with progress bar
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all jobs
            future_to_file = {
                executor.submit(self.process_single_file, pdf_file, ocr_output_dir): pdf_file
                for pdf_file in pdf_files
            }
            
            # Process results with progress bar
            with tqdm(total=len(pdf_files), desc="Processing receipts") as pbar:
                for future in as_completed(future_to_file):
                    pdf_file = future_to_file[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Exception processing {pdf_file}: {e}")
                        self.stats['failed'] += 1
                    
                    pbar.update(1)
                    pbar.set_postfix({
                        'processed': self.stats['processed'],
                        'failed': self.stats['failed']
                    })
        
        self.stats['review_items'] = len(self.review_queue.items)
        
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
        
        # Export to Excel
        excel_path = output_dir / 'transactions.xlsx'
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
        click.echo(f"\\nOutput files:")
        click.echo(f"  - Excel: {excel_path}")
        click.echo(f"  - OCR JSON: {output_dir / 'ocr_json'}")
        click.echo(f"  - Logs: logs/run.log")
        
        if processor.review_queue.items:
            click.echo(f"\\n⚠️  {len(processor.review_queue.items)} items need manual review!")
            click.echo("Check the 'Review' sheet in the Excel file.")
        
        success_rate = (processor.stats['processed'] / processor.stats['total_files']) * 100 if processor.stats['total_files'] > 0 else 0
        click.echo(f"\\nSuccess rate: {success_rate:.1f}%")
        
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()