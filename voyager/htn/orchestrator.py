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

    def __init__(self, env, facts, skill_manager, recorder=None):
        """
        Initialize the HTN orchestrator.

        Args:
            env: VoyagerEnv instance for executing actions
            facts: RecipeFacts instance for game mechanics validation
            skill_manager: SkillManager instance for skill library access
            recorder: Optional event recorder
        """
        self.env = env
        self.facts = facts
        self.skill_manager = skill_manager
        self.recorder = recorder
        self.analyzer = JavaScriptAnalyzer()

        # Execution state
        self.task_queue = TaskQueue()
        self.last_skill_name = None
        self.last_skill_code = None
        self.last_primitives_used = []

        # Primitive function names (mineflayer built-ins)
        self.primitives = {
            'mineBlock', 'craftItem', 'smeltItem', 'placeItem',
            'killMob', 'exploreUntil', 'useChest'
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
        available_functions = set(self.primitives)
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

    def decompose_skill_to_primitives(self, skill_code, skill_name, known_skills=None):
        """
        Recursively decompose skill into primitive operations.

        This builds a stack of primitive operations that must be executed
        to accomplish the skill. Skills are decomposed into their constituent
        primitives by recursively analyzing function calls.

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
            function_calls = self.analyzer.extract_function_calls(skill_code)
        except ValueError as e:
            print(f"\033[31m[HTN] Failed to extract function calls: {e}\033[0m")
            return []

        execution_stack = []

        for call in function_calls:
            if call in self.primitives:
                # It's a primitive - add to stack
                execution_stack.append(Task(
                    action="primitive",
                    payload={"function": call, "skill": skill_name},
                    parent=skill_name
                ))
                print(f"\033[32m[HTN]   Primitive: {call}\033[0m")

            elif call in known_skills:
                # It's a known skill - recursively decompose
                print(f"\033[33m[HTN]   Decomposing sub-skill: {call}\033[0m")
                sub_skill_code = known_skills[call]['code']
                sub_tasks = self.decompose_skill_to_primitives(
                    sub_skill_code, call, known_skills
                )
                execution_stack.extend(sub_tasks)

            else:
                # Unknown function (should have been caught in validation)
                print(f"\033[31m[HTN]   Warning: Unknown function {call} (skipping)\033[0m")

        print(f"\033[36m[HTN] Decomposition complete: {len(execution_stack)} primitive tasks\033[0m")
        return execution_stack

    def execute_skill(self, skill_code, skill_name):
        """
        Execute a validated skill in the mineflayer environment.

        Args:
            skill_code (str): JavaScript skill code
            skill_name (str): Name of the skill

        Returns:
            tuple: (success, events, error)
                success (bool): True if execution succeeded
                events (list): List of events from execution
                error (str): Error message if failed, None otherwise
        """
        print(f"\033[32m[HTN] Executing skill: {skill_name}\033[0m")

        try:
            # Get all available programs (skills + primitives)
            all_programs = self.skill_manager.programs

            # Execute the skill code with full program context
            events = self.env.step(code=skill_code, programs=all_programs)

            # Check for execution errors
            success = self._check_execution_success(events)

            if success:
                print(f"\033[32m[HTN] Skill executed successfully: {skill_name}\033[0m")
            else:
                print(f"\033[33m[HTN] Skill execution completed with warnings: {skill_name}\033[0m")

            # Store execution state
            self.last_skill_name = skill_name
            self.last_skill_code = skill_code

            return success, events, None

        except Exception as e:
            error_msg = f"Execution error: {e}"
            print(f"\033[31m[HTN] {error_msg}\033[0m")
            return False, [], error_msg

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
        Execute tasks from the queue (for future use with interruption).

        Currently not used - skills are executed directly. This method
        will be important when we add priority-based task interruption.

        Args:
            max_steps (int): Maximum number of tasks to execute

        Returns:
            tuple: (success, events_list)
                success (bool): True if all tasks completed
                events_list (list): All events from execution
        """
        steps = 0
        all_events = []

        print(f"\033[36m[HTN] Starting queued task execution (max {max_steps} steps)\033[0m")

        while not self.task_queue.empty() and steps < max_steps:
            task = self.task_queue.pop()
            print(f"\033[36m[HTN] Executing task {steps+1}: {task}\033[0m")

            # For now, tasks are just markers - actual execution happens
            # via the full skill code
            steps += 1

        success = self.task_queue.empty()
        print(f"\033[36m[HTN] Queue execution {'completed' if success else 'incomplete'}\033[0m")

        return success, all_events

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
