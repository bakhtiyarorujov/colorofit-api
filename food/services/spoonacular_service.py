"""
Spoonacular Service for nutrition analysis using Spoonacular API.
"""
import logging
import requests
from typing import Dict, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class SpoonacularService:
    """
    Service for interacting with Spoonacular API for nutrition analysis.
    """
    
    BASE_URL = "https://api.spoonacular.com/recipes"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Spoonacular service.
        
        Args:
            api_key: Spoonacular API key. If not provided, uses SPOONACULAR_API_KEY from settings.
        """
        self.api_key = api_key or getattr(settings, 'SPOONACULAR_API_KEY', None)
        if not self.api_key:
            raise ValueError("SPOONACULAR_API_KEY must be set in settings or provided to constructor")
    
    def analyze_recipe_nutrition(self, ingredients: str, servings: int = 1) -> Dict:
        """
        Analyze recipe nutrition using Spoonacular's recipe analysis endpoint.
        
        Args:
            ingredients: Newline-separated list of ingredients
            servings: Number of servings (default: 1)
            
        Returns:
            Dict: Nutrition data including calories and macronutrients
            
        Raises:
            requests.RequestException: If API request fails
            ValueError: If API response is invalid
        """
        if not ingredients or not ingredients.strip():
            raise ValueError("Ingredients cannot be empty")
        
        url = f"{self.BASE_URL}/analyze"
        
        params = {
            'apiKey': self.api_key,
        }
        
        data = {
            'ingredientList': ingredients,
            'servings': servings,
        }
        
        try:
            response = requests.post(
                url,
                params=params,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract nutrition information
            nutrition_data = self._extract_nutrition_data(result)
            
            logger.info(f"Successfully analyzed recipe nutrition: {nutrition_data.get('calories', 0)} calories")
            return nutrition_data
            
        except requests.exceptions.Timeout:
            logger.error("Spoonacular API request timed out")
            raise Exception("Request to nutrition service timed out. Please try again.")
        except requests.exceptions.HTTPError as e:
            logger.error(f"Spoonacular API HTTP error: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 401:
                raise Exception("Invalid API key for nutrition service")
            elif e.response.status_code == 402:
                raise Exception("API quota exceeded for nutrition service")
            else:
                raise Exception(f"Nutrition service error: {e.response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Spoonacular API request failed: {e}")
            raise Exception(f"Failed to connect to nutrition service: {str(e)}")
        except KeyError as e:
            logger.error(f"Unexpected API response format: {e}")
            raise ValueError(f"Invalid response from nutrition service: missing {e}")
        except Exception as e:
            logger.error(f"Unexpected error in nutrition analysis: {e}")
            raise
    
    def _extract_nutrition_data(self, api_response: Dict) -> Dict:
        """
        Extract and normalize nutrition data from Spoonacular API response.
        Includes both macronutrients and micronutrients (vitamins and minerals).
        
        Args:
            api_response: Raw API response from Spoonacular
            
        Returns:
            Dict: Normalized nutrition data with macros and micros
        """
        try:
            # Spoonacular analyze endpoint returns nutrition in 'nutrition' key
            nutrition = api_response.get('nutrition', {})
            nutrients = nutrition.get('nutrients', [])
            
            # Initialize macronutrient values
            calories = 0.0
            protein = 0.0
            carbohydrates = 0.0
            fats = 0.0
            fiber = 0.0
            sugar = 0.0
            saturated_fat = 0.0
            trans_fat = 0.0
            cholesterol = 0.0
            sodium = 0.0
            
            # Initialize micronutrient values (vitamins and minerals)
            vitamins = {
                'vitamin_a': 0.0,
                'vitamin_c': 0.0,
                'vitamin_d': 0.0,
                'vitamin_e': 0.0,
                'vitamin_k': 0.0,
                'thiamin': 0.0,  # B1
                'riboflavin': 0.0,  # B2
                'niacin': 0.0,  # B3
                'vitamin_b6': 0.0,
                'folate': 0.0,  # B9
                'vitamin_b12': 0.0,
            }
            
            minerals = {
                'calcium': 0.0,
                'iron': 0.0,
                'magnesium': 0.0,
                'phosphorus': 0.0,
                'potassium': 0.0,
                'zinc': 0.0,
                'copper': 0.0,
                'manganese': 0.0,
                'selenium': 0.0,
            }
            
            # Extract values from nutrients array
            for nutrient in nutrients:
                name = nutrient.get('name', '').lower()
                amount = float(nutrient.get('amount', 0))
                
                # Macronutrients
                if 'calorie' in name or 'energy' in name:
                    calories = amount
                elif 'protein' in name:
                    protein = amount
                elif 'carbohydrate' in name or 'carb' in name:
                    if 'net' not in name and 'fiber' not in name:
                        carbohydrates = amount
                elif 'fat' in name:
                    if 'saturated' in name:
                        saturated_fat = amount
                    elif 'trans' in name:
                        trans_fat = amount
                    elif 'monounsaturated' not in name and 'polyunsaturated' not in name:
                        fats = amount
                elif 'fiber' in name or 'fibre' in name:
                    fiber = amount
                elif 'sugar' in name:
                    sugar = amount
                elif 'cholesterol' in name:
                    cholesterol = amount
                elif 'sodium' in name:
                    sodium = amount
                
                # Vitamins
                elif 'vitamin a' in name or 'vitamin a' in name:
                    vitamins['vitamin_a'] = amount
                elif 'vitamin c' in name:
                    vitamins['vitamin_c'] = amount
                elif 'vitamin d' in name:
                    vitamins['vitamin_d'] = amount
                elif 'vitamin e' in name:
                    vitamins['vitamin_e'] = amount
                elif 'vitamin k' in name:
                    vitamins['vitamin_k'] = amount
                elif 'thiamin' in name or 'vitamin b1' in name:
                    vitamins['thiamin'] = amount
                elif 'riboflavin' in name or 'vitamin b2' in name:
                    vitamins['riboflavin'] = amount
                elif 'niacin' in name or 'vitamin b3' in name:
                    vitamins['niacin'] = amount
                elif 'vitamin b6' in name:
                    vitamins['vitamin_b6'] = amount
                elif 'folate' in name or 'folic acid' in name or 'vitamin b9' in name:
                    vitamins['folate'] = amount
                elif 'vitamin b12' in name or 'cobalamin' in name:
                    vitamins['vitamin_b12'] = amount
                
                # Minerals
                elif 'calcium' in name:
                    minerals['calcium'] = amount
                elif 'iron' in name:
                    minerals['iron'] = amount
                elif 'magnesium' in name:
                    minerals['magnesium'] = amount
                elif 'phosphorus' in name:
                    minerals['phosphorus'] = amount
                elif 'potassium' in name:
                    minerals['potassium'] = amount
                elif 'zinc' in name:
                    minerals['zinc'] = amount
                elif 'copper' in name:
                    minerals['copper'] = amount
                elif 'manganese' in name:
                    minerals['manganese'] = amount
                elif 'selenium' in name:
                    minerals['selenium'] = amount
            
            # Get recipe title if available
            recipe_title = api_response.get('title', 'Custom Recipe')
            
            # Round all values to 2 decimal places
            def round_dict_values(d):
                return {k: round(v, 2) for k, v in d.items()}
            
            return {
                'food_name': recipe_title,
                # Macronutrients
                'calories': round(calories, 2),
                'protein': round(protein, 2),
                'carbohydrates': round(carbohydrates, 2),
                'fats': round(fats, 2),
                'fiber': round(fiber, 2),
                'sugar': round(sugar, 2),
                'saturated_fat': round(saturated_fat, 2),
                'trans_fat': round(trans_fat, 2),
                'cholesterol': round(cholesterol, 2),
                'sodium': round(sodium, 2),
                # Micronutrients
                'vitamins': round_dict_values(vitamins),
                'minerals': round_dict_values(minerals),
                # Other
                'servings': api_response.get('servings', 1),
            }
            
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error extracting nutrition data: {e}")
            raise ValueError(f"Failed to parse nutrition data from API response: {str(e)}")

