"""
Ingredient Parser Service for normalizing recipe text into ingredient lines.
"""
import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class IngredientParser:
    """
    Service for parsing and normalizing recipe text into ingredient lines.
    """
    
    # Common measurement units and abbreviations
    MEASUREMENT_UNITS = [
        'cup', 'cups', 'tbsp', 'tablespoon', 'tablespoons', 'tsp', 'teaspoon', 'teaspoons',
        'oz', 'ounce', 'ounces', 'lb', 'pound', 'pounds', 'g', 'gram', 'grams',
        'kg', 'kilogram', 'kilograms', 'ml', 'milliliter', 'milliliters',
        'l', 'liter', 'liters', 'fl oz', 'fluid ounce', 'fluid ounces',
        'piece', 'pieces', 'slice', 'slices', 'clove', 'cloves',
        'can', 'cans', 'package', 'packages', 'bunch', 'bunches',
        'head', 'heads', 'stalk', 'stalks', 'sprig', 'sprigs'
    ]
    
    # Common cooking terms that might appear in ingredient lines
    COOKING_TERMS = [
        'chopped', 'diced', 'minced', 'sliced', 'grated', 'shredded',
        'crushed', 'mashed', 'peeled', 'seeded', 'trimmed', 'cut',
        'fresh', 'dried', 'frozen', 'canned', 'organic', 'raw', 'cooked'
    ]
    
    def __init__(self):
        """Initialize the ingredient parser."""
    
    def normalize_text(self, raw_text: str) -> List[str]:
        """
        Normalize raw recipe text into a list of ingredient lines.
        
        Args:
            raw_text: Raw text extracted from OCR
            
        Returns:
            List[str]: List of normalized ingredient lines
        """
        if not raw_text or not raw_text.strip():
            return []
        
        # Split text into lines
        lines = raw_text.split('\n')
        
        # Process each line
        ingredient_lines = []
        for line in lines:
            normalized_line = self._normalize_line(line)
            if normalized_line:
                ingredient_lines.append(normalized_line)
        
        # If we got very few lines, try splitting by common delimiters
        if len(ingredient_lines) < 2:
            ingredient_lines = self._split_by_delimiters(raw_text)
        
        logger.info(f"Normalized {len(ingredient_lines)} ingredient lines from text")
        return ingredient_lines
    
    def _normalize_line(self, line: str) -> Optional[str]:
        """
        Normalize a single line of text into an ingredient line.
        
        Args:
            line: Single line of text
            
        Returns:
            Optional[str]: Normalized ingredient line or None if invalid
        """
        # Remove extra whitespace
        line = ' '.join(line.split())
        
        # Skip empty lines
        if not line or len(line.strip()) < 3:
            return None
        
        # Skip lines that are clearly not ingredients (too short, all numbers, etc.)
        if len(line) < 5:
            return None
        
        # Remove common prefixes/suffixes that aren't part of ingredients
        line = re.sub(r'^[\d\.\-\s]+', '', line)  # Remove leading numbers/dashes
        line = re.sub(r'[•\-\*]\s*', '', line)  # Remove bullet points
        
        # Clean up the line
        line = line.strip()
        
        # Skip if line is too short after cleaning
        if len(line) < 3:
            return None
        
        return line
    
    def _split_by_delimiters(self, text: str) -> List[str]:
        """
        Split text by common delimiters if line splitting didn't work well.
        
        Args:
            text: Raw text to split
            
        Returns:
            List[str]: List of ingredient lines
        """
        # Common delimiters in recipe text
        delimiters = [',', ';', '|', '\n', '•', '-']
        
        # Try splitting by delimiters
        for delimiter in delimiters:
            if delimiter in text:
                parts = text.split(delimiter)
                normalized = [self._normalize_line(part) for part in parts]
                normalized = [n for n in normalized if n]  # Remove None values
                if len(normalized) > 1:
                    return normalized
        
        # If no delimiters found, return the whole text as one ingredient
        normalized = self._normalize_line(text)
        return [normalized] if normalized else []
    
    def format_for_spoonacular(self, ingredient_lines: List[str]) -> str:
        """
        Format ingredient lines for Spoonacular API.
        Spoonacular expects ingredients in a specific format.
        
        Args:
            ingredient_lines: List of ingredient lines
            
        Returns:
            str: Formatted string for Spoonacular API
        """
        # Spoonacular recipe analysis API expects ingredients as a newline-separated string
        return '\n'.join(ingredient_lines)

