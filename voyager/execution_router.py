"""
Execution Routing Module

Decides HOW a task should be executed based on task type and world state.
Returns ExecutionPlan without referencing implementation details.
"""

from typing import Optional, Any
from .task_spec import TaskSpec, TaskType
from .execution_plan import ExecutionPlan, ExecutionMode


class ExecutionRouter:
    """
    Routes tasks to appropriate execution modes.

    Responsibilities:
    - Decide execution mode based on task type and world state
    - Check for existing skills
    - Choose between primitive, HTN, or LLM execution
    - Return ExecutionPlan (metadata only, no implementation logic)
    """

    def __init__(self, skill_manager: Any):
        """
        Initialize the ExecutionRouter.

        Args:
            skill_manager: SkillManager instance for checking existing skills
        """
        self.skill_manager = skill_manager

    def route(
        self,
        task_spec: TaskSpec,
        world_state: Optional[Any] = None
    ) -> ExecutionPlan:
        """
        Route a task to an appropriate execution mode.

        Phase 1 Implementation:
        1. If matching skill exists → EXISTING_SKILL
        2. If task_type == CRAFT → EXECUTOR_PRIMITIVE
        3. If task_type == MINE → EXECUTOR_PRIMITIVE
        4. Else → ACTION_LLM

        Future phases will add:
        - HTN planning for complex tasks
        - Context-aware routing
        - Difficulty-based routing

        Args:
            task_spec: Structured task specification
            world_state: Optional world state for context-aware routing

        Returns:
            ExecutionPlan with routing decision
        """
        # Check for existing skill first
        skill_name = self._find_matching_skill(task_spec)
        if skill_name:
            return ExecutionPlan(
                mode=ExecutionMode.EXISTING_SKILL,
                skill_name=skill_name,
                save_as_skill=False  # Already a skill
            )

        # Route based on task type
        if task_spec.type == TaskType.CRAFT:
            return ExecutionPlan(
                mode=ExecutionMode.EXECUTOR_PRIMITIVE,
                save_as_skill=True  # Crafting primitives can be saved
            )

        elif task_spec.type == TaskType.MINE:
            return ExecutionPlan(
                mode=ExecutionMode.EXECUTOR_PRIMITIVE,
                save_as_skill=False  # Mining is always primitive, don't save
            )

        elif task_spec.type == TaskType.GATHER:
            # Treat as mining for now
            return ExecutionPlan(
                mode=ExecutionMode.EXECUTOR_PRIMITIVE,
                save_as_skill=False
            )

        # Default to Action LLM for unknown or complex tasks
        return ExecutionPlan(
            mode=ExecutionMode.ACTION_LLM,
            fallback_mode=ExecutionMode.EXECUTOR_PRIMITIVE,
            save_as_skill=True
        )

    def _find_matching_skill(self, task_spec: TaskSpec) -> Optional[str]:
        """
        Find a matching skill for the given task.

        Args:
            task_spec: Task specification

        Returns:
            Skill name if found, None otherwise
        """
        # Build potential skill name based on task type and params
        if task_spec.type == TaskType.CRAFT:
            item_name = task_spec.params.get("item", "")
            if item_name:
                # Convert to camelCase skill name
                skill_name = self._to_skill_name("craft", item_name)
                if self._skill_exists(skill_name):
                    return skill_name

        elif task_spec.type == TaskType.MINE:
            block_name = task_spec.params.get("block", "")
            if block_name:
                skill_name = self._to_skill_name("mine", block_name)
                if self._skill_exists(skill_name):
                    return skill_name

        # Could add more sophisticated skill matching here
        # (e.g., semantic search, partial matches)

        return None

    def _to_skill_name(self, action: str, item_name: str) -> str:
        """
        Convert action and item name to skill name format.

        Examples:
            craft, oak_planks -> craftOakPlanks
            mine, cobblestone -> mineCobblestone
        """
        # Convert snake_case to CamelCase
        parts = item_name.split("_")
        camel = "".join(word.capitalize() for word in parts)
        return f"{action}{camel}"

    def _skill_exists(self, skill_name: str) -> bool:
        """
        Check if a skill exists in the skill library.

        Args:
            skill_name: Name of the skill to check

        Returns:
            True if skill exists, False otherwise
        """
        if not self.skill_manager or not hasattr(self.skill_manager, 'skills'):
            return False

        return skill_name in self.skill_manager.skills
