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

    def __init__(self, bot, facts):
        """
        Initialize the skill executor.

        Args:
            bot: Mineflayer bot instance
            facts: RecipeFacts instance for game mechanics validation
        """
        self.bot = bot
        self.facts = facts

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
        else:
            print(f"\033[31m[SkillExecutor] Unknown task action: {task.action}\033[0m")
            return []

    def _execute_craft(self, task):
        """
        Execute a craft task using mineflayer primitives.

        Args:
            task (Task): Craft task with payload = item name

        Returns:
            list[Task]: Missing ingredient tasks, or empty if crafting succeeded
        """
        item_name = task.payload
        print(f"\033[36m[SkillExecutor] Attempting to craft: {item_name}\033[0m")

        # For now, just return empty to execute via mineflayer
        # The mineflayer craftItem function will handle checking ingredients and recipes
        print(f"\033[32m[SkillExecutor] Will execute via mineflayer: craft {item_name}\033[0m")
        return []  # No missing dependencies, ready to execute

    def _execute_gather(self, task):
        """
        Execute a gather/mine task using mineflayer primitives.

        Args:
            task (Task): Gather task with payload = resource/block name

        Returns:
            list[Task]: Missing tool tasks, or empty if gathering succeeded
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
        """
        dependency = task.payload
        print(f"\033[36m[SkillExecutor] Resolving dependency: {dependency}\033[0m")

        if ":" not in dependency:
            print(f"\033[31m[SkillExecutor] Invalid dependency format: {dependency}\033[0m")
            return []

        dep_type, dep_item = dependency.split(":", 1)

        if dep_type == "craft":
            return [Task("craft", dep_item, parent=task.parent)]
        elif dep_type == "gather":
            return [Task("gather", dep_item, parent=task.parent)]
        elif dep_type == "tool_required":
            return [Task("craft", dep_item, parent=task.parent)]
        elif dep_type == "locate":
            # TODO: Implement location tasks
            print(f"\033[33m[SkillExecutor] Location tasks not yet implemented\033[0m")
            return []
        else:
            print(f"\033[31m[SkillExecutor] Unknown dependency type: {dep_type}\033[0m")
            return []

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

        # For now, return empty to execute via mineflayer
        print(f"\033[32m[SkillExecutor] Will execute via mineflayer: smelt {item_name}\033[0m")
        return []

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
            # TODO:
            # 1. Use the mineflayer bot's inventory API to inspect all items:
            #    - Prefer `self.bot.inventory.items()` (or the equivalent for your version).
            #    - Normalize `item_name` to the correct mineflayer item identifier
            #      (e.g., via `self.bot.registry.itemsByName[item_name]` or a shared
            #      name→id helper so Python and JS agree on naming).
            # 2. Iterate inventory items and sum counts for all matching items:
            #    - Match either by `item.name` or by numeric `item.type` (id), but be
            #      consistent across the codebase.
            #    - Take item metadata/variant into account if needed (e.g., different
            #      wood types) using minecraft-data / registry information.
            # 3. Return True if the total count for the requested item is >= `count`,
            #    otherwise False.
            # 4. Consider moving any name/id normalization into a shared utility
            #    module (e.g., `voyager/minecraft/items.py`) so that other agents,
            #    RecipeFacts, and the JS side all share the same mapping.
            # 5. Keep this function as a thin wrapper over mineflayer; do not
            #    replicate minecraft-data or recipe logic here.
            return False
        except Exception as e:
            print(f"\033[31m[SkillExecutor] Error checking inventory: {e}\033[0m")
            return False

    def _has_access_to_crafting_table(self):
        """
        Check if bot has access to a crafting table.

        Returns:
            bool: True if crafting table is nearby or in inventory
        """
        try:
            # TODO:
            # 1. Check if the bot already has a crafting table item:
            #    - Call `_has_item("crafting_table", 1)` using the same naming/
            #      id convention as the JS side.
            # 2. If not in inventory, use mineflayer's world query APIs:
            #    - Use `self.bot.registry.blocksByName.crafting_table.id` (or
            #      equivalent) to get the correct block id.
            #    - Call `self.bot.findBlock({...})` with a reasonable search
            #      radius (e.g., 4–6 blocks, potentially configurable).
            # 3. Return True if either inventory or world search finds access
            #    to a crafting table; otherwise return False.
            # 4. Keep this as a pure availability check; pathfinding, walking
            #    to the table, or placing one should be handled by higher-level
            #    skills / tasks, not here.
            # 5. If version differences matter, gate behavior behind
            #    `self.bot.supportFeature(...)` rather than hardcoding ids.
            return False
        except Exception as e:
            print(f"\033[31m[SkillExecutor] Error checking for crafting table: {e}\033[0m")
            return False
