"""
Canonical type definitions for Voyager.

All other modules import ExecutionResult and Trace from here.
Trace itself is defined in voyager/trace.py and re-exported here for convenience.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from voyager.trace import Trace  # Trace remains in trace.py


@dataclass
class ExecutionResult:
    """
    Unified result type returned by all executor methods.

    This is the single canonical definition — supersedes the three separate
    definitions that previously existed in:
    - voyager/agents/agents_common.py
    - voyager/task_executors/base_executor.py

    Fields are a superset of all three prior definitions so no information
    is lost.
    """
    success: bool
    trace: Trace
    program_code: Optional[str] = None
    program_name: Optional[str] = None
    is_one_line_primitive: bool = False
    new_skills: List[Tuple[str, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    conversations: List[Any] = field(default_factory=list)

    @property
    def events(self) -> List[Any]:
        """Backward compatibility: existing code using result.events still works."""
        return self.trace.to_list()

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        parts = [f"status={status}", f"events={len(self.trace)}"]
        if self.program_name:
            parts.append(f"program={self.program_name}")
        if self.is_one_line_primitive:
            parts.append("primitive")
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        return f"ExecutionResult({', '.join(parts)})"


__all__ = ["Trace", "ExecutionResult"]
