"""
Task Specification Data Models

Defines structured task representations to replace free-form string parsing.
All downstream logic relies on TaskSpec instead of raw strings.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class TaskType(Enum):
    """Task classification enum."""
    CRAFT = "craft"
    MINE = "mine"
    GATHER = "gather"
    SMELT = "smelt"
    BUILD = "build"
    EXPLORE = "explore"
    UNKNOWN = "unknown"


@dataclass
class TaskSpec:
    """
    Structured task representation.

    All task processing should use TaskSpec instead of raw strings.
    This enables:
    - Consistent parsing
    - Type safety
    - Testability
    - Clear routing decisions

    Examples:
        TaskSpec(
            raw_text="Craft 4 oak planks",
            normalized="craft oak planks",
            type=TaskType.CRAFT,
            params={"item": "oak_planks", "count": 4},
            origin="curriculum"
        )

        TaskSpec(
            raw_text="Mine 8 cobblestone",
            normalized="mine cobblestone",
            type=TaskType.MINE,
            params={"block": "cobblestone", "count": 8},
            origin="manual"
        )
    """
    raw_text: str
    normalized: str
    type: TaskType
    params: Dict
    origin: str  # "curriculum" | "manual" | "htn_subtask"
    metadata: Dict = field(default_factory=dict)  # Optional difficulty, priority, etc.

    def __repr__(self) -> str:
        return f"TaskSpec(type={self.type.value}, params={self.params}, origin={self.origin})"
