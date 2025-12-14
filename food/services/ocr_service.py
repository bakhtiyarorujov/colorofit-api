"""
OCR Service for extracting text from recipe images.
Uses EasyOCR for better accuracy with food recipe text.
"""
import logging
from typing import Optional
from PIL import Image
import io
import easyocr

logger = logging.getLogger(__name__)


class OCRService:
    """
    Service for extracting text from images using OCR.
    """
    
    def __init__(self):
        """Initialize OCR reader. EasyOCR supports multiple languages."""
        try:
            # Initialize EasyOCR reader (English by default, can add more languages)
            self.reader = easyocr.Reader(['en'], gpu=False)
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            raise
    
    def extract_text(self, image_file) -> str:
        """
        Extract text from an image file.
        
        Args:
            image_file: Django UploadedFile or file-like object
            
        Returns:
            str: Extracted text from the image
            
        Raises:
            ValueError: If image cannot be processed
            Exception: If OCR processing fails
        """
        try:
            # Read image file
            image_bytes = image_file.read()
            image_file.seek(0)  # Reset file pointer for potential reuse
            
            # Open image with PIL
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if necessary (EasyOCR works best with RGB)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Perform OCR
            results = self.reader.readtext(image)
            
            # Extract text from results
            # EasyOCR returns list of (bbox, text, confidence)
            extracted_text = '\n'.join([result[1] for result in results])
            
            if not extracted_text.strip():
                raise ValueError("No text could be extracted from the image")
            
            logger.info(f"Successfully extracted {len(extracted_text)} characters from image")
            return extracted_text.strip()
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise Exception(f"Failed to extract text from image: {str(e)}")

