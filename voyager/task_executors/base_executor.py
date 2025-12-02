"""
Base Task Executor Interface

Defines the interface all task executors must implement.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass
class ExecutionResult:
    """
    Result from task execution.

    Contains all information needed to:
    - Determine success
    - Update world state
    - Save as skill
    - Update curriculum
    """
    success: bool
    events: List[Any]  # Mineflayer events
    program_code: Optional[str] = None
    program_name: Optional[str] = None
    is_one_line_primitive: bool = False
    errors: Optional[List[str]] = None
    conversations: List[Any] = field(default_factory=list)  # For LLM executors

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        parts = [f"status={status}", f"events={len(self.events)}"]
        if self.program_name:
            parts.append(f"skill={self.program_name}")
        if self.is_one_line_primitive:
            parts.append("primitive")
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        return f"ExecutionResult({', '.join(parts)})"


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
