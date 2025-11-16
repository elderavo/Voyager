"""
HTN Orchestrator - Main interface for HTN-based execution.

This module provides a clean API for HTN execution, decoupling it from
the main Voyager orchestration logic.
"""

import re
import json
import copy
from voyager.agents.task_queue import Task, TaskQueue
from voyager.agents.skill_executor import SkillExecutor


class HTNOrchestrator:
    """
    Orchestrates HTN-based task execution.

    This class provides a modular interface for:
    1. Parsing JSON responses from LLM
    2. Managing task queue
    3. Executing tasks with fact validation
    4. Maintaining execution state
    """

    def __init__(self, env, facts, recorder=None, skill_programs=""):
        """
        Initialize the HTN orchestrator.

        Args:
            env: VoyagerEnv instance for executing actions
            facts: RecipeFacts instance for game mechanics validation
            recorder: Optional event recorder
            skill_programs: String containing all skill/primitive function definitions
        """
        self.env = env
        self.facts = facts
        self.recorder = recorder
        self.skill_programs = skill_programs
        self.task_queue = TaskQueue()
        self.executor = SkillExecutor(env.bot if hasattr(env, 'bot') else None, facts)
        self.last_intention = None
        self.last_primitives = []
        self.last_dependencies = []

        # Decomposition cache: intention -> [list of primitive tasks]
        self.decomposition_cache = {}

        # Generated code accumulator
        self.generated_code = []

    def parse_json_response(self, ai_message_content):
        """
        Parse JSON response from LLM.

        Args:
            ai_message_content (str): Raw AI message content

        Returns:
            tuple: (intention, primitive_actions, missing_dependencies)

        Raises:
            ValueError: If JSON parsing fails
        """
        response = ai_message_content

        # Try to extract JSON from markdown code blocks
        json_pattern = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
        json_matches = json_pattern.findall(response)

        if json_matches:
            json_str = json_matches[0]
        else:
            json_str = response

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM did not produce valid JSON: {e}\nResponse: {response}")

        intention = data.get("intention", "")
        primitive_actions = data.get("primitive_actions", [])
        missing_dependencies = data.get("missing", [])
        notes = data.get("notes", "")

        if not intention:
            raise ValueError("JSON response missing 'intention' field")

        print(f"\033[32m[HTN] Parsed Action****")
        print(f"  Intention: {intention}")
        print(f"  Primitive Actions: {primitive_actions}")
        print(f"  Missing Dependencies: {missing_dependencies}")
        if notes:
            print(f"  Notes: {notes}")
        print(f"\033[0m")

        # Store for later reference
        self.last_intention = intention
        self.last_primitives = primitive_actions
        self.last_dependencies = missing_dependencies

        return intention, primitive_actions, missing_dependencies

    def queue_tasks(self, intention, primitive_actions, missing_dependencies):
        """
        Queue tasks based on LLM response.

        Args:
            intention (str): High-level goal
            primitive_actions (list): Actions executable now
            missing_dependencies (list): Dependencies to resolve

        Returns:
            int: Number of tasks queued
        """
        initial_size = self.task_queue.size()

        # Queue dependencies first (will be resolved in order)
        for dep in missing_dependencies:
            self.task_queue.push(Task("dependency", dep, parent=intention))

        # Then queue primitive actions
        for pa in primitive_actions:
            if isinstance(pa, dict):
                action_type = pa.get("type", "unknown")
                payload = pa.get("payload", None)
                self.task_queue.push(Task(action_type, payload, parent=intention))
            elif isinstance(pa, str):
                # Parse string format like "mine:oak_log"
                if ":" in pa:
                    action_type, payload = pa.split(":", 1)
                    self.task_queue.push(Task(action_type, payload, parent=intention))
                else:
                    self.task_queue.push(Task(pa, None, parent=intention))
            else:
                self.task_queue.push(Task(str(pa), None, parent=intention))

        tasks_added = self.task_queue.size() - initial_size
        print(f"\033[36m[HTN] Queued {tasks_added} tasks (queue size: {self.task_queue.size()})\033[0m")
        return tasks_added

    def execute_queue(self, max_steps=100):
        """
        Execute tasks from the queue.

        Args:
            max_steps (int): Maximum number of tasks to execute

        Returns:
            tuple: (success, events, generated_code)
                success (bool): True if queue was emptied successfully
                events (list): List of events from execution
                generated_code (str): All generated code concatenated
        """
        steps = 0
        all_events = []
        self.generated_code = []  # Reset code accumulator

        while not self.task_queue.empty() and steps < max_steps:
            # Debug: Print current queue state
            print(f"\033[35m[HTN DEBUG] Current queue: {self.task_queue.queue}\033[0m")

            task = self.task_queue.pop()
            print(f"\033[36m[HTN] Executing task {steps+1}: {task}\033[0m")

            try:
                # Execute task and get missing dependencies
                missing = self.executor.execute(task)

                if missing:
                    print(f"\033[33m[HTN] Task requires {len(missing)} dependencies\033[0m")
                    # Push original task back first (so it executes AFTER dependencies)
                    self.task_queue.push(task)
                    # Then push dependencies (so they execute BEFORE original task)
                    self.task_queue.push_many(missing)
                    print(f"\033[33m[HTN] Re-queued original task after dependencies\033[0m")
                    # Don't increment steps - we didn't actually execute anything
                    continue

                # Generate mineflayer code for this primitive action
                code = self._generate_code_for_task(task)

                if code:
                    self.generated_code.append(code)
                    print(f"\033[32m[HTN] Executing mineflayer code for {task}\033[0m")
                    events = self.env.step(code, programs=self.skill_programs)
                    all_events.extend(events)
                else:
                    print(f"\033[33m[HTN] No code generated, skipping execution\033[0m")

                steps += 1

            except Exception as e:
                print(f"\033[31m[HTN] Task execution error: {e}\033[0m")
                # Continue to next task instead of crashing
                steps += 1
                continue

        success = self.task_queue.empty()
        print(f"\033[36m[HTN] Queue execution {'completed' if success else 'incomplete'} after {steps} steps\033[0m")

        combined_code = "\n".join(self.generated_code)
        return success, all_events, combined_code

    def _generate_code_for_task(self, task):
        """
        Generate mineflayer JavaScript code for a primitive task.

        Args:
            task (Task): Task to generate code for

        Returns:
            str: JavaScript code to execute, or None if no code needed
        """
        action = task.action
        payload = task.payload

        if action == "mine" or action == "gather":
            # Generate code to mine a block
            block_name = payload
            return f"""
// Mine {block_name}
const {block_name.replace('_', '')}Block = bot.findBlock({{
    matching: mcData.blocksByName.{block_name}.id,
    maxDistance: 32
}});
if ({block_name.replace('_', '')}Block) {{
    await mineBlock(bot, "{block_name}", 1);
}} else {{
    bot.chat("Cannot find {block_name} nearby");
}}
"""
        elif action == "craft":
            item_name = payload
            return f"""
// Craft {item_name}
await craftItem(bot, "{item_name}", 1);
"""
        elif action == "smelt":
            item_name = payload
            return f"""
// Smelt {item_name}
await smeltItem(bot, "{item_name}", 1);
"""
        else:
            print(f"\033[33m[HTN] No code generation for action: {action}\033[0m")
            return None

    def execute_with_queue(self, intention, primitive_actions, missing_dependencies, max_steps=100):
        """
        Convenience method: queue tasks and execute.

        Args:
            intention (str): High-level goal
            primitive_actions (list): Actions executable now
            missing_dependencies (list): Dependencies to resolve
            max_steps (int): Maximum steps to execute

        Returns:
            tuple: (success, events)
        """
        self.queue_tasks(intention, primitive_actions, missing_dependencies)
        return self.execute_queue(max_steps)

    def get_execution_summary(self):
        """
        Get summary of last execution.

        Returns:
            dict: Execution summary with intention, primitives, dependencies
        """
        return {
            "intention": self.last_intention,
            "primitive_actions": self.last_primitives,
            "missing_dependencies": self.last_dependencies,
            "queue_size": self.task_queue.size(),
        }

    def reset_queue(self):
        """
        Clear the task queue.
        """
        self.task_queue.clear()
        print(f"\033[36m[HTN] Queue cleared\033[0m")
