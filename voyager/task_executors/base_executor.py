"""
Base Task Executor Interface

Defines the interface all task executors must implement.
"""

from voyager.types import ExecutionResult  # noqa: F401 — re-exported for import compatibility


class TaskExecutor:
    """
    Base interface for task executors.

    All executor implementations must inherit from this class
    and implement the execute() method.
    """

    def execute(self, task_spec, plan, world_state) -> ExecutionResult:
        """
        Execute a task.

        Args:
            task_spec: TaskSpec with task details
            plan: ExecutionPlan with routing decision
            world_state: WorldStateTracker with current state

        Returns:
            ExecutionResult with outcome
        """
        raise NotImplementedError("Subclasses must implement execute()")
