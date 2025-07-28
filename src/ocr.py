"""YomiToku OCR wrapper for Japanese text extraction."""

import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import hashlib
import asyncio
import cv2
import numpy as np

try:
    from yomitoku import DocumentAnalyzer
    from pdf2image import convert_from_path
except ImportError:
    print("Required packages not installed. Run: pip install yomitoku pdf2image")
    raise

logger = logging.getLogger(__name__)


class OCRProcessor:
    """Wrapper for YomiToku DocumentAnalyzer with Japanese optimization."""
    
    def __init__(self, device: str = "mps", lite: bool = False):
        """
        Initialize OCR processor.
        
        Args:
            device: Device to use ('mps', 'cuda', 'cpu')
            lite: Use lite models for faster processing
        """
        self.device = device
        self.lite = lite
        self.analyzer = None
        self._init_analyzer()
        
    def _init_analyzer(self):
        """Initialize YomiToku DocumentAnalyzer."""
        try:
            # YomiToku will download models on first run
            logger.info(f"Initializing YomiToku with device: {self.device}")
            # Initialize with proper config dict
            configs = {
                'device': self.device,
                'det_model_dir': None,  # Use default
                'rec_model_dir': None,  # Use default
            }
            self.analyzer = DocumentAnalyzer(configs=configs)
            logger.info("YomiToku initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize YomiToku: {e}")
            raise
    
    def get_file_hash(self, file_path: Path) -> str:
        """Generate hash for file to detect duplicates."""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def extract_text_from_pdf(self, pdf_path: Path, output_dir: Path) -> Dict[str, Any]:
        """
        Extract text from PDF using YomiToku.
        
        Args:
            pdf_path: Path to PDF file
            output_dir: Directory to save OCR JSON results
            
        Returns:
            Dictionary with OCR results and metadata
        """
        try:
            file_hash = self.get_file_hash(pdf_path)
            
            # Check if already processed
            json_path = output_dir / f"{pdf_path.stem}_{file_hash}.json"
            if json_path.exists():
                logger.info(f"Loading cached OCR result for {pdf_path.name}")
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            logger.info(f"Processing {pdf_path.name} with YomiToku...")
            
            # Convert PDF to images
            images = convert_from_path(str(pdf_path), dpi=200)
            logger.info(f"Converted PDF to {len(images)} image(s)")
            
            # Process each page with YomiToku
            ocr_result = {
                'file_path': str(pdf_path),
                'file_hash': file_hash,
                'pages': [],
                'full_text': '',
                'confidence': 0.0
            }
            
            full_text_parts = []
            total_confidence = 0
            block_count = 0
            
            async def process_page(page_img, page_idx):
                # Convert PIL image to numpy array for YomiToku
                img_array = np.array(page_img)
                if img_array.shape[2] == 4:  # RGBA
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
                elif img_array.shape[2] == 3:  # RGB
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                
                # Workaround for YomiToku bug: set img attribute
                self.analyzer.img = img_array
                
                # Process with YomiToku
                result = await self.analyzer.run(img_array)
                return result, page_idx
            
            async def process_all_pages():
                tasks = [process_page(img, idx) for idx, img in enumerate(images)]
                return await asyncio.gather(*tasks)
            
            # Run async processing
            page_results = asyncio.run(process_all_pages())
            
            for result, page_idx in page_results:
                page_data = {
                    'page_number': page_idx + 1,
                    'blocks': [],
                    'text': ''
                }
                
                page_text_parts = []
                
                # Extract text from YomiToku result (tuple format)
                if isinstance(result, tuple) and len(result) > 0:
                    document_schema = result[0]
                    
                    # Use words directly since they contain the actual text
                    if hasattr(document_schema, 'words') and document_schema.words:
                        word_texts = []
                        word_confidences = []
                        
                        for word in document_schema.words:
                            if hasattr(word, 'content') and word.content.strip():
                                word_texts.append(word.content)
                                word_confidences.append(getattr(word, 'rec_score', 0.8))
                        
                        if word_texts:
                            # Create one block with all text
                            combined_text = '\n'.join(word_texts)  # Use newlines to separate words for better parsing
                            avg_confidence = sum(word_confidences) / len(word_confidences) if word_confidences else 0.8
                            
                            block_data = {
                                'text': combined_text,
                                'confidence': avg_confidence
                            }
                            page_data['blocks'].append(block_data)
                            page_text_parts.append(combined_text)
                            
                            total_confidence += avg_confidence
                            block_count += 1
                
                page_data['text'] = '\\n'.join(page_text_parts)
                ocr_result['pages'].append(page_data)
                full_text_parts.append(page_data['text'])
            
            ocr_result['full_text'] = '\\n'.join(full_text_parts)
            ocr_result['confidence'] = total_confidence / block_count if block_count > 0 else 0.7
            
            # Save OCR result to JSON
            output_dir.mkdir(parents=True, exist_ok=True)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(ocr_result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"OCR completed for {pdf_path.name} with confidence: {ocr_result['confidence']:.2f}")
            return ocr_result
            
        except Exception as e:
            logger.error(f"OCR failed for {pdf_path}: {e}")
            raise
    
    def has_embedded_text(self, pdf_path: Path) -> bool:
        """
        Check if PDF has GOOD QUALITY embedded text (to skip OCR if possible).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            True if PDF has substantial, good quality embedded text
        """
        try:
            from pdfminer.high_level import extract_text
            text = extract_text(str(pdf_path))
            
            # More strict criteria for embedded text quality
            if len(text.strip()) > 100:
                # Check for signs of good quality text
                lines = text.split('\n')
                readable_lines = 0
                total_chars = 0
                
                for line in lines:
                    line = line.strip()
                    if len(line) > 3:
                        total_chars += len(line)
                        # Count lines that look readable (not too many weird chars)
                        weird_chars = sum(1 for c in line if ord(c) < 32 or ord(c) > 126)
                        if weird_chars / len(line) < 0.3:  # Less than 30% weird characters
                            readable_lines += 1
                
                # Only use embedded text if it looks high quality
                quality_good = readable_lines >= 3 and total_chars > 50
                
                if quality_good:
                    logger.info(f"{pdf_path.name} has good embedded text, extracting directly")
                    return True
                else:
                    logger.info(f"{pdf_path.name} has poor embedded text, will use OCR instead")
                    return False
            
            return False
            
        except Exception as e:
            logger.warning(f"Could not check embedded text for {pdf_path}: {e}")
            return False
    
    def extract_embedded_text(self, pdf_path: Path) -> str:
        """Extract embedded text from PDF."""
        try:
            from pdfminer.high_level import extract_text
            return extract_text(str(pdf_path))
        except Exception as e:
            logger.error(f"Failed to extract embedded text from {pdf_path}: {e}")
            return ""