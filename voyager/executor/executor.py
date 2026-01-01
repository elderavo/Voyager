"""
Executor: Direct primitive execution and recursive skill discovery.

Handles:
- Direct execution of primitives and known skills
- Recursive dependency resolution for crafting
- Skill synthesis from successful execution sequences
"""

import re
from typing import List, Optional, Tuple, Dict, Any

import voyager.utils as U

from .executor_utils import ExecutorUtils
from .executor_actions import ExecutorActions
from .executor_skills import ExecutorSkills, ExecutionStep, SkillDiscoveryTask


class Executor:
    """
    Executes primitives directly and recursively discovers crafting skills.

    This is a parallel execution path to the existing Action Agent flow.
    It enables:
    1. Direct primitive execution without LLM overhead
    2. Recursive dependency resolution
    3. Automatic skill composition and registration
    """

    def __init__(
        self,
        env,
        skill_manager,
        ckpt_dir: str = "ckpt",
        max_recursion_depth: int = 5,
    ):
        """
        Initialize the Executor.

        Args:
            env: VoyagerEnv instance for direct code execution
            skill_manager: SkillManager instance for skill storage/retrieval
            ckpt_dir: Checkpoint directory for skill storage
            max_recursion_depth: Maximum recursion depth for skill discovery
        """
        self.env = env
        self.skill_manager = skill_manager
        self.ckpt_dir = ckpt_dir
        self.max_recursion_depth = max_recursion_depth

        # Initialize sub-modules
        self.utils = ExecutorUtils(env, skill_manager)
        self.actions = ExecutorActions(env, skill_manager, self.utils)
        self.skills = ExecutorSkills(env, skill_manager, self.utils, max_recursion_depth)

        print(f"\033[36mExecutor initialized with max recursion depth: {max_recursion_depth}\033[0m")

    def execute_skill(self, skill_name: str) -> Tuple[bool, List[Any]]:
        """
        Execute an existing JavaScript skill.

        Args:
            skill_name: Name of the skill to execute (e.g., "craftPlanks")

        Returns:
            (success: bool, events: List)
        """
        success, events = self.actions.execute_skill(skill_name)

        return success, events

    def _get_item_count(self, item_name: str) -> int:
        """
        Get current inventory count of an item.

        Args:
            item_name: Normalized item name

        Returns:
            Count of item in inventory
        """
        code = f"bot.chat('INV_COUNT:' + (bot.inventory.count(bot.registry.itemsByName['{item_name}']?.id || -1)));"
        events = self.env.step(code, programs=self.skill_manager.programs)

        for event_type, event in events:
            if event_type == "onChat":
                msg = event.get("onChat", event) if isinstance(event, dict) else event
                if msg.startswith("INV_COUNT:"):
                    try:
                        return int(msg.split(":", 1)[1])
                    except (ValueError, IndexError):
                        return 0

        return 0

    def ensure_skill(self, skill_name: str, depth: int = 0, task_type: str = "craft") -> Tuple[bool, List[ExecutionStep]]:
        """
        Ensure a skill exists, discovering it recursively if needed.

        If the skill exists in the library, returns immediately.
        If not, attempts to discover it by:
        1. Trying direct execution
        2. Parsing missing dependencies
        3. Recursively ensuring each dependency
        4. Synthesizing and registering the skill

        Args:
            skill_name: Name of skill to ensure (e.g., "craftSticks")
            depth: Current recursion depth
            task_type: Type of task ("craft" or "mine")

        Returns:
            (success: bool, execution_sequence: List[ExecutionStep])
        """
        return self.skills.ensure_skill(skill_name, depth, task_type, actions_executor=self.actions)

    def craft_item(self, item_name: str, task_type: str = "craft"):
        """
        High-level helper to craft an item WITH QUANTITY SUPPORT using inventory delta.

        Uses inventory delta checking:
        - Get initial inventory count
        - Execute skill once
        - Check if inventory increased by desired amount
        - If not, loop until target reached or max retries hit
        """
        # =========================
        # 1. Extract quantity
        # =========================
        raw = item_name.strip()
        qty_match = re.match(r"^(\d+)\s+", raw)
        quantity = int(qty_match.group(1)) if qty_match else 1

        # =========================
        # 2. Normalize item name
        # =========================
        normalized = self.utils.normalize_item_name(item_name)

        if isinstance(normalized, str):
            normalized_name = normalized
        elif isinstance(normalized, dict) and normalized.get("suggestions"):
            suggestion = normalized["suggestions"][0]
            print(f"[DEBUG] Normalizing '{item_name}' → '{suggestion}' (auto-correct)")
            normalized_name = suggestion
        else:
            print(f"[DEBUG] Could not normalize '{item_name}' → no usable match")
            return False, [], ""

        # =========================
        # 3. Build skill name
        # =========================
        skill_name = f"craft{self.utils.to_camel_case(normalized_name)}"

        # =========================
        # 4. Get initial inventory count
        # =========================
        initial_count = self._get_item_count(normalized_name)
        target_count = initial_count + quantity
        print(f"[QUANTITY] Initial {normalized_name}: {initial_count}, Target: {target_count}")

        # =========================
        # 5. Ensure skill exists (this crafts the item during discovery)
        # =========================
        skill_ok, _ = self.ensure_skill(skill_name, depth=0, task_type=task_type)
        if not skill_ok:
            print(f"\033[31mFailed to ensure skill for crafting {normalized_name}\033[0m")
            return False, [], normalized_name

        # =========================
        # 6. Check inventory delta and craft more if needed
        # =========================
        all_events = []
        max_attempts = quantity * 2  # Safety limit

        for attempt in range(max_attempts):
            current_count = self._get_item_count(normalized_name)
            needed = target_count - current_count

            if needed <= 0:
                print(f"[QUANTITY] ✓ Reached target: {current_count}/{target_count}")
                return True, all_events, normalized_name

            print(f"[QUANTITY] Current: {current_count}, Needed: {needed} more (attempt {attempt+1}/{max_attempts})")

            success, events = self.execute_skill(skill_name)
            all_events.extend(events)

            if not success:
                print(f"\033[31m[QUANTITY] Craft failed at attempt {attempt+1}\033[0m")
                return False, all_events, normalized_name

        # Exhausted retries
        final_count = self._get_item_count(normalized_name)
        print(f"\033[31m[QUANTITY] Max attempts reached. Final: {final_count}/{target_count}\033[0m")
        return final_count >= target_count, all_events, normalized_name

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
        return self.actions.direct_mine(item_name, count, task_type)

    # Expose utility methods for backward compatibility
    def _normalize_item_name(self, raw_name: str) -> Optional[str]:
        """Normalize item name (backward compatibility)."""
        return self.utils.normalize_item_name(raw_name)

    def _to_camel_case(self, snake_str: str) -> str:
        """Convert snake_case to CamelCase (backward compatibility)."""
        return self.utils.to_camel_case(snake_str)

    def _extract_item_name(self, skill_name: str) -> str:
        """Extract item name from skill name (backward compatibility)."""
        return self.utils.extract_item_name(skill_name)

    def _check_execution_success(self, events: List[Tuple[str, Any]]) -> bool:
        """Check execution success (backward compatibility)."""
        return self.utils.check_execution_success(events)

    def _parse_dependencies(self, events: List[Tuple[str, Any]]) -> List[str]:
        """Parse dependencies (backward compatibility)."""
        return self.utils.parse_dependencies(events)

    def _direct_execute_craft(self, item_name: str) -> Tuple[bool, List[Any]]:
        """Direct craft execution (backward compatibility)."""
        return self.actions.direct_execute_craft(item_name)

    def _direct_execute_gather(self, item_name: str, count: int = 1) -> Tuple[bool, List[Any]]:
        """Direct gather execution (backward compatibility)."""
        return self.actions.direct_execute_gather(item_name, count)

    def _synthesize_skill(self, skill_name: str, execution_sequence: List[ExecutionStep]):
        """Synthesize skill (backward compatibility)."""
        return self.skills.synthesize_skill(skill_name, execution_sequence)

    def _ensure_dependency(self, dep: str, current_depth: int, task_type: str = "craft") -> bool:
        """Ensure dependency (backward compatibility)."""
        return self.skills.ensure_dependency(dep, current_depth, task_type, actions_executor=self.actions)

    def _get_available_items(self) -> List[str]:
        """Get available items (backward compatibility)."""
        return self.utils.get_available_items()

    def _match_item_js(self, normalized: str) -> Optional[str]:
        """Match item in JavaScript (backward compatibility)."""
        return self.utils.match_item_js(normalized)

    def _fallback_suggest_item(self, normalized: str) -> Optional[List[str]]:
        """Fallback item suggestion (backward compatibility)."""
        return self.utils.fallback_suggest_item(normalized)
