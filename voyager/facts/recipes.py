"""
Recipe and game mechanics fact source.

This module provides authoritative information about:
- Crafting recipes
- Tool requirements for harvesting
- Block harvest levels
- Item properties

This is the ONLY source of truth for game mechanics - the LLM must never
generate or hallucinate this information.
"""

class RecipeFacts:
    """
    Authoritative source for Minecraft recipes and mechanics.

    This class queries Mineflayer's built-in registry for accurate
    game information, preventing LLM hallucination of recipes.
    """

    def __init__(self, bot):
        """
        Initialize the recipe fact source.

        Args:
            bot: Mineflayer bot instance with access to registry
        """
        self.bot = bot

    def get_recipe(self, item_name):
        """
        Get the crafting recipe for an item from Mineflayer's registry.

        Args:
            item_name (str): Name of the item (e.g., "wooden_pickaxe")

        Returns:
            list or None: List of recipes if found, None otherwise.
            Each recipe is a dict with 'ingredients', 'result', etc.
        """
        try:
            # Get item from registry
            item = self.bot.registry.itemsByName.get(item_name)
            if not item:
                print(f"\033[31m[RecipeFacts] Item not found: {item_name}\033[0m")
                return None

            # Get recipes for this item
            recipes = self.bot.recipesFor(item.id, None, 1, None)

            if not recipes or len(recipes) == 0:
                print(f"\033[31m[RecipeFacts] No recipe found for: {item_name}\033[0m")
                return None

            print(f"\033[32m[RecipeFacts] Found {len(recipes)} recipe(s) for {item_name}\033[0m")
            return recipes

        except Exception as e:
            print(f"\033[31m[RecipeFacts] Error getting recipe for {item_name}: {e}\033[0m")
            return None

    def required_tool(self, block_name):
        """
        Get the tool requirements for harvesting a block.

        Args:
            block_name (str): Name of the block (e.g., "stone", "iron_ore")

        Returns:
            dict or None: Dictionary of valid tool IDs that can harvest this block,
            or None if block doesn't exist or has no tool requirements.
        """
        try:
            block = self.bot.registry.blocksByName.get(block_name)
            if not block:
                print(f"\033[31m[RecipeFacts] Block not found: {block_name}\033[0m")
                return None

            # Get harvest tools from block properties
            harvest_tools = getattr(block, 'harvestTools', None)

            if harvest_tools is None:
                # No specific tool required (e.g., dirt, sand)
                print(f"\033[32m[RecipeFacts] No tool required for {block_name}\033[0m")
                return {}

            print(f"\033[32m[RecipeFacts] Tools for {block_name}: {harvest_tools}\033[0m")
            return harvest_tools

        except Exception as e:
            print(f"\033[31m[RecipeFacts] Error getting tool requirements for {block_name}: {e}\033[0m")
            return None

    def can_harvest(self, block_name, tool_name):
        """
        Check if a specific tool can harvest a specific block.

        Args:
            block_name (str): Name of the block to mine
            tool_name (str): Name of the tool to use

        Returns:
            bool: True if the tool can harvest the block, False otherwise
        """
        try:
            block = self.bot.registry.blocksByName.get(block_name)
            if not block:
                return False

            # If no harvest tools specified, any tool (or hand) works
            harvest_tools = getattr(block, 'harvestTools', None)
            if harvest_tools is None or len(harvest_tools) == 0:
                return True

            # Check if tool is in the list of valid harvest tools
            tool = self.bot.registry.itemsByName.get(tool_name)
            if not tool:
                return False

            can_harvest = tool.id in harvest_tools
            print(f"\033[32m[RecipeFacts] Can {tool_name} harvest {block_name}? {can_harvest}\033[0m")
            return can_harvest

        except Exception as e:
            print(f"\033[31m[RecipeFacts] Error checking harvest capability: {e}\033[0m")
            return False

    def get_ingredient_names(self, recipe):
        """
        Extract ingredient names from a recipe object.

        Args:
            recipe: Recipe object from Mineflayer

        Returns:
            list: List of ingredient item names
        """
        try:
            if not recipe:
                return []

            ingredients = []

            # Handle different recipe formats
            if hasattr(recipe, 'delta'):
                # Shaped/shapeless recipe with delta
                for item in recipe.delta:
                    if item.count < 0:  # Negative count means consumed ingredient
                        item_id = abs(item.id)
                        item_name = self.bot.registry.items[item_id].name
                        ingredients.append(item_name)

            elif hasattr(recipe, 'ingredients'):
                # Direct ingredients list
                for ingredient in recipe.ingredients:
                    item_id = ingredient.id
                    item_name = self.bot.registry.items[item_id].name
                    ingredients.append(item_name)

            return ingredients

        except Exception as e:
            print(f"\033[31m[RecipeFacts] Error extracting ingredients: {e}\033[0m")
            return []

    def requires_crafting_table(self, item_name):
        """
        Check if an item requires a crafting table to craft.

        Args:
            item_name (str): Name of the item

        Returns:
            bool: True if crafting table is required, False if 2x2 grid is sufficient
        """
        try:
            recipes = self.get_recipe(item_name)
            if not recipes or len(recipes) == 0:
                return False

            # Check first recipe (usually most common)
            recipe = recipes[0]

            # If recipe has inShape or outShape with more than 2x2, needs table
            if hasattr(recipe, 'inShape'):
                shape = recipe.inShape
                if len(shape) > 2 or any(len(row) > 2 for row in shape):
                    return True

            return False

        except Exception as e:
            print(f"\033[31m[RecipeFacts] Error checking crafting table requirement: {e}\033[0m")
            return False
