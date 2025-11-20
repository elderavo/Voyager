"""
Executor module for direct primitive execution and recursive skill discovery.

This module provides an alternative execution path that:
1. Executes primitives directly via HTTP to mineflayer
2. Recursively discovers and learns crafting dependencies
3. Synthesizes composite skills from successful execution sequences
"""

from .executor import Executor

__all__ = ["Executor"]
