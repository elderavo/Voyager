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

    This class queries the Mineflayer server's registry via HTTP for accurate
    game information, preventing LLM hallucination of recipes.
    """

    def __init__(self, env):
        """
        Initialize the recipe fact source.

        Args:
            env: VoyagerEnv instance with registry access
        """
        self.env = env
        self._item_cache = None
        self._block_cache = None

    def _ensure_cache(self):
        """Ensure item and block caches are loaded."""
        if self._item_cache is None:
            items = self.env.get_registry("items")
            if items:
                self._item_cache = set(items)
            else:
                self._item_cache = set()
                print("\033[33m[RecipeFacts] Warning: Could not load item cache\033[0m")

        if self._block_cache is None:
            blocks = self.env.get_registry("blocks")
            if blocks:
                self._block_cache = set(blocks)
            else:
                self._block_cache = set()
                print("\033[33m[RecipeFacts] Warning: Could not load block cache\033[0m")

    def is_valid_item(self, item_name):
        """
        Check if an item name is valid.

        Args:
            item_name (str): Name of the item

        Returns:
            bool: True if valid, False otherwise
        """
        self._ensure_cache()
        return item_name in self._item_cache

    def is_valid_block(self, block_name):
        """
        Check if a block name is valid.

        Args:
            block_name (str): Name of the block

        Returns:
            bool: True if valid, False otherwise
        """
        self._ensure_cache()
        return block_name in self._block_cache

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
            recipes = self.env.get_registry("recipes", name=item_name)

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
        # Note: Full block metadata (harvestTools) requires more complex registry access
        # For now, we'll implement basic validation only
        # TODO: Extend /registry endpoint to include block metadata if needed
        self._ensure_cache()

        if block_name not in self._block_cache:
            print(f"\033[31m[RecipeFacts] Block not found: {block_name}\033[0m")
            return None

        # For now, assume no tool requirement
        # This can be extended later with more detailed block data
        print(f"\033[33m[RecipeFacts] Tool requirements not fully implemented yet\033[0m")
        return {}

    def can_harvest(self, block_name, tool_name):
        """
        Check if a specific tool can harvest a specific block.

        Args:
            block_name (str): Name of the block to mine
            tool_name (str): Name of the tool to use

        Returns:
            bool: True if the tool can harvest the block, False otherwise
        """
        self._ensure_cache()

        # Basic validation - check if block and tool exist
        if block_name not in self._block_cache:
            return False

        if tool_name not in self._item_cache:
            return False

        # For now, assume all tools can harvest all blocks
        # This can be extended with more detailed metadata later
        print(f"\033[33m[RecipeFacts] Harvest validation simplified - assuming {tool_name} can harvest {block_name}\033[0m")
        return True

    def get_ingredient_names(self, recipe):
        """
        Extract ingredient names from a recipe object.

        Args:
            recipe: Recipe object from Mineflayer (dict format from HTTP)

        Returns:
            list: List of ingredient item names
        """
        try:
            if not recipe:
                return []

            # The enhanced recipe from the /registry endpoint includes ingredientNames
            if 'ingredientNames' in recipe:
                return recipe['ingredientNames']

            # Fallback: if ingredientNames not present, log warning
            print(f"\033[33m[RecipeFacts] Warning: Recipe missing ingredientNames field\033[0m")
            return []

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
