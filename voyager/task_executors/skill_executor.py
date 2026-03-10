"""
Skill Task Executor

Executes existing JavaScript skills from the skill library.
"""

from typing import Any
from voyager.types import ExecutionResult
from voyager.trace import Trace
from .base_executor import TaskExecutor
from ..task_spec import TaskSpec


class SkillExecutor(TaskExecutor):
    """
    Executor for existing skills.

    Executes pre-learned JavaScript skills from the skill library.
    """

    def __init__(self, executor: Any):
        """
        Initialize the SkillExecutor.

        Args:
            executor: Existing Executor instance with execute_skill method
        """
        self.executor = executor

    def execute(self, task_spec: TaskSpec, plan, world_state) -> ExecutionResult:
        """
        Execute an existing skill.

        Args:
            task_spec: TaskSpec with task details
            plan: ExecutionPlan with skill_name
            world_state: WorldStateTracker (not used directly)

        Returns:
            ExecutionResult with outcome
        """
        skill_name = plan.skill_name

        if not skill_name:
            return ExecutionResult(
                success=False,
                trace=Trace.from_events([]),
                errors=["No skill name provided in execution plan"]
            )

        try:
            success, events = self.executor.execute_skill(skill_name)

            # Get skill code for result
            program_code = None
            if hasattr(self.executor, 'skill_manager'):
                skills = self.executor.skill_manager.skills
                if skill_name in skills:
                    program_code = skills[skill_name].get("code", None)

            return ExecutionResult(
                success=success,
                trace=Trace.from_events(events if events else []),
                program_code=program_code,
                program_name=skill_name,
                is_one_line_primitive=False  # Skills are not primitives
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                trace=Trace.from_events([]),
                errors=[f"Skill execution error: {str(e)}"]
            )
