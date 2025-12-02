"""
Execution Planning Data Models

Defines how a task should be executed without referencing implementation details.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Any


class ExecutionMode(Enum):
    """Execution mode enum."""
    EXISTING_SKILL = "existing_skill"
    EXECUTOR_PRIMITIVE = "executor_primitive"
    HTN_PLAN = "htn_plan"
    ACTION_LLM = "action_llm"


@dataclass
class PrimitiveStep:
    """
    A single primitive execution step for HTN planning.

    This is a placeholder for future HTN integration.
    """
    action: str
    params: dict = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """
    Execution plan for a task.

    Contains routing metadata but no implementation logic.
    The executor uses this plan to decide how to execute the task.

    Examples:
        ExecutionPlan(
            mode=ExecutionMode.EXISTING_SKILL,
            skill_name="craftPlanks",
            save_as_skill=False
        )

        ExecutionPlan(
            mode=ExecutionMode.EXECUTOR_PRIMITIVE,
            save_as_skill=True
        )

        ExecutionPlan(
            mode=ExecutionMode.ACTION_LLM,
            fallback_mode=ExecutionMode.EXECUTOR_PRIMITIVE,
            save_as_skill=True
        )
    """
    mode: ExecutionMode
    skill_name: Optional[str] = None
    plan_steps: Optional[List[PrimitiveStep]] = None
    fallback_mode: Optional[ExecutionMode] = None
    save_as_skill: bool = True  # Whether to save successful execution as a skill

    def __repr__(self) -> str:
        parts = [f"mode={self.mode.value}"]
        if self.skill_name:
            parts.append(f"skill={self.skill_name}")
        if self.fallback_mode:
            parts.append(f"fallback={self.fallback_mode.value}")
        if not self.save_as_skill:
            parts.append("no_save")
        return f"ExecutionPlan({', '.join(parts)})"
