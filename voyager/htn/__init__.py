"""
Voyager HTN (Hierarchical Task Network) Execution System

This module provides a modular task decomposition and execution system as an
alternative to purely generating code from scratch.

Public API:
    - HTNOrchestrator: Main interface for HTN-based execution
    - Task, TaskQueue: Core data structures
    - SkillExecutor: Fact-based task executor

Example:
    from voyager.htn import HTNOrchestrator

    orchestrator = HTNOrchestrator(env, skill_manager)

    intention, primitives, missing = orchestrator.parse_json(ai_message)
    orchestrator.execute_with_queue(intention, primitives, missing)
"""

from voyager.agents.task_queue import Task, TaskQueue
from voyager.agents.skill_executor import SkillExecutor
from voyager.htn.orchestrator import HTNOrchestrator

__all__ = ['Task', 'TaskQueue', 'SkillExecutor', 'HTNOrchestrator']
