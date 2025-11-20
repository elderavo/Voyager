"""
Executor: Direct primitive execution and recursive skill discovery.

Handles:
- Direct execution of primitives and known skills
- Recursive dependency resolution for crafting
- Skill synthesis from successful execution sequences
"""

import os
import re
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field

import voyager.utils as U


@dataclass
class ExecutionStep:
    """Records a single execution step (primitive or skill call)."""
    step_type: str  # "primitive", "skill"
    name: str  # e.g., "mineBlock", "craftPlanks"
    args: List[str]  # e.g., ["oak_log", "1"]
    success: bool = False


@dataclass
class SkillDiscoveryTask:
    """Tracks state during recursive skill discovery."""
    skill_name: str
    item_name: str
    depth: int
    parent_task: Optional[str] = None
    execution_sequence: List[ExecutionStep] = field(default_factory=list)
    missing_dependencies: List[str] = field(default_factory=list)
    status: str = "pending"  # "pending", "in_progress", "completed", "failed"


class Executor:
    """
    Executes primitives directly and recursively discovers crafting skills.

    This is a parallel execution path to the existing Action Agent flow.
    It enables:
    1. Direct primitive execution without LLM overhead
    2. Recursive dependency resolution
    3. Automatic skill composition and registration
    """

    def __init__(
        self,
        env,
        skill_manager,
        ckpt_dir: str = "ckpt",
        max_recursion_depth: int = 5,
    ):
        """
        Initialize the Executor.

        Args:
            env: VoyagerEnv instance for direct code execution
            skill_manager: SkillManager instance for skill storage/retrieval
            ckpt_dir: Checkpoint directory for skill storage
            max_recursion_depth: Maximum recursion depth for skill discovery
        """
        self.env = env
        self.skill_manager = skill_manager
        self.ckpt_dir = ckpt_dir
        self.max_recursion_depth = max_recursion_depth

        # State tracking
        self.task_stack: List[SkillDiscoveryTask] = []
        self.current_depth = 0

        # Gatherable primitives (can be obtained via mineBlock)
        self.gatherable_primitives = {
            "oak_log", "spruce_log", "birch_log", "jungle_log", "acacia_log",
            "dark_oak_log", "mangrove_log", "stone", "cobblestone", "dirt",
            "coal_ore", "iron_ore", "copper_ore", "gold_ore", "diamond_ore",
            "lapis_ore", "redstone_ore", "emerald_ore", "coal", "sand", "gravel",
        }

        print(f"\033[36mExecutor initialized with max recursion depth: {max_recursion_depth}\033[0m")

    def execute_skill(self, skill_name: str) -> Tuple[bool, List[Any]]:
        """
        Execute an existing JavaScript skill.

        Args:
            skill_name: Name of the skill to execute (e.g., "craftPlanks")

        Returns:
            (success: bool, events: List)
        """
        if skill_name not in self.skill_manager.skills:
            print(f"\033[31mSkill '{skill_name}' not found in skill library\033[0m")
            return False, []

        print(f"\033[36mExecuting skill: {skill_name}\033[0m")

        # Execute via env.step
        exec_code = f"await {skill_name}(bot);"
        events = self.env.step(
            code=exec_code,
            programs=self.skill_manager.programs
        )

        # Check success (no errors in events)
        success = self._check_execution_success(events)

        return success, events

    def ensure_skill(self, skill_name: str, depth: int = 0) -> Tuple[bool, List[ExecutionStep]]:
        """
        Ensure a skill exists, discovering it recursively if needed.

        If the skill exists in the library, returns immediately.
        If not, attempts to discover it by:
        1. Trying direct execution
        2. Parsing missing dependencies
        3. Recursively ensuring each dependency
        4. Synthesizing and registering the skill

        Args:
            skill_name: Name of skill to ensure (e.g., "craftSticks")
            depth: Current recursion depth

        Returns:
            (success: bool, execution_sequence: List[ExecutionStep])
        """
        # Check recursion depth
        if depth > self.max_recursion_depth:
            print(f"\033[31mMax recursion depth {self.max_recursion_depth} exceeded for {skill_name}\033[0m")
            return False, []

        # If skill already exists, we're done
        if skill_name in self.skill_manager.skills:
            print(f"\033[36mSkill '{skill_name}' already exists\033[0m")
            return True, [ExecutionStep("skill", skill_name, [], success=True)]

        print(f"\033[36mDiscovering skill: {skill_name} (depth: {depth})\033[0m")

        # Extract item name from skill name (e.g., "craftSticks" -> "stick")
        item_name = self._extract_item_name(skill_name)

        # Create discovery task
        task = SkillDiscoveryTask(
            skill_name=skill_name,
            item_name=item_name,
            depth=depth,
            parent_task=self.task_stack[-1].skill_name if self.task_stack else None
        )
        self.task_stack.append(task)
        task.status = "in_progress"

        # Attempt direct execution
        success, events = self._direct_execute_craft(item_name)

        if success:
            # Simple case: worked on first try
            print(f"\033[32m✓ Direct craft succeeded for {item_name}\033[0m")
            step = ExecutionStep("primitive", "craftItem", [item_name, "1"], success=True)
            task.execution_sequence.append(step)
            task.status = "completed"
            self.task_stack.pop()

            # Synthesize and save skill
            self._synthesize_skill(skill_name, task.execution_sequence)

            return True, task.execution_sequence

        # Parse missing dependencies
        dependencies = self._parse_dependencies(events)
        task.missing_dependencies = dependencies

        if not dependencies:
            # Failed but no clear dependencies - can't proceed
            print(f"\033[31m✗ Failed to craft {item_name} with no clear dependencies\033[0m")
            task.status = "failed"
            self.task_stack.pop()
            return False, []

        print(f"\033[33mMissing dependencies for {item_name}: {dependencies}\033[0m")

        # Recursively ensure each dependency
        for dep in dependencies:
            dep_success = self._ensure_dependency(dep, depth)
            if not dep_success:
                print(f"\033[31m✗ Failed to obtain dependency: {dep}\033[0m")
                task.status = "failed"
                self.task_stack.pop()
                return False, []

        # All dependencies satisfied, retry craft
        print(f"\033[36mRetrying craft for {item_name} after resolving dependencies\033[0m")
        success, events = self._direct_execute_craft(item_name)

        if success:
            print(f"\033[32m✓ Craft succeeded for {item_name} after dependency resolution\033[0m")
            step = ExecutionStep("primitive", "craftItem", [item_name, "1"], success=True)
            task.execution_sequence.append(step)
            task.status = "completed"

            # Synthesize and save the composite skill
            self._synthesize_skill(skill_name, task.execution_sequence)

            execution_sequence = task.execution_sequence.copy()
            self.task_stack.pop()
            return True, execution_sequence
        else:
            print(f"\033[31m✗ Craft failed for {item_name} even after dependency resolution\033[0m")
            task.status = "failed"
            self.task_stack.pop()
            return False, []

    def craft_item(self, item_name: str) -> Tuple[bool, List[Any]]:
        """
        High-level helper to craft an item.

        Ensures the crafting skill exists, then executes it.

        Args:
            item_name: Name of item to craft (e.g., "stick", "planks")

        Returns:
            (success: bool, events: List)
        """
        skill_name = f"craft{self._to_camel_case(item_name)}"

        # Ensure skill exists
        success, _ = self.ensure_skill(skill_name, depth=0)

        if not success:
            print(f"\033[31mFailed to ensure skill for crafting {item_name}\033[0m")
            return False, []

        # Execute the skill
        return self.execute_skill(skill_name)

    # ==================== Private Helper Methods ====================

    def _direct_execute_craft(self, item_name: str) -> Tuple[bool, List[Any]]:
        """
        Directly execute craftItem primitive.

        Args:
            item_name: Item to craft

        Returns:
            (success: bool, events: List)
        """
        code = f"await craftItem(bot, '{item_name}', 1);"
        events = self.env.step(code=code, programs=self.skill_manager.programs)
        success = self._check_execution_success(events)
        return success, events

    def _direct_execute_gather(self, item_name: str, count: int = 1) -> Tuple[bool, List[Any]]:
        """
        Directly execute mineBlock primitive.

        Args:
            item_name: Item to gather
            count: Number to gather

        Returns:
            (success: bool, events: List)
        """
        code = f"await mineBlock(bot, '{item_name}', {count});"
        events = self.env.step(code=code, programs=self.skill_manager.programs)
        success = self._check_execution_success(events)
        return success, events

    def _parse_dependencies(self, events: List[Tuple[str, Any]]) -> List[str]:
        """
        Parse missing dependencies from event chat messages.

        Looks for messages like:
        "I cannot make stick because I need: 2 more planks"

        Returns list of item names: ["planks"]
        """
        dependencies = []

        pattern = r"I cannot make .+ because I need: (.*)"

        print(f"\033[36m[DEBUG] Parsing dependencies from {len(events)} events\033[0m")

        for event_type, event in events:
            print(f"\033[36m[DEBUG] Event type: {event_type}\033[0m")
            if event_type == "onChat":
                message = event.get("onChat", "")
                print(f"\033[36m[DEBUG] Chat message: {message}\033[0m")
                match = re.search(pattern, message)
                if match:
                    deps_str = match.group(1)
                    print(f"\033[36m[DEBUG] Matched dependency string: {deps_str}\033[0m")
                    # Parse "2 more planks, 3 more sticks" -> ["planks", "sticks"]
                    for item in deps_str.split(","):
                        # Extract just the item name (remove "2 more" prefix)
                        item_match = re.search(r"more (.+)", item.strip())
                        if item_match:
                            dep_name = item_match.group(1).strip()
                            dependencies.append(dep_name)
                            print(f"\033[36m[DEBUG] Extracted dependency: {dep_name}\033[0m")
            elif event_type == "onError":
                error_msg = event.get("onError", "")
                print(f"\033[31m[DEBUG] Error event: {error_msg}\033[0m")

        print(f"\033[36m[DEBUG] Final dependencies list: {dependencies}\033[0m")
        return dependencies

    def _ensure_dependency(self, dep: str, current_depth: int) -> bool:
        """
        Ensure a single dependency is satisfied.

        Determines if dependency is gatherable or craftable, then handles accordingly.

        Args:
            dep: Dependency item name
            current_depth: Current recursion depth

        Returns:
            success: bool
        """
        # Check if it's a gatherable primitive
        if dep in self.gatherable_primitives or dep.endswith("_log") or dep.endswith("_ore"):
            print(f"\033[36mGathering primitive: {dep}\033[0m")
            success, events = self._direct_execute_gather(dep, count=1)

            if success:
                # Record in current task's execution sequence
                if self.task_stack:
                    step = ExecutionStep("primitive", "mineBlock", [dep, "1"], success=True)
                    self.task_stack[-1].execution_sequence.append(step)

            return success

        # Otherwise, it's craftable - check if we have a skill for it
        dep_skill_name = f"craft{self._to_camel_case(dep)}"

        if dep_skill_name in self.skill_manager.skills:
            # Known skill - execute it
            print(f"\033[36mExecuting known skill for dependency: {dep_skill_name}\033[0m")
            success, events = self.execute_skill(dep_skill_name)

            if success and self.task_stack:
                step = ExecutionStep("skill", dep_skill_name, [], success=True)
                self.task_stack[-1].execution_sequence.append(step)

            return success

        # Unknown skill - recurse!
        print(f"\033[36mRecursively discovering skill for: {dep}\033[0m")
        success, sub_steps = self.ensure_skill(dep_skill_name, depth=current_depth + 1)

        if success and self.task_stack:
            # Add sub-steps to current task's execution sequence
            self.task_stack[-1].execution_sequence.extend(sub_steps)

        return success

    def _check_execution_success(self, events: List[Tuple[str, Any]]) -> bool:
        """
        Check if execution was successful by examining events.

        Success indicators:
        - No onError events
        - Chat messages indicate success (e.g., "I did the recipe")

        Args:
            events: List of (event_type, event_data) tuples

        Returns:
            success: bool
        """
        print(f"\033[36m[DEBUG] Checking execution success for {len(events)} events\033[0m")

        for event_type, event in events:
            print(f"\033[36m[DEBUG] Checking event type: {event_type}\033[0m")
            if event_type == "onError":
                error_msg = event.get("onError", "")
                print(f"\033[31m[DEBUG] Found error event, returning False: {error_msg}\033[0m")
                return False
            if event_type == "onChat":
                message = event.get("onChat", "")
                print(f"\033[36m[DEBUG] Chat message for success check: {message}\033[0m")
                if "I cannot" in message or "failed" in message.lower():
                    print(f"\033[31m[DEBUG] Chat indicates failure, returning False\033[0m")
                    return False
                if "I did the recipe" in message or "mined" in message.lower():
                    print(f"\033[32m[DEBUG] Chat indicates success, returning True\033[0m")
                    return True

        # Default to success if no errors
        print(f"\033[33m[DEBUG] No explicit success/failure indicators, defaulting to True\033[0m")
        return True

    def _synthesize_skill(self, skill_name: str, execution_sequence: List[ExecutionStep]):
        """
        Synthesize a JavaScript skill from execution sequence and register it.

        Args:
            skill_name: Name for the new skill
            execution_sequence: List of ExecutionStep objects
        """
        # Generate JavaScript code
        code_lines = []
        for step in execution_sequence:
            if step.step_type == "primitive":
                if step.name == "mineBlock":
                    code_lines.append(f"  await mineBlock(bot, '{step.args[0]}', {step.args[1]});")
                elif step.name == "craftItem":
                    code_lines.append(f"  await craftItem(bot, '{step.args[0]}', {step.args[1]});")
            elif step.step_type == "skill":
                code_lines.append(f"  await {step.name}(bot);")

        code_body = "\n".join(code_lines)
        program_code = f"async function {skill_name}(bot) {{\n{code_body}\n}}"

        print(f"\033[32mSynthesized skill {skill_name}:\033[0m")
        print(f"\033[90m{program_code}\033[0m")

        # Register with skill manager
        info = {
            "task": f"Synthesized by Executor: {skill_name}",
            "program_name": skill_name,
            "program_code": program_code,
        }

        self.skill_manager.add_new_skill(info)
        print(f"\033[32m✓ Registered skill: {skill_name}\033[0m")

    def _extract_item_name(self, skill_name: str) -> str:
        """
        Extract item name from skill name.

        Examples:
            "craftSticks" -> "stick"
            "craftWoodenPickaxe" -> "wooden_pickaxe"

        Args:
            skill_name: Skill name in camelCase

        Returns:
            item_name: Item name in snake_case
        """
        print(f"\033[36m[DEBUG] Extracting item name from skill: {skill_name}\033[0m")

        # Remove "craft" prefix
        if skill_name.startswith("craft"):
            name = skill_name[5:]  # Remove "craft"
        else:
            name = skill_name

        print(f"\033[36m[DEBUG] After removing 'craft' prefix: {name}\033[0m")

        # Convert from CamelCase to snake_case
        # But first handle the special case of lowercase first letter
        name = name[0].lower() + name[1:] if name else name

        # Insert underscores before capitals
        result = re.sub(r'([A-Z])', r'_\1', name).lower()

        print(f"\033[36m[DEBUG] Converted to snake_case: {result}\033[0m")

        # Special handling: "sticks" -> "stick", "planks" -> "oak_planks" (guess)
        # For now, just return as-is - mineflayer should handle plurals
        return result

    def _to_camel_case(self, snake_str: str) -> str:
        """
        Convert snake_case to CamelCase.

        Args:
            snake_str: String in snake_case

        Returns:
            camel_case: String in CamelCase
        """
        components = snake_str.split('_')
        return ''.join(x.title() for x in components)
