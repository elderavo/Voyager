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


class HTNOrchestrator:
    """
    Orchestrates skill-based task execution with HTN decomposition.

    The orchestrator validates LLM-generated JavaScript skills and decomposes
    them into primitive operations for stack-based execution.
    """

    def __init__(self, env, skill_manager, recorder=None):
        """
        Initialize the HTN orchestrator.

        Args:
            env: VoyagerEnv instance for executing actions
            skill_manager: SkillManager instance for skill library access
            recorder: Optional event recorder
        """
        self.env = env
        self.skill_manager = skill_manager
        self.recorder = recorder
        self.analyzer = JavaScriptAnalyzer()

        # Execution state
        self.task_queue = TaskQueue()
        self.last_skill_name = None
        self.last_skill_code = None
        self.last_primitives_used = []

        # Primitive function names (mineflayer built-ins)
        # NOTE: craftItem is both a primitive AND decomposable
        # It executes in JS, but also triggers prerequisite decomposition in Python
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

        Args:
            ai_message_content (str): Raw AI message content

        Returns:
            dict: Parsed response with program_code, program_name, reasoning

        Raises:
            ValueError: If JSON parsing fails or required fields missing
        """
        # Try to extract JSON from markdown code blocks
        json_pattern = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
        json_matches = json_pattern.findall(ai_message_content)

        json_str = json_matches[0] if json_matches else ai_message_content

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM did not produce valid JSON: {e}\nResponse: {ai_message_content}")

        # Validate required fields
        required = ["program_code", "program_name"]
        missing = [f for f in required if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Validate types
        if not isinstance(data['program_code'], str):
            raise ValueError("program_code must be a string")
        if not isinstance(data['program_name'], str):
            raise ValueError("program_name must be a string")

        print(f"\033[32m[HTN] Parsed skill from LLM:\033[0m")
        print(f"  Name: {data['program_name']}")
        print(f"  Reasoning: {data.get('reasoning', 'N/A')}")
        print(f"  Code length: {len(data['program_code'])} chars")

        return data

    def validate_skill_code(self, skill_code, skill_name):
        """
        Validate that skill code only uses known functions.

        Args:
            skill_code (str): JavaScript skill code
            skill_name (str): Name of the skill

        Returns:
            tuple: (is_valid, error_message, function_calls)
                is_valid (bool): True if all functions are known
                error_message (str): Error details if invalid, None otherwise
                function_calls (list): All function calls found in code
        """
        print(f"\033[36m[HTN] Validating skill: {skill_name}\033[0m")

        # Build set of available functions
        # Include primitives (includes craftItem)
        available_functions = set(self.primitives)
        # Include all known skills
        available_functions.update(self.skill_manager.skills.keys())

        # Validate function calls
        is_valid, error, function_calls = self.analyzer.validate_function_calls(
            skill_code, available_functions
        )

        if not is_valid:
            print(f"\033[31m[HTN] Validation failed: {error}\033[0m")
            return False, error, function_calls

        print(f"\033[32m[HTN] Validation passed. Functions used: {function_calls}\033[0m")
        return True, None, function_calls

    def find_skill_for_output(self, item_name, known_skills):
        """
        Find a skill that produces the given item.

        Args:
            item_name (str): Item to find (e.g., "stick", "wooden_pickaxe")
            known_skills (dict): Known skills with recipe metadata

        Returns:
            tuple: (skill_name, skill_data) or (None, None) if not found
        """
        for skill_name, skill_data in known_skills.items():
            if 'recipe' in skill_data and skill_data['recipe']:
                if skill_data['recipe'].get('output') == item_name:
                    return skill_name, skill_data
        return None, None

    def decompose_skill_to_primitives(self, skill_code, skill_name, known_skills=None):
        """
        Recursively decompose skill into primitive operations WITH arguments.

        This builds a stack of primitive operations that must be executed
        to accomplish the skill. Skills are decomposed into their constituent
        primitives by recursively analyzing function calls and extracting arguments.

        STACK-BASED EXECUTION:
        - Tasks are pushed onto a stack (LIFO)
        - For craftItem calls: push the craft FIRST, then decompose prerequisites
        - Prerequisites execute first (on top of stack)
        - Craft executes last (at bottom of stack) when ingredients are ready

        Args:
            skill_code (str): JavaScript skill code
            skill_name (str): Name of the skill
            known_skills (dict): Known skills {name: {code, description}}

        Returns:
            list: Ordered list of primitive tasks for execution stack
        """
        if known_skills is None:
            known_skills = self.skill_manager.skills

        print(f"\033[36m[HTN] Decomposing skill: {skill_name}\033[0m")

        try:
            # Extract function calls WITH arguments
            function_calls = self.analyzer.extract_function_calls_with_args(skill_code)
        except ValueError as e:
            print(f"\033[31m[HTN] Failed to extract function calls: {e}\033[0m")
            return []

        execution_stack = []

        for call_info in function_calls:
            func_name = call_info['function']
            func_args = call_info['args']
            line_num = call_info['line']

            # CRAFT ITEM - special handling: both primitive AND decomposable
            if func_name == 'craftItem':
                # Extract item name from arguments
                item_name = func_args[1].strip("'\"") if len(func_args) > 1 else "unknown"

                # STEP 1: Push the craft action onto stack first
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
                print(f"\033[33m[HTN]   Craft: craftItem({', '.join(func_args)})\033[0m")

                # STEP 2: Look for a skill that produces this item
                producing_skill_name, producing_skill_data = self.find_skill_for_output(item_name, known_skills)

                if producing_skill_name:
                    # Found a skill that produces this item - decompose it to get ingredients
                    print(f"\033[33m[HTN]   Decomposing skill: {producing_skill_name} (produces {item_name})\033[0m")
                    sub_skill_code = producing_skill_data['code']
                    sub_tasks = self.decompose_skill_to_primitives(
                        sub_skill_code, producing_skill_name, known_skills
                    )
                    # Add prerequisite tasks (they'll execute before the craft)
                    execution_stack.extend(sub_tasks)
                else:
                    # No stored skill produces this item yet. Treat craftItem as directly executable
                    # so Mineflayer can leverage its own recipe knowledge (bot.findRecipe / bot.recipesFor)
                    print(
                        f"\033[33m[HTN]   No stored skill for {item_name}; executing craftItem directly\033[0m"
                    )

            # TRUE PRIMITIVES (non-craft) - add to stack directly
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
                print(f"\033[32m[HTN]   Primitive: {func_name}({', '.join(func_args)})\033[0m")

            # OTHER SKILL CALL - recursively decompose
            elif func_name in known_skills:
                print(f"\033[33m[HTN]   Decomposing sub-skill: {func_name}\033[0m")
                sub_skill_code = known_skills[func_name]['code']
                sub_tasks = self.decompose_skill_to_primitives(
                    sub_skill_code, func_name, known_skills
                )
                execution_stack.extend(sub_tasks)

            else:
                # Unknown function (should have been caught in validation)
                print(f"\033[31m[HTN]   Warning: Unknown function {func_name} (skipping)\033[0m")

        print(f"\033[36m[HTN] Decomposition complete: {len(execution_stack)} primitive tasks\033[0m")
        return execution_stack

    def _check_execution_success(self, events):
        """
        Check if execution was successful based on events.

        Args:
            events (list): List of execution events

        Returns:
            bool: True if no errors detected
        """
        if not events:
            return False

        # Check for error events
        for event_type, event_data in events:
            if event_type == "onError":
                error_msg = event_data.get("onError", "Unknown error")
                print(f"\033[31m[HTN] Execution error: {error_msg}\033[0m")
                return False

        return True

    def queue_tasks_from_skill(self, skill_code, skill_name):
        """
        Decompose skill and queue primitive tasks for execution.

        This is used when we want to execute a skill as a series of
        primitive operations on the task queue (for future priority-based
        interruption support).

        Args:
            skill_code (str): JavaScript skill code
            skill_name (str): Name of the skill

        Returns:
            int: Number of tasks queued
        """
        # Decompose skill into primitives
        primitive_tasks = self.decompose_skill_to_primitives(skill_code, skill_name)

        # Queue tasks (in reverse order since stack is LIFO)
        initial_size = self.task_queue.size()
        for task in reversed(primitive_tasks):
            self.task_queue.push(task)

        tasks_added = self.task_queue.size() - initial_size
        print(f"\033[36m[HTN] Queued {tasks_added} primitive tasks for {skill_name}\033[0m")

        # Store for reference
        self.last_primitives_used = [t.payload['function'] for t in primitive_tasks]

        return tasks_added

    def execute_queued_tasks(self, max_steps=100):
        """
        Execute primitive tasks from the queue.

        Pops tasks off the stack and executes them as mineflayer primitives.
        This is the ONLY way Python should send tasks to mineflayer -
        one primitive at a time from the queue.

        Args:
            max_steps (int): Maximum number of tasks to execute

        Returns:
            tuple: (success, events_list, error)
                success (bool): True if all tasks completed without errors
                events_list (list): All events from execution
                error (str): Error message if failed, None otherwise
        """
        steps = 0
        all_events = []
        all_programs = self.skill_manager.programs

        print(f"\033[36m[HTN] Starting queued task execution (max {max_steps} steps)\033[0m")
        print(f"\033[36m[HTN] Queue size: {self.task_queue.size()}\033[0m")

        while not self.task_queue.empty() and steps < max_steps:
            task = self.task_queue.pop()
            print(f"\033[36m[HTN] Executing task {steps+1}: {task}\033[0m")

            if task.action != "primitive":
                print(f"\033[31m[HTN] Error: Non-primitive task in queue: {task.action}\033[0m")
                continue

            try:
                primitive_func = task.payload['function']
                primitive_args = task.payload['args']
                parent_skill = task.payload['skill']
                line_num = task.payload['line']

                print(f"\033[32m[HTN] Executing primitive: {primitive_func}({', '.join(primitive_args)}) (from {parent_skill}:{line_num})\033[0m")

                # Generate JavaScript code to execute the primitive with arguments
                args_str = ', '.join(primitive_args)
                code = f"await {primitive_func}({args_str});"

                # Execute in mineflayer environment
                print(f"\033[36m[HTN] Executing code: {code}\033[0m")
                events = self.env.step(code=code, programs=all_programs)
                all_events.extend(events)

                # Check for errors in execution
                if not self._check_execution_success(events):
                    error_msg = f"Primitive {primitive_func} failed during execution"
                    return False, all_events, error_msg

                steps += 1
                print(f"\033[32m[HTN] Primitive {primitive_func} completed successfully\033[0m")

            except KeyError as e:
                error_msg = f"Missing expected field in task payload: {e}"
                print(f"\033[31m[HTN] {error_msg}\033[0m")
                return False, all_events, error_msg
            except Exception as e:
                error_msg = f"Error executing primitive {task}: {e}"
                print(f"\033[31m[HTN] {error_msg}\033[0m")
                return False, all_events, error_msg

        success = self.task_queue.empty()
        print(f"\033[36m[HTN] Queue execution {'completed' if success else 'incomplete'} after {steps} steps\033[0m")

        return success, all_events, None

    def get_execution_summary(self):
        """
        Get summary of last execution.

        Returns:
            dict: Execution summary with skill info and primitives used
        """
        return {
            "skill_name": self.last_skill_name,
            "primitives_used": self.last_primitives_used,
            "queue_size": self.task_queue.size(),
        }

    def reset_queue(self):
        """Clear the task queue."""
        self.task_queue.clear()
        print(f"\033[36m[HTN] Queue cleared\033[0m")
