"""
Skill executor - validates and executes tasks using fact-based constraints.

This module ensures that all task execution is validated against authoritative
game mechanics before any primitives are executed. It prevents impossible
actions and automatically decomposes tasks into dependencies when prerequisites
are missing.
"""

from voyager.agents.task_queue import Task


class SkillExecutor:
    """
    Executes tasks with fact-based validation.

    This executor is the bridge between high-level intentions and low-level
    primitive actions. It:
    1. Validates prerequisites using RecipeFacts
    2. Decomposes tasks into dependencies when needed
    3. Only executes primitives when all prerequisites are met
    """

    def __init__(self, facts, inventory=None):
        """
        Initialize the skill executor.

        Args:
            facts: RecipeFacts instance for game mechanics validation
            inventory: Current bot inventory (dict of item_name -> count)
        """
        self.facts = facts
        self.inventory = inventory or {}

    def update_inventory(self, inventory):
        """
        Update the inventory from latest observations.

        Args:
            inventory (dict): Dictionary of item_name -> count
        """
        self.inventory = inventory
        print(f"\033[36m[SkillExecutor] Inventory updated: {len(self.inventory)} item types\033[0m")

    def execute(self, task):
        """
        Execute a task, validating prerequisites and returning missing dependencies.

        Args:
            task (Task): Task to execute

        Returns:
            list[Task]: List of missing prerequisite tasks (empty if task executed)
        """
        print(f"\033[36m[SkillExecutor] Executing task: {task}\033[0m")

        if task.action == "craft":
            return self._execute_craft(task)
        elif task.action == "gather" or task.action == "mine":
            # mine is just gather with tool requirements
            return self._execute_gather(task)
        elif task.action == "dependency":
            return self._resolve_dependency(task)
        elif task.action == "smelt":
            return self._execute_smelt(task)
        elif task.action == "equip":
            return self._execute_equip(task)
        elif task.action == "attack":
            return self._execute_attack(task)
        elif task.action == "place":
            return self._execute_place(task)
        elif task.action == "use":
            return self._execute_use(task)
        else:
            print(f"\033[31m[SkillExecutor] Unknown task action: {task.action}\033[0m")
            return []

    def _execute_craft(self, task):
        """
        Execute a craft task using mineflayer primitives.

        Args:
            task (Task): Craft task with payload = item name

        Returns:
            list[Task]: Missing ingredient tasks, or empty if crafting should proceed
        """
        item_name = task.payload
        print(f"\033[36m[SkillExecutor] Attempting to craft: {item_name}\033[0m")

        # Normalize to a canonical item id so we never pass bogus names to mineflayer
        normalized = self._normalize_item_name(item_name)
        if normalized is None:
            print(f"\033[31m[SkillExecutor] Cannot craft unknown item: {item_name}\033[0m")
            # Nothing valid to execute; do not push further dependencies
            return []

        # Try to get recipe for dependency checking, but don't fail if not found
        # Mineflayer might still be able to craft it even if RecipeFacts doesn't have the recipe
        if self.facts is not None:
            recipes = self.facts.get_recipe(normalized)
            if not recipes:
                print(f"\033[33m[SkillExecutor] No recipe found in RecipeFacts for: {normalized} (will still attempt craft)\033[0m")
                # Don't return empty - let mineflayer try to craft it
                # Update payload and continue
                task.payload = normalized
                return []

            # Check if we have all the ingredients
            missing_tasks = []
            recipe = recipes[0]  # Use first recipe (most common)
            ingredients = self.facts.get_ingredient_names(recipe)

            print(f"\033[36m[SkillExecutor] Recipe for {normalized} requires: {ingredients}\033[0m")

            for ingredient in ingredients:
                if not self._has_item(ingredient, 1):
                    print(f"\033[33m[SkillExecutor] Missing ingredient: {ingredient}\033[0m")
                    # Check if this ingredient can be crafted
                    ingredient_recipes = self.facts.get_recipe(ingredient)
                    if ingredient_recipes:
                        # Can be crafted - add as craft dependency
                        missing_tasks.append(Task("craft", ingredient, parent=task.parent))
                    else:
                        # Cannot be crafted - must be gathered
                        missing_tasks.append(Task("gather", ingredient, parent=task.parent))

            if missing_tasks:
                print(f"\033[33m[SkillExecutor] Cannot craft {normalized} yet, missing {len(missing_tasks)} ingredients\033[0m")
                return missing_tasks

        # Update payload so downstream code generation uses the canonical name
        task.payload = normalized
        print(f"\033[32m[SkillExecutor] Will execute via mineflayer: craft {normalized}\033[0m")
        return []  # No missing dependencies, ready to execute

    def _execute_gather(self, task):
        """
        Execute a gather/mine task using mineflayer primitives.

        Args:
            task (Task): Gather task with payload = resource/block name

        Returns:
            list[Task]: Missing tool tasks, or empty if gathering should proceed
        """
        resource = task.payload
        print(f"\033[36m[SkillExecutor] Attempting to gather/mine: {resource}\033[0m")

        # For now, return empty to indicate task should be executed via mineflayer code
        # The orchestrator will generate the actual mineflayer code
        print(f"\033[32m[SkillExecutor] Will execute via mineflayer: mine {resource}\033[0m")
        return []  # No missing dependencies, ready to execute

    def _resolve_dependency(self, task):
        """
        Resolve a dependency string into concrete tasks.

        Args:
            task (Task): Dependency task with payload in format "type:item"

        Returns:
            list[Task]: Concrete tasks to resolve the dependency

        Raises:
            ValueError: If the item name is invalid, to trigger LLM retry with correction
        """
        dependency = task.payload
        print(f"\033[36m[SkillExecutor] Resolving dependency: {dependency}\033[0m")

        if not isinstance(dependency, str) or ":" not in dependency:
            print(f"\033[31m[SkillExecutor] Invalid dependency format: {dependency}\033[0m")
            raise ValueError(f"Invalid dependency format: {dependency}. Must be 'type:item'")

        dep_type, dep_item = dependency.split(":", 1)
        dep_type = dep_type.strip()
        dep_item = dep_item.strip()

        if dep_type in ("craft", "tool_required"):
            # Normalize item name and ensure it corresponds to a real item/recipe.
            normalized = self._normalize_item_name(dep_item)
            if normalized is None:
                # Item name is invalid - raise error to trigger LLM retry
                error_msg = f"Unknown item '{dep_item}'. This is not a valid Minecraft item name. Please use exact item names from minecraft-data (e.g., 'stick' not 'sticks', 'planks' not 'plank')."
                print(f"\033[31m[SkillExecutor] {error_msg}\033[0m")
                raise ValueError(error_msg)

            if dep_type == "craft" and self.facts is not None:
                recipes = self.facts.get_recipe(normalized)
                if not recipes:
                    # Don't fail hard - RecipeFacts might not have the recipe but mineflayer might
                    print(f"\033[33m[SkillExecutor] No recipe in RecipeFacts for '{normalized}', but will attempt craft anyway\033[0m")

            return [Task("craft", normalized, parent=task.parent)]

        elif dep_type == "gather":
            # For gather, we currently assume dep_item is a valid block/resource name.
            return [Task("gather", dep_item, parent=task.parent)]

        elif dep_type == "locate":
            # TODO: Implement location tasks
            print(f"\033[33m[SkillExecutor] Location tasks not yet implemented\033[0m")
            return []

        else:
            print(f"\033[31m[SkillExecutor] Unknown dependency type: {dep_type}\033[0m")
            raise ValueError(f"Unknown dependency type: {dep_type}. Must be 'craft', 'gather', 'tool_required', or 'locate'")


    def _execute_smelt(self, task):
        """
        Execute a smelt task.

        Args:
            task (Task): Smelt task with payload = item to smelt

        Returns:
            list[Task]: Missing dependencies (fuel, furnace, raw material)
        """
        item_name = task.payload
        print(f"\033[36m[SkillExecutor] Attempting to smelt: {item_name}\033[0m")

        normalized = self._normalize_item_name(item_name)
        if normalized is None:
            print(f"\033[31m[SkillExecutor] Cannot smelt unknown item: {item_name}\033[0m")
            return []

        task.payload = normalized
        print(f"\033[32m[SkillExecutor] Will execute via mineflayer: smelt {normalized}\033[0m")
        return []

    def _normalize_item_name(self, item_name):
        """
        Normalize a free-form item string to a canonical mineflayer/minecraft-data item name.

        Ensures that task payloads correspond to real item identifiers so that:
        - RecipeFacts can resolve recipes reliably
        - Code generation can safely call craftItem / smeltItem / mcData.itemsByName
        """
        if not item_name or not self.facts:
            return None

        try:
            raw = str(item_name).strip()
            if not raw:
                return None

            base = raw.lower().replace(" ", "_")
            candidates = [raw, raw.lower(), base]

            # Simple plural → singular heuristics: "sticks" -> "stick", "torches" -> "torch"
            if base.endswith("s") and not base.endswith("ss"):
                candidates.append(base[:-1])
            if base.endswith("es"):
                candidates.append(base[:-2])

            # Try each candidate
            for candidate in candidates:
                if candidate and self.facts.is_valid_item(candidate):
                    return candidate

            print(f"\033[31m[SkillExecutor] Unknown item name (cannot normalize): {item_name}\033[0m")
            return None

        except Exception as e:
            print(f"\033[31m[SkillExecutor] Error normalizing item name {item_name}: {e}\033[0m")
            return None

    def _has_item(self, item_name, count=1):
        """
        Check if bot has an item in inventory.

        Args:
            item_name (str): Name of the item
            count (int): Minimum quantity required

        Returns:
            bool: True if item is in inventory with sufficient count
        """
        try:
            normalized = self._normalize_item_name(item_name)
            if normalized is None:
                return False

            # Check inventory dict directly
            total = self.inventory.get(normalized, 0)
            has_enough = total >= count

            print(f"\033[32m[SkillExecutor] Inventory check for {normalized}: have {total}, need {count} -> {has_enough}\033[0m")
            return has_enough

        except Exception as e:
            print(f"\033[31m[SkillExecutor] Error checking inventory: {e}\033[0m")
            return False

    def _has_access_to_crafting_table(self):
        """
        Check if bot has access to a crafting table.

        Returns:
            bool: True if crafting table is in inventory
        """
        # Simplified version - just check inventory
        # Finding nearby blocks would require bot access
        if self._has_item("crafting_table", 1):
            print("\033[32m[SkillExecutor] Crafting table available in inventory\033[0m")
            return True

        print("\033[33m[SkillExecutor] No crafting table in inventory (nearby check not implemented)\033[0m")
        return False

    def _execute_equip(self, task):
        """
        Execute an equip task.

        Args:
            task (Task): Equip task with payload = item to equip

        Returns:
            list[Task]: Missing dependencies (item to equip if not in inventory)
        """
        item_name = task.payload
        print(f"\033[36m[SkillExecutor] Attempting to equip: {item_name}\033[0m")

        normalized = self._normalize_item_name(item_name)
        if normalized is None:
            print(f"\033[31m[SkillExecutor] Cannot equip unknown item: {item_name}\033[0m")
            return []

        # Check if we have the item to equip
        if not self._has_item(normalized, 1):
            print(f"\033[33m[SkillExecutor] Missing item to equip: {normalized}\033[0m")
            # Check if it can be crafted or must be gathered
            if self.facts is not None:
                recipes = self.facts.get_recipe(normalized)
                if recipes:
                    return [Task("craft", normalized, parent=task.parent)]
                else:
                    return [Task("gather", normalized, parent=task.parent)]
            else:
                return [Task("gather", normalized, parent=task.parent)]

        task.payload = normalized
        print(f"\033[32m[SkillExecutor] Will execute via mineflayer: equip {normalized}\033[0m")
        return []

    def _execute_attack(self, task):
        """
        Execute an attack task.

        Args:
            task (Task): Attack task with payload = entity to attack

        Returns:
            list[Task]: Missing dependencies (weapon if needed)
        """
        entity_name = task.payload
        print(f"\033[36m[SkillExecutor] Attempting to attack: {entity_name}\033[0m")

        # For now, assume we can attack without checking for weapon
        # TODO: Add weapon requirement checking for specific entities
        print(f"\033[32m[SkillExecutor] Will execute via mineflayer: attack {entity_name}\033[0m")
        return []

    def _execute_place(self, task):
        """
        Execute a place task.

        Args:
            task (Task): Place task with payload = block to place

        Returns:
            list[Task]: Missing dependencies (block to place if not in inventory)
        """
        block_name = task.payload
        print(f"\033[36m[SkillExecutor] Attempting to place: {block_name}\033[0m")

        normalized = self._normalize_item_name(block_name)
        if normalized is None:
            print(f"\033[31m[SkillExecutor] Cannot place unknown block: {block_name}\033[0m")
            return []

        # Check if we have the block to place
        if not self._has_item(normalized, 1):
            print(f"\033[33m[SkillExecutor] Missing block to place: {normalized}\033[0m")
            # Check if it can be crafted or must be gathered
            if self.facts is not None:
                recipes = self.facts.get_recipe(normalized)
                if recipes:
                    return [Task("craft", normalized, parent=task.parent)]
                else:
                    return [Task("gather", normalized, parent=task.parent)]
            else:
                return [Task("gather", normalized, parent=task.parent)]

        task.payload = normalized
        print(f"\033[32m[SkillExecutor] Will execute via mineflayer: place {normalized}\033[0m")
        return []

    def _execute_use(self, task):
        """
        Execute a use task.

        Args:
            task (Task): Use task with payload = item to use

        Returns:
            list[Task]: Missing dependencies (item to use if not in inventory)
        """
        item_name = task.payload
        print(f"\033[36m[SkillExecutor] Attempting to use: {item_name}\033[0m")

        normalized = self._normalize_item_name(item_name)
        if normalized is None:
            print(f"\033[31m[SkillExecutor] Cannot use unknown item: {item_name}\033[0m")
            return []

        # Check if we have the item to use
        if not self._has_item(normalized, 1):
            print(f"\033[33m[SkillExecutor] Missing item to use: {normalized}\033[0m")
            # Check if it can be crafted or must be gathered
            if self.facts is not None:
                recipes = self.facts.get_recipe(normalized)
                if recipes:
                    return [Task("craft", normalized, parent=task.parent)]
                else:
                    return [Task("gather", normalized, parent=task.parent)]
            else:
                return [Task("gather", normalized, parent=task.parent)]

        task.payload = normalized
        print(f"\033[32m[SkillExecutor] Will execute via mineflayer: use {normalized}\033[0m")
        return []

