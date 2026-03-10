"""
Executor actions: Direct execution of primitives and skills.

This module contains functions for direct execution of:
- Crafting primitives
- Mining/gathering primitives
- Existing JavaScript skills
"""

import re
from typing import List, Any
from voyager.types import ExecutionResult
from voyager.trace import Trace
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

    def execute_skill(self, skill_name: str) -> ExecutionResult:
        """
        Execute an existing JavaScript skill.

        Args:
            skill_name: Name of the skill to execute (e.g., "craftPlanks")

        Returns:
            ExecutionResult with success flag and trace
        """
        if skill_name not in self.skill_manager.skills:
            print(f"\033[31mSkill '{skill_name}' not found in skill library\033[0m")
            return ExecutionResult(
                success=False,
                trace=Trace.from_events([])
            )

        print(f"\033[36mExecuting skill: {skill_name}\033[0m")

        # Execute via env.step
        exec_code = f"await {skill_name}(bot);"
        events = self.env.step(
            code=exec_code,
            programs=self.skill_manager.programs
        )

        # Check success (no errors in events)
        success = self.utils.check_execution_success(events)

        return ExecutionResult(
            success=success,
            trace=Trace.from_events(events)
        )

    def direct_execute_craft(self, item_name: str) -> ExecutionResult:
        """
        Directly execute the craftItem primitive.

        Args:
            item_name: Item to craft

        Returns:
            ExecutionResult with success flag and trace
        """
        code = f"await craftItem(bot, '{item_name}', 1);"
        events = self.env.step(code, programs=self.skill_manager.programs)
        success = self.utils.check_execution_success(events)
        return ExecutionResult(
            success=success,
            trace=Trace.from_events(events)
        )

    def direct_execute_gather(self, item_name: str, count: int = 1) -> ExecutionResult:
        """
        Directly execute mineBlock primitive.

        Args:
            item_name: Item to gather
            count: Number to gather

        Returns:
            ExecutionResult with success flag and trace
        """
        code = f"await mineBlock(bot, '{item_name}', {count});"
        events = self.env.step(code=code, programs=self.skill_manager.programs)
        success = self.utils.check_execution_success(events)
        return ExecutionResult(
            success=success,
            trace=Trace.from_events(events)
        )

    def craft_item(self, item_name: str, task_type: str = "craft"):
        """
        High-level helper to craft an item WITH QUANTITY SUPPORT.
        Always returns (success, events, normalized_name).

        Note: This method requires skill discovery capabilities and will be
        connected to ExecutorSkills in the main Executor class.
        """
        # This is a placeholder - the actual implementation will be in the main Executor
        # class which has access to both actions and skills modules
        raise NotImplementedError("craft_item should be called from main Executor class")

    def direct_mine(self, item_name: str, count: int = 1, task_type: str = "mine") -> ExecutionResult:
        """
        Direct mining primitive, bypasses skill synthesis and crafting logic.

        This is used for mining tasks to prevent them from triggering crafting
        dependencies or being saved as skills.

        Args:
            item_name: Item to mine
            count: Number to mine
            task_type: Type of task (should be "mine")

        Returns:
            ExecutionResult with success flag and trace
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

        return self.direct_execute_gather(normalized_name, count)

    def direct_place_item(self, item_name: str) -> ExecutionResult:
        """
        Directly place an item adjacent to the bot.

        Args:
            item_name: Item to place

        Returns:
            ExecutionResult with success flag and trace
        """
        code = (
            "const pos = bot.entity.position.offset(1, 0, 0);"
            f"await placeItem(bot, '{item_name}', pos);"
        )
        events = self.env.step(code=code, programs=self.skill_manager.programs)
        success = self.utils.check_execution_success(events)
        return ExecutionResult(
            success=success,
            trace=Trace.from_events(events)
        )

    def get_source_blocks_for_item(self, item_name: str) -> List[str]:
        """
        Get all block names that drop the specified item when mined.

        Uses mcData to authoritatively determine which blocks produce
        the desired item as a drop.

        Args:
            item_name: The item to find source blocks for (e.g., "cobblestone")

        Returns:
            List of block names that drop this item (e.g., ["stone"] for cobblestone)
        """
        # Normalize JS string safely
        safe = item_name.replace("\\", "\\\\").replace("'", "\\'").strip()

    # const {{ getSourceBlocksForItem }} = require('./voyager/control_primitives/getSourceBlocksForItem.js');
    # const mcData = require('minecraft-data')(bot.version);

        code = f"""
try {{
    const result = getSourceBlocksForItem('{safe}', mcData);
    bot.chat("SOURCE_BLOCKS:" + JSON.stringify(result));
}} catch (e) {{
    bot.chat("ERR:" + e.toString());
}}
"""

        events = self.env.step(code=code, programs=self.skill_manager.programs)

        for event_type, event in events:
            if event_type == "onChat":
                msg = event.get("onChat", event) if isinstance(event, dict) else event
                if msg.startswith("SOURCE_BLOCKS:"):
                    import json
                    payload = msg.split("SOURCE_BLOCKS:", 1)[1].strip()
                    try:
                        return json.loads(payload)
                    except json.JSONDecodeError as e:
                        print(f"\033[31m[ERROR] Failed to parse SOURCE_BLOCKS JSON: {e}\033[0m")
                        return []
                elif msg.startswith("ERR:"):
                    print(f"\033[31m[ERROR] JS error in getSourceBlocksForItem: {msg[4:]}\033[0m")
                    return []

        return []
