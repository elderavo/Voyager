"""
Primitive Task Executor

Wraps the existing Executor class for direct primitive execution.
Handles crafting, mining, smelting, and other primitive operations.
"""

from typing import Any
from .base_executor import TaskExecutor, ExecutionResult
from ..task_spec import TaskSpec, TaskType


class PrimitiveExecutor(TaskExecutor):
    """
    Executor for primitive operations.

    Wraps the existing Executor class to provide:
    - Direct crafting (craft_item)
    - Direct mining (direct_mine)
    - Future: smelting, placing, etc.
    """

    def __init__(self, executor: Any):
        """
        Initialize the PrimitiveExecutor.

        Args:
            executor: Existing Executor instance
        """
        self.executor = executor

    def execute(self, task_spec: TaskSpec, plan, world_state) -> ExecutionResult:
        """
        Execute a primitive task.

        Routes to appropriate primitive method based on task type.

        Args:
            task_spec: TaskSpec with task details
            plan: ExecutionPlan (not used for primitives)
            world_state: WorldStateTracker (not used directly)

        Returns:
            ExecutionResult with outcome
        """
        if task_spec.type == TaskType.CRAFT:
            return self._execute_craft(task_spec)
        elif task_spec.type == TaskType.MINE:
            return self._execute_mine(task_spec)
        elif task_spec.type == TaskType.GATHER:
            # Treat as mining for now
            return self._execute_mine(task_spec)
        elif task_spec.type == TaskType.SMELT:
            return self._execute_smelt(task_spec)
        else:
            return ExecutionResult(
                success=False,
                events=[],
                errors=[f"Unsupported primitive task type: {task_spec.type}"]
            )

    def _execute_craft(self, task_spec: TaskSpec) -> ExecutionResult:
        """
        Execute a crafting task.

        Uses the existing executor.craft_item() method.
        """
        item_name = task_spec.params.get("item", "")
        count = task_spec.params.get("count", 1)

        # Build item string with count if needed
        if count > 1:
            item_str = f"{count} {item_name}"
        else:
            item_str = item_name

        try:
            success, events, normalized_name = self.executor.craft_item(
                item_str,
                task_type="craft"
            )

            # Build skill name if successful
            program_name = None
            program_code = None
            if success:
                skill_name = f"craft{self.executor._to_camel_case(normalized_name)}"
                if skill_name in self.executor.skill_manager.skills:
                    program_name = skill_name
                    program_code = self.executor.skill_manager.skills[skill_name]["code"]

            return ExecutionResult(
                success=success,
                events=events if events else [],
                program_code=program_code,
                program_name=program_name,
                is_one_line_primitive=False  # Crafting can be complex
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                events=[],
                errors=[f"Crafting error: {str(e)}"]
            )

    def _execute_mine(self, task_spec: TaskSpec) -> ExecutionResult:
        """
        Execute a mining task.

        Uses the existing executor.direct_mine() method.
        """
        block_name = task_spec.params.get("block", "")
        count = task_spec.params.get("count", 1)

        try:
            success, events = self.executor.direct_mine(
                block_name,
                count,
                task_type="mine"
            )

            return ExecutionResult(
                success=success,
                events=events if events else [],
                is_one_line_primitive=True  # Mining is always primitive
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                events=[],
                errors=[f"Mining error: {str(e)}"]
            )

    def _execute_smelt(self, task_spec: TaskSpec) -> ExecutionResult:
        """
        Execute a smelting task.

        TODO: Implement when smelting support is added to Executor.
        """
        return ExecutionResult(
            success=False,
            events=[],
            errors=["Smelting not yet implemented"]
        )
