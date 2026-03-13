"""
HTN Orchestrator - Skill-based execution with validation and decomposition.

This module provides the interface for:
1. Parsing JavaScript skill code from LLM responses
2. Validating skill code against known skills and primitives
3. Decomposing skills into primitive execution stacks
4. Executing skills in mineflayer environment
"""

import re
import json
from voyager.htn.code_analyzer import JavaScriptAnalyzer
from voyager.agents.task_queue import Task, TaskQueue
from voyager.utils import get_logger

logger = get_logger(__name__)


class HTNOrchestrator:
    """
    Orchestrates skill-based task execution with HTN decomposition.

    The orchestrator validates LLM-generated JavaScript skills and decomposes
    them into primitive operations for stack-based execution.
    """

    def __init__(self, env, skill_manager, recorder=None):
        self.env = env
        self.skill_manager = skill_manager
        self.recorder = recorder
        self.analyzer = JavaScriptAnalyzer()

        self.task_queue = TaskQueue()
        self.last_skill_name = None
        self.last_skill_code = None
        self.last_primitives_used = []

        # Primitive function names (mineflayer built-ins)
        # NOTE: craftItem is both a primitive AND decomposable
        self.primitives = {
            'mineBlock', 'smeltItem', 'placeItem',
            'killMob', 'exploreUntil', 'useChest', 'craftItem'
        }

    def parse_llm_response(self, ai_message_content):
        """
        Parse JSON response from LLM containing skill code.

        Expected format:
        {
          "program_code": "async function ...",
          "program_name": "functionName",
          "reasoning": "explanation"
        }
        """
        json_pattern = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
        json_matches = json_pattern.findall(ai_message_content)
        json_str = json_matches[0] if json_matches else ai_message_content

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM did not produce valid JSON: {e}\nResponse: {ai_message_content}")

        required = ["program_code", "program_name"]
        missing = [f for f in required if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        if not isinstance(data['program_code'], str):
            raise ValueError("program_code must be a string")
        if not isinstance(data['program_name'], str):
            raise ValueError("program_name must be a string")

        logger.info(
            f"Parsed skill from LLM: name={data['program_name']} "
            f"code_len={len(data['program_code'])} "
            f"reasoning={data.get('reasoning', 'N/A')[:80]}"
        )
        return data

    def validate_skill_code(self, skill_code, skill_name):
        """
        Validate that skill code only uses known functions.

        Returns:
            tuple: (is_valid, error_message, function_calls)
        """
        logger.debug(f"Validating skill: {skill_name}")

        available_functions = set(self.primitives)
        available_functions.update(self.skill_manager.skills.keys())

        is_valid, error, function_calls = self.analyzer.validate_function_calls(
            skill_code, available_functions
        )

        if not is_valid:
            logger.error(f"Validation failed for '{skill_name}': {error}")
            return False, error, function_calls

        logger.debug(f"Validation passed for '{skill_name}'. Functions used: {function_calls}")
        return True, None, function_calls

    def find_skill_for_output(self, item_name, known_skills):
        for skill_name, skill_data in known_skills.items():
            if 'recipe' in skill_data and skill_data['recipe']:
                if skill_data['recipe'].get('output') == item_name:
                    return skill_name, skill_data
        return None, None

    def decompose_skill_to_primitives(self, skill_code, skill_name, known_skills=None, _stack=None):
        """
        Recursively decompose skill into primitive operations WITH arguments.

        STACK-BASED EXECUTION:
        - Tasks are pushed onto a stack (LIFO)
        - For craftItem calls: push the craft FIRST, then decompose prerequisites
        - Prerequisites execute first (on top of stack)
        - Craft executes last (at bottom of stack) when ingredients are ready

        _stack is a frozenset of skill names currently being decomposed.
        Any skill already in _stack is a cycle and is treated as a primitive leaf
        rather than decomposed further, preventing infinite recursion.
        """
        if known_skills is None:
            known_skills = self.skill_manager.skills

        if _stack is None:
            _stack = frozenset()

        # Cycle guard: if this skill is already being decomposed higher up the
        # call chain, stop here and let the primitive executor handle it directly.
        if skill_name in _stack:
            logger.warning(
                f"Cycle detected: '{skill_name}' is already in the decomposition "
                f"stack {set(_stack)} — treating as a primitive leaf to break recursion"
            )
            return []

        # Add this skill to the immutable stack copy so recursive calls see it.
        _stack = _stack | {skill_name}

        logger.debug(f"Decomposing skill: {skill_name}")

        try:
            function_calls = self.analyzer.extract_function_calls_with_args(skill_code)
        except ValueError as e:
            logger.error(f"Failed to extract function calls from '{skill_name}': {e}")
            return []

        execution_stack = []

        for call_info in function_calls:
            func_name = call_info['function']
            func_args = call_info['args']
            line_num = call_info['line']

            if func_name == 'craftItem':
                item_name = func_args[1].strip("'\"") if len(func_args) > 1 else "unknown"

                craft_task = Task(
                    action="primitive",
                    payload={
                        "function": "craftItem",
                        "args": func_args,
                        "skill": skill_name,
                        "line": line_num
                    },
                    parent=skill_name
                )
                execution_stack.append(craft_task)
                logger.debug(f"  Craft: craftItem({', '.join(func_args)})")

                producing_skill_name, producing_skill_data = self.find_skill_for_output(item_name, known_skills)

                if producing_skill_name and producing_skill_name not in _stack:
                    logger.debug(f"  Decomposing prerequisite skill '{producing_skill_name}' (produces {item_name})")
                    sub_tasks = self.decompose_skill_to_primitives(
                        producing_skill_data['code'], producing_skill_name, known_skills, _stack
                    )
                    execution_stack.extend(sub_tasks)
                elif producing_skill_name and producing_skill_name in _stack:
                    logger.debug(
                        f"  Skipping prerequisite '{producing_skill_name}' — already in decomposition stack (cycle)"
                    )
                else:
                    logger.debug(f"  No stored skill for '{item_name}'; executing craftItem directly via Mineflayer")

            elif func_name in self.primitives:
                execution_stack.append(Task(
                    action="primitive",
                    payload={
                        "function": func_name,
                        "args": func_args,
                        "skill": skill_name,
                        "line": line_num
                    },
                    parent=skill_name
                ))
                logger.debug(f"  Primitive: {func_name}({', '.join(func_args)})")

            elif func_name in known_skills:
                if func_name not in _stack:
                    logger.debug(f"  Decomposing sub-skill: {func_name}")
                    sub_tasks = self.decompose_skill_to_primitives(
                        known_skills[func_name]['code'], func_name, known_skills, _stack
                    )
                    execution_stack.extend(sub_tasks)
                else:
                    logger.debug(
                        f"  Skipping sub-skill '{func_name}' — already in decomposition stack (cycle)"
                    )

            else:
                logger.warning(f"  Unknown function '{func_name}' in skill '{skill_name}' — skipping")

        logger.debug(f"Decomposition complete for '{skill_name}': {len(execution_stack)} primitive tasks")
        return execution_stack

    def _check_execution_success(self, events):
        """
        Check execution success and extract missing prerequisite info.

        Returns:
            tuple: (success: bool, error: dict or None)
        """
        if not events:
            return False, {"type": "no_events", "message": "No events returned"}

        for event_type, event_data in events:
            if event_type == "onError":
                error_msg = event_data.get("onError", "Unknown error")
                logger.error(f"Execution error: {error_msg}")

                missing_items = self._parse_missing_items(error_msg)
                if missing_items:
                    return False, {"type": "missing_prereq", "items": missing_items}
                else:
                    return False, {"type": "execution_error", "message": error_msg}

        return True, None

    def _parse_missing_items(self, error_msg):
        """
        Extract (item_name, quantity) pairs from Mineflayer error messages.

        Returns list of (item_name: str, quantity: int) tuples.
        """
        # Pattern: "I cannot make X because I need: 2 more oak_planks, 1 more stick"
        pattern = r"I cannot make .+ because I need: (.+)"
        match = re.search(pattern, error_msg)
        if match:
            raw_parts = [p.strip().rstrip(',') for p in match.group(1).split(',')]
            result = []
            for part in raw_parts:
                if not part:
                    continue
                qty_match = re.match(r'(\d+)\s+more\s+(\w+)', part)
                if qty_match:
                    result.append((qty_match.group(2), int(qty_match.group(1))))
                else:
                    result.append((part, 1))
            logger.debug(f"Parsed missing items: {result}")
            return result

        # Pattern: "NoItem: item_name" or "MissingIngredient: item_name"
        pattern2 = r"(?:NoItem|MissingIngredient):\s*(\w+)"
        match = re.search(pattern2, error_msg)
        if match:
            item = match.group(1)
            logger.debug(f"Parsed missing item: {item}")
            return [(item, 1)]

        return []

    def queue_tasks_from_skill(self, skill_code, skill_name):
        """Decompose skill and queue primitive tasks for execution."""
        primitive_tasks = self.decompose_skill_to_primitives(skill_code, skill_name)

        initial_size = self.task_queue.size()
        for task in reversed(primitive_tasks):
            self.task_queue.push(task)

        tasks_added = self.task_queue.size() - initial_size
        logger.info(f"Queued {tasks_added} primitive tasks for '{skill_name}'")

        self.last_primitives_used = []
        return tasks_added

    def execute_queued_tasks(self, max_steps=100):
        """
        Execute primitive tasks from the queue one at a time.

        Returns:
            tuple: (success, events_list, error)
        """
        steps = 0
        all_events = []
        executed_primitives = []
        all_programs = self.skill_manager.programs

        logger.info(f"Starting queued task execution (max {max_steps} steps, queue size {self.task_queue.size()})")

        while not self.task_queue.empty() and steps < max_steps:
            task = self.task_queue.pop()
            logger.debug(f"Executing task {steps + 1}: {task}")

            if task.action != "primitive":
                logger.error(f"Non-primitive task in queue: {task.action} — skipping")
                continue

            try:
                primitive_func = task.payload['function']
                primitive_args = task.payload['args']
                parent_skill = task.payload['skill']
                line_num = task.payload['line']

                args_str = ', '.join(primitive_args)
                code = f"await {primitive_func}({args_str});"

                logger.debug(f"Executing: {code}  (from {parent_skill}:{line_num})")
                events = self.env.step(code=code, programs=all_programs)
                all_events.extend(events)

                success, error_info = self._check_execution_success(events)
                if not success:
                    self.task_queue.push(task)

                    if error_info and error_info.get("type") == "missing_prereq":
                        logger.warning(f"Missing prerequisites detected — propagating to Voyager")
                        self.last_primitives_used = executed_primitives
                        return False, all_events, error_info
                    else:
                        error_msg = error_info.get("message", "Unknown error") if error_info else "Execution failed"
                        error_msg = f"Primitive {primitive_func} failed: {error_msg}"
                        self.last_primitives_used = executed_primitives
                        return False, all_events, error_msg

                executed_primitives.append(primitive_func)
                steps += 1
                logger.debug(f"Primitive '{primitive_func}' completed successfully")

            except KeyError as e:
                error_msg = f"Missing expected field in task payload: {e}"
                logger.error(error_msg, exc_info=True)
                self.last_primitives_used = executed_primitives
                return False, all_events, error_msg
            except Exception as e:
                error_msg = f"Error executing primitive {task}: {e}"
                logger.error(error_msg, exc_info=True)
                self.last_primitives_used = executed_primitives
                return False, all_events, error_msg

        success = self.task_queue.empty()
        status = "completed" if success else "incomplete"
        logger.info(f"Queue execution {status} after {steps} steps")

        self.last_primitives_used = executed_primitives
        return success, all_events, None

    def schedule_missing_prereqs(self, missing_items):
        """
        Schedule tasks that satisfy missing prerequisite items.

        For each missing item:
          - If a stored skill produces it, decompose and queue that skill.
          - Otherwise, inject a direct craftItem primitive.  craftItem itself
            handles 2x2/3x3 resolution, table placement, and error reporting,
            so this short-circuits the ActionAgent LLM loop for simple crafted
            intermediates (planks, sticks, etc.).

        Returns list of truly unresolved items — those where even the craftItem
        fallback could not be queued (currently always empty; craftItem failure
        surfaces as an execution error on the next step rather than here).
        """
        logger.info(f"Scheduling prerequisites for: {missing_items}")

        for item_tuple in missing_items:
            # _parse_missing_items now returns (name, qty) tuples
            if isinstance(item_tuple, tuple):
                item_name, qty = item_tuple
            else:
                item_name, qty = item_tuple, 1

            skill_name, skill_data = self.find_skill_for_output(item_name, self.skill_manager.skills)

            if skill_name and skill_data:
                logger.info(f"Found stored skill '{skill_name}' for '{item_name}' — decomposing")
                subtasks = self.decompose_skill_to_primitives(skill_data['code'], skill_name)
                for task in reversed(subtasks):
                    self.task_queue.push(task)
            else:
                # No stored skill — inject a direct craftItem rather than going
                # back through the ActionAgent LLM for a trivially craftable item.
                logger.info(
                    f"No stored skill for '{item_name}' — injecting craftItem(bot, '{item_name}', {qty}) directly"
                )
                self.task_queue.push(Task(
                    action="primitive",
                    payload={
                        "function": "craftItem",
                        "args": ["bot", f"'{item_name}'", str(qty)],
                        "skill": f"_auto_{item_name}",
                        "line": 0,
                    },
                    parent="_auto",
                ))

        # All items were handled (either via skill or craftItem fallback).
        # Actual un-craftable items will surface as execution errors on the next
        # step and escalate naturally to the ActionAgent.
        return []

    def get_execution_summary(self):
        return {
            "skill_name": self.last_skill_name,
            "primitives_used": self.last_primitives_used,
            "queue_size": self.task_queue.size(),
        }

    def reset_queue(self):
        """Clear the task queue."""
        self.task_queue.clear()
        logger.debug("Task queue cleared")
