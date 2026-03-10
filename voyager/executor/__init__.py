"""
Executor module for direct primitive execution and recursive skill discovery.

This module provides an alternative execution path that:
1. Executes primitives directly via HTTP to mineflayer
2. Recursively discovers and learns crafting dependencies
3. Synthesizes composite skills from successful execution sequences
"""

from .executor import Executor
from .executor_skills import ExecutionStep, SkillDiscoveryTask
from .executor_utils import ExecutorUtils
from .executor_actions import ExecutorActions
from .executor_skills import ExecutorSkills

__all__ = [
    "Executor",
    "ExecutionStep",
    "SkillDiscoveryTask",
    "ExecutorUtils",
    "ExecutorActions",
    "ExecutorSkills",
]
