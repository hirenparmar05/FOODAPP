from flask import Blueprint, render_template, request, jsonify
import pandas as pd
import random
import requests
import re
import os

views = Blueprint('views', __name__)

API_KEY = 'FtiBqTvtyNcF7FrO5c3oSg==aLg0Iw2qa5daSY7e'
API_URL = 'https://api.calorieninjas.com/v1/nutrition?query='

# Load the dataset
file_name = "food_data.csv"
df = pd.read_csv(file_name)
df['Ingredients'] = df['Ingredients'].fillna("No ingredients listed")
df['Instructions'] = df['Instructions'].fillna("No instructions available")

def get_calories_and_macros(ingredient):
    headers = {'X-Api-Key': API_KEY}
    response = requests.get(f"{API_URL}{ingredient}", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if 'items' in data and data['items']:
            item = data['items'][0]
            return {
                'calories': item.get('calories', 'Calories not found'),
                'protein': item.get('protein_g', 'Protein not found'),
                'total_fat': item.get('fat_total_g', 'Total fat not found'),
                'carbohydrates': item.get('carbohydrates_total_g', 'Carbohydrates not found'),
            }
    return None

@views.route('/')
def home():
    return render_template('home.html')

@views.route('/search-ingredients', methods=['GET', 'POST'])
def search_ingredients():
    if request.method == 'POST':
        ingredients = request.form.get('ingredients', '').strip()
        if not ingredients:
            return render_template('search_ingredients.html', results=[], 
                                message="Please enter ingredients")
        
        # Split ingredients and clean the input
        ingredients_list = [ing.strip().lower() for ing in ingredients.split(',') if ing.strip()]
        
        # Create initial mask
        mask = pd.Series([True] * len(df))
        
        # Filter for each ingredient
        for ingredient in ingredients_list:
            pattern = r'\b' + re.escape(ingredient) + r'\b'
            mask &= df['Ingredients'].str.lower().str.contains(pattern, regex=True, na=False)
        
        results = df[mask].copy()
        
        if len(results) == 0:
            return render_template('search_ingredients.html', results=[], 
                                message=f"No recipes found with all ingredients: {ingredients}")
        
        # Reset index for proper ID reference
        results = results.reset_index()
        
        return render_template('search_ingredients.html', 
                             results=results.to_dict(orient='records'),
                             message=f"Found {len(results)} recipes")
    
    return render_template('search_ingredients.html', results=[], 
                         message="Enter ingredients to search")

@views.route('/meal-tracker', methods=['GET'])
def meal_tracker():
    return render_template('meal_tracker.html')

@views.route('/api/track-ingredient', methods=['POST'])
def track_ingredient():
    data = request.json
    ingredient = data.get('ingredient', '')
    grams = float(data.get('grams', 100))
    
    macros = get_calories_and_macros(ingredient)
    if not macros:
        return jsonify({"error": f"No nutritional data found for {ingredient}"}), 404
    
    scaled_macros = {
        "ingredient": ingredient,
        "grams": grams,
        "calories": (grams / 100) * macros['calories'],
        "protein": (grams / 100) * macros['protein'],
        "total_fat": (grams / 100) * macros['total_fat'],
        "carbohydrates": (grams / 100) * macros['carbohydrates'],
    }
    return jsonify(scaled_macros)

@views.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            return render_template('search.html', results=[], message="Please enter a search term")
        
        # Split search terms and create a pattern that matches any of the words
        search_terms = title.split()
        pattern = '|'.join(map(re.escape, search_terms))
        
        try:
            # Search for partial matches in Title column
            mask = df['Title'].str.contains(pattern, case=False, na=False, regex=True)
            results = df[mask].copy()  # Create a copy to avoid SettingWithCopyWarning
            
            if len(results) == 0:
                return render_template('search.html', results=[], 
                                    message=f"No recipes found matching '{title}'")
            
            # Sort results by relevance (exact matches first)
            results['relevance'] = results['Title'].apply(
                lambda x: sum(term.lower() in x.lower() for term in search_terms)
            )
            results = results.sort_values('relevance', ascending=False)
            
            # Reset index for proper ID reference
            results = results.reset_index()
            
            return render_template('search.html', 
                                 results=results.to_dict(orient='records'),
                                 message=f"Found {len(results)} recipes")
            
        except Exception as e:
            print(f"Search error: {e}")  # For debugging
            return render_template('search.html', results=[], 
                                message="An error occurred while searching")
    
    return render_template('search.html', results=[], message="Enter a recipe name to search")

def get_image_path(recipe):
    try:
        # Get image name from the recipe dictionary and add .jpg extension
        image_name = f"{recipe['Image_Name']}.jpg"
        base_path = os.path.join('website', 'static', 'food_images')
        
        # Debug prints
        print(f"Looking for image: {image_name}")
        
        if os.path.exists(os.path.join(base_path, image_name)):
            print(f"Found image: {image_name}")
            return f"food_images/{image_name}"
        else:
            print(f"Image not found: {image_name}")
    except Exception as e:
        print(f"Error finding image: {e}")
    
    return "food_images/default.jpg"

@views.route('/recipe/<int:recipe_id>')
def recipe_details(recipe_id):
    try:
        recipe = df.iloc[recipe_id].to_dict()
        
        # Get image path using recipe's Image_Name
        image_path = get_image_path(recipe)
        print(f"Image path returned: {image_path}")
        
        recipe['image_path'] = image_path
        return render_template('recipe_details.html', recipe=recipe)
    except IndexError as e:
        print(f"Error: {e}")
        return render_template('404.html'), 404


@views.route('/random_recipe')
def random_recipe():
    recipe = df.sample().iloc[0].to_dict()
    # Add image path to the recipe dictionary
    recipe['image_path'] = get_image_path(recipe)
    return render_template('recipe_details.html', recipe=recipe)  # Use recipe_details.html instead of recipe.html

@views.route('/macros', methods=['POST'])
def macros():
    data = request.json
    ingredient = data.get('ingredient', '')
    grams = data.get('grams', 100)

    macros = get_calories_and_macros(ingredient)
    if not macros:
        return jsonify({"message": f"No nutritional data found for {ingredient}"}), 404

    scaled_macros = {
        "calories": (grams / 100) * macros['calories'],
        "protein": (grams / 100) * macros['protein'],
        "total_fat": (grams / 100) * macros['total_fat'],
        "carbohydrates": (grams / 100) * macros['carbohydrates'],
    }
    return jsonify(scaled_macros)
