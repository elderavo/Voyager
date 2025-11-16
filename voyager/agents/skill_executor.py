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
        elif task.action == "gather":
            return self._execute_gather(task)
        elif task.action == "dependency":
            return self._resolve_dependency(task)
        elif task.action == "move":
            return self._execute_move(task)
        elif task.action == "equip":
            return self._execute_equip(task)
        else:
            print(f"\033[31m[SkillExecutor] Unknown task action: {task.action}\033[0m")
            return []

    def _execute_craft(self, task):
        """
        Execute a craft task, checking recipe and inventory.

        Args:
            task (Task): Craft task with payload = item name

        Returns:
            list[Task]: Missing ingredient tasks, or empty if crafting succeeded
        """
        item_name = task.payload
        print(f"\033[36m[SkillExecutor] Attempting to craft: {item_name}\033[0m")

        # Get recipe from fact source
        recipes = self.facts.get_recipe(item_name)
        if not recipes or len(recipes) == 0:
            print(f"\033[31m[SkillExecutor] No recipe found for {item_name}\033[0m")
            return []  # Cannot craft, skip

        recipe = recipes[0]  # Use first recipe

        # Check if crafting table is required
        requires_table = self.facts.requires_crafting_table(item_name)
        if requires_table and not self._has_access_to_crafting_table():
            print(f"\033[33m[SkillExecutor] Crafting table required for {item_name}\033[0m")
            return [Task("craft", "crafting_table", parent=task.parent)]

        # Check inventory for ingredients
        missing = []
        ingredients = self.facts.get_ingredient_names(recipe)

        for ingredient in ingredients:
            if not self._has_item(ingredient):
                print(f"\033[33m[SkillExecutor] Missing ingredient: {ingredient}\033[0m")
                # Determine if ingredient needs crafting or gathering
                # For now, assume it needs crafting (can be improved with item classification)
                missing.append(Task("craft", ingredient, parent=task.parent))

        if missing:
            return missing

        # All prerequisites met - execute craft primitive
        print(f"\033[32m[SkillExecutor] Crafting {item_name}\033[0m")
        # TODO: Call Mineflayer craftItem primitive
        # self.bot.craftItem(item_name, 1)

        return []  # Task completed

    def _execute_gather(self, task):
        """
        Execute a gather task, checking tool requirements.

        Args:
            task (Task): Gather task with payload = resource/block name

        Returns:
            list[Task]: Missing tool tasks, or empty if gathering succeeded
        """
        resource = task.payload
        print(f"\033[36m[SkillExecutor] Attempting to gather: {resource}\033[0m")

        # Check tool requirements
        required_tools = self.facts.required_tool(resource)

        if required_tools and len(required_tools) > 0:
            # Check if bot has any valid tool
            has_valid_tool = False
            for tool_id in required_tools.keys():
                tool_name = self.bot.registry.items[tool_id].name
                if self._has_item(tool_name):
                    has_valid_tool = True
                    break

            if not has_valid_tool:
                # Need to craft a tool
                # For now, pick first valid tool (can be improved with tool priority)
                tool_id = list(required_tools.keys())[0]
                tool_name = self.bot.registry.items[tool_id].name
                print(f"\033[33m[SkillExecutor] Need tool: {tool_name} to gather {resource}\033[0m")
                return [Task("craft", tool_name, parent=task.parent)]

        # All prerequisites met - execute gather primitive
        print(f"\033[32m[SkillExecutor] Gathering {resource}\033[0m")
        # TODO: Call Mineflayer mineBlock primitive
        # self.bot.mineBlock(resource, 1)

        return []  # Task completed

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

    def _execute_move(self, task):
        """
        Execute a move task.

        Args:
            task (Task): Move task with payload = target position/direction

        Returns:
            list[Task]: Empty (move is primitive action)
        """
        print(f"\033[36m[SkillExecutor] Moving to: {task.payload}\033[0m")
        # TODO: Implement movement primitives
        return []

    def _execute_equip(self, task):
        """
        Execute an equip task.

        Args:
            task (Task): Equip task with payload = item name

        Returns:
            list[Task]: Empty if equipped, or craft task if item missing
        """
        item_name = task.payload
        print(f"\033[36m[SkillExecutor] Equipping: {item_name}\033[0m")

        if not self._has_item(item_name):
            print(f"\033[33m[SkillExecutor] Cannot equip - don't have {item_name}\033[0m")
            return [Task("craft", item_name, parent=task.parent)]

        # TODO: Call Mineflayer equip primitive
        # self.bot.equip(item_name)

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
            # TODO: Implement actual inventory check via Mineflayer
            # For now, return False to trigger dependency resolution
            # inv = self.bot.inventory.items()
            # for item in inv:
            #     if item.name == item_name and item.count >= count:
            #         return True
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
            # TODO: Check both inventory and nearby blocks
            # has_in_inventory = self._has_item("crafting_table")
            # nearby_table = self.bot.findBlock({
            #     "matching": self.bot.registry.blocksByName.crafting_table.id,
            #     "maxDistance": 4
            # })
            # return has_in_inventory or nearby_table is not None
            return False
        except Exception as e:
            print(f"\033[31m[SkillExecutor] Error checking for crafting table: {e}\033[0m")
            return False
