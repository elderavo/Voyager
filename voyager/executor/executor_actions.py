"""
Executor actions: Direct execution of primitives and skills.

This module contains functions for direct execution of:
- Crafting primitives
- Mining/gathering primitives
- Existing JavaScript skills
"""

import re
from typing import List, Tuple, Any, Dict
from .executor_utils import ExecutorUtils


class ExecutorActions:
    """Direct action execution for the Executor."""

    def __init__(self, env, skill_manager, utils: ExecutorUtils):
        """
        Initialize ExecutorActions.

        Args:
            env: VoyagerEnv instance for direct code execution
            skill_manager: SkillManager instance for skill storage/retrieval
            utils: ExecutorUtils instance for utility functions
        """
        self.env = env
        self.skill_manager = skill_manager
        self.utils = utils

    def execute_skill(self, skill_name: str) -> Tuple[bool, List[Any]]:
        """
        Execute an existing JavaScript skill.

        Args:
            skill_name: Name of the skill to execute (e.g., "craftPlanks")

        Returns:
            (success: bool, events: List)
        """
        if skill_name not in self.skill_manager.skills:
            print(f"\033[31mSkill '{skill_name}' not found in skill library\033[0m")
            return False, []

        print(f"\033[36mExecuting skill: {skill_name}\033[0m")

        # Execute via env.step
        exec_code = f"await {skill_name}(bot);"
        events = self.env.step(
            code=exec_code,
            programs=self.skill_manager.programs
        )

        # Check success (no errors in events)
        success = self.utils.check_execution_success(events)

        return success, events

    def direct_execute_craft(self, item_name: str) -> Tuple[bool, List[Any]]:
        """
        Directly execute craftItem primitive.
        If missing-crafting-table error occurs, place a table if possible,
        then retry once. Otherwise return result normally.
        """

        code = f"await craftItem(bot, '{item_name}', 1);"

        # ---- FIRST ATTEMPT ----
        events = self.env.step(code=code, programs=self.skill_manager.programs)
        success = self.utils.check_execution_success(events)

        if success:
            return True, events

        # ---- Check for missing crafting table ----
        if self.utils.is_missing_crafting_table_error(events):
            print("[CT] Missing table → placing one if we have it")
            self.direct_place_item("crafting_table")

            # ---- RETRY CRAFT ----
            retry_events = self.env.step(code=code, programs=self.skill_manager.programs)
            retry_success = self.utils.check_execution_success(retry_events)

            # Merge event streams if you want full trace
            combined = events + retry_events
            return retry_success, combined

        # ---- Not a crafting-table-related failure ----
        return False, events


    def direct_execute_gather(self, item_name: str, count: int = 1) -> Tuple[bool, List[Any]]:
        """
        Directly execute mineBlock primitive.

        Args:
            item_name: Item to gather
            count: Number to gather

        Returns:
            (success: bool, events: List)
        """
        code = f"await mineBlock(bot, '{item_name}', {count});"
        events = self.env.step(code=code, programs=self.skill_manager.programs)
        success = self.utils.check_execution_success(events)
        return success, events

    def craft_item(self, item_name: str, task_type: str = "craft") -> Tuple[bool, List[Any], str]:
        """
        High-level helper to craft an item WITH QUANTITY SUPPORT.
        Always returns (success, events, normalized_name).

        Note: This method requires skill discovery capabilities and will be
        connected to ExecutorSkills in the main Executor class.
        """
        # This is a placeholder - the actual implementation will be in the main Executor
        # class which has access to both actions and skills modules
        raise NotImplementedError("craft_item should be called from main Executor class")

    def direct_mine(self, item_name: str, count: int = 1, task_type: str = "mine") -> Tuple[bool, List[Any]]:
        """
        Direct mining primitive, bypasses skill synthesis and crafting logic.

        This is used for mining tasks to prevent them from triggering crafting
        dependencies or being saved as skills.

        Args:
            item_name: Item to mine
            count: Number to mine
            task_type: Type of task (should be "mine")

        Returns:
            (success: bool, events: List)
        """
        print(f"\033[36m[DEBUG] Direct mining: {count} x {item_name}\033[0m")

        # Normalize the item name (e.g., "wood log" -> "oak_log")
        normalized = self.utils.normalize_item_name(item_name)

        # Handle normalization result
        if isinstance(normalized, str):
            normalized_name = normalized
        elif isinstance(normalized, dict) and normalized.get("suggestions"):
            normalized_name = normalized["suggestions"][0]
            print(f"[DEBUG] Normalizing '{item_name}' → '{normalized_name}' (auto-correct)")
        else:
            print(f"[DEBUG] Could not normalize '{item_name}' for mining")
            # Try using the raw name as fallback
            normalized_name = item_name.lower().replace(" ", "_")

        success, events = self.direct_execute_gather(normalized_name, count)
        return success, events

    def direct_place_item(self, item_name: str) -> Tuple[bool, List[Any]]:
        code = (
            "const pos = bot.entity.position.offset(1, 0, 0);"
            f"await placeItem(bot, '{item_name}', pos);"
)
        events = self.env.step(code=code, programs=self.skill_manager.programs)
        success = self.utils.check_execution_success(events)
        return success, events

