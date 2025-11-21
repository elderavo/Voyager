"""
Executor skills: Skill discovery, synthesis, and dependency resolution.

This module contains functions for:
- Recursive skill discovery
- Dependency resolution
- Skill synthesis from execution sequences
- Skill registration
"""

from typing import List, Tuple, Optional, Any
from dataclasses import dataclass, field
from .executor_utils import ExecutorUtils


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
    steps_by_depth: dict = field(default_factory=lambda: {})
    status: str = "pending"  # "pending", "in_progress", "completed", "failed"


class ExecutorSkills:
    """Skill discovery and synthesis for the Executor."""

    def __init__(self, env, skill_manager, utils: ExecutorUtils, max_recursion_depth: int = 5):
        """
        Initialize ExecutorSkills.

        Args:
            env: VoyagerEnv instance for direct code execution
            skill_manager: SkillManager instance for skill storage/retrieval
            utils: ExecutorUtils instance for utility functions
            max_recursion_depth: Maximum recursion depth for skill discovery
        """
        self.env = env
        self.skill_manager = skill_manager
        self.utils = utils
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

    def ensure_skill(self, skill_name: str, depth: int = 0, task_type: str = "craft",
                    actions_executor=None) -> Tuple[bool, List[ExecutionStep]]:
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
            task_type: Type of task ("craft" or "mine")
            actions_executor: ExecutorActions instance for executing skills/primitives

        Returns:
            (success: bool, execution_sequence: List[ExecutionStep])
        """
        if actions_executor is None:
            raise ValueError("actions_executor is required for ensure_skill")

        # Check recursion depth
        if depth > self.max_recursion_depth:
            print(f"\033[31mMax recursion depth {self.max_recursion_depth} exceeded for {skill_name}\033[0m")
            return False, []

        # If skill exists, try executing it first
        if skill_name in self.skill_manager.skills:
            print(f"\033[36mSkill '{skill_name}' already exists — testing it\033[0m")
            success, events = actions_executor.execute_skill(skill_name)

            # If old skill still works, use it
            if success:
                return True, [ExecutionStep("skill", skill_name, [], success=True)]

            print(f"\033[33mSkill '{skill_name}' is outdated — re-discovering\033[0m")
            # FALL THROUGH to full skill discovery (DEPENDENCY PARSE + SYNTHESIS)

        print(f"\033[36mDiscovering skill: {skill_name} (depth: {depth})\033[0m")

        # Extract item name from skill name (e.g., "craftSticks" -> "stick")
        item_name = self.utils.extract_item_name(skill_name)

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


        # ============================================================
        # RECURSIVE MULTI-PASS DEPENDENCY RESOLUTION LOOP
        # ============================================================
        # ============================================================
        # RECURSIVE MULTI-PASS DEPENDENCY RESOLUTION LOOP (FIXED)
        # ============================================================
        while True:
            success, events = actions_executor.direct_execute_craft(item_name)

            # --------------------------------------------------------
            # ✔ EARLY EXIT: if craft succeeds, do NOT parse deps.
            # --------------------------------------------------------
            if success:
                print(f"\033[32m✓ Craft succeeded for {item_name}\033[0m")

                # Record step
                step = ExecutionStep("primitive", "craftItem", [item_name, "1"], success=True)
                task.execution_sequence.append(step)
                task.status = "completed"

                # Synthesize final skill
                self.synthesize_skill(skill_name, task.execution_sequence)

                execution_sequence = task.execution_sequence.copy()
                self.task_stack.pop()
                return True, execution_sequence

            # --------------------------------------------------------
            # Craft FAILED → parse missing dependencies
            # --------------------------------------------------------
            dependencies = self.utils.parse_dependencies(events)
            task.missing_dependencies = dependencies

            if not dependencies:
                # True failure: no deps left to resolve
                print(f"\033[31m✗ Failed to craft {item_name}: no further dependencies\033[0m")
                task.status = "failed"
                self.task_stack.pop()
                return False, []

            print(f"\033[33mMissing dependencies for {item_name}: {dependencies}\033[0m")

            # --------------------------------------------------------
            # Resolve ALL dependencies
            # --------------------------------------------------------
            all_deps_ok = True
            for dep in dependencies:
                dep_success = self.ensure_dependency(
                    dep,
                    depth,
                    task_type=task_type,
                    actions_executor=actions_executor
                )
                if not dep_success:
                    print(f"\033[31m✗ Failed to obtain dependency: {dep}\033[0m")
                    all_deps_ok = False
                    break

            if not all_deps_ok:
                task.status = "failed"
                self.task_stack.pop()
                return False, []

            # --------------------------------------------------------
            # After resolving deps, the loop automatically retries
            # --------------------------------------------------------
            print(f"\033[36m[LOOP] Retrying craft for {item_name} after resolving deps...\033[0m")
            # Do NOT break — loop continues until success or true failure




        if success:
            # Simple case: worked on first try
            print(f"\033[32m✓ Direct craft succeeded for {item_name}\033[0m")
            step = ExecutionStep("primitive", "craftItem", [item_name, "1"], success=True)
            task.execution_sequence.append(step)
            task.status = "completed"
            self.task_stack.pop()

            # Synthesize and save skill
            self.synthesize_skill(skill_name, task.execution_sequence)

            return True, task.execution_sequence

        # Parse missing dependencies
        dependencies = self.utils.parse_dependencies(events)
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
            dep_success = self.ensure_dependency(dep, depth, task_type=task_type,
                                                actions_executor=actions_executor)
            if not dep_success:
                print(f"\033[31m✗ Failed to obtain dependency: {dep}\033[0m")
                task.status = "failed"
                self.task_stack.pop()
                return False, []

        # All dependencies satisfied, retry craft
        print(f"\033[36mRetrying craft for {item_name} after resolving dependencies\033[0m")
        success, events = actions_executor.direct_execute_craft(item_name)

        if success:
            print(f"\033[32m✓ Craft succeeded for {item_name} after dependency resolution\033[0m")
            step = ExecutionStep("primitive", "craftItem", [item_name, "1"], success=True)
            task.execution_sequence.append(step)
            task.status = "completed"

            # Synthesize and save the composite skill
            self.synthesize_skill(skill_name, task.execution_sequence)

            execution_sequence = task.execution_sequence.copy()
            self.task_stack.pop()
            return True, execution_sequence
        else:
            print(f"\033[31m✗ Craft failed for {item_name} even after dependency resolution\033[0m")
            task.status = "failed"
            self.task_stack.pop()
            return False, []

    def ensure_dependency(self, dep: str, current_depth: int, task_type: str = "craft",
                         actions_executor=None) -> bool:
        """
        Ensure a single dependency is satisfied.

        Determines if dependency is gatherable or craftable, then handles accordingly.

        Args:
            dep: Dependency item name
            current_depth: Current recursion depth
            task_type: Type of task ("craft" or "mine")
            actions_executor: ExecutorActions instance for executing skills/primitives

        Returns:
            success: bool
        """
        if actions_executor is None:
            raise ValueError("actions_executor is required for ensure_dependency")

        # MINING tasks are forbidden from invoking crafting dependencies
        if task_type == "mine":
            print(f"\033[31m[DEBUG] Mining task cannot auto-craft dependency '{dep}'. Failing only.\033[0m")
            return False

        # Check if it's a gatherable primitive
        if dep in self.gatherable_primitives or dep.endswith("_log") or dep.endswith("_ore"):
            print(f"\033[36mGathering primitive: {dep}\033[0m")
            success, events = actions_executor.direct_execute_gather(dep, count=1)

            if success:
                # Record in current task's execution sequence
                if self.task_stack:
                    step = ExecutionStep("primitive", "mineBlock", [dep, "1"], success=True)
                    self.task_stack[-1].execution_sequence.append(step)

            return success

        # Otherwise, it's craftable - check if we have a skill for it
        dep_skill_name = f"craft{self.utils.to_camel_case(dep)}"

        if dep_skill_name in self.skill_manager.skills:
            # Known skill - execute it
            print(f"\033[36mExecuting known skill for dependency: {dep_skill_name}\033[0m")
            success, events = actions_executor.execute_skill(dep_skill_name)

            if success:
                # NEW: After discovering a new skill, treat that skill as a known SKILL call.
                if dep_skill_name in self.skill_manager.skills:
                    if self.task_stack:
                        self.task_stack[-1].execution_sequence.append(
                            ExecutionStep("skill", dep_skill_name, [], success=True)
                        )
                    return True

            # Fallback (should rarely happen): append raw sub-steps
            if self.task_stack:
                self.task_stack[-1].execution_sequence.extend(sub_steps)

            return True


        # Unknown skill - recurse!
        print(f"\033[36mRecursively discovering skill for: {dep}\033[0m")
        success, sub_steps = self.ensure_skill(dep_skill_name, depth=current_depth + 1,
                                              task_type=task_type, actions_executor=actions_executor)

        if success and self.task_stack:
            # Add sub-steps to current task's execution sequence
            self.task_stack[-1].execution_sequence.extend(sub_steps)

        return success

    def synthesize_skill(self, skill_name: str, execution_sequence: List[ExecutionStep]):
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
            "is_one_line_primitive": False,  # Executor-synthesized skills are NOT primitives
        }

        self.skill_manager.add_new_skill(info)
        print(f"\033[32m✓ Registered skill: {skill_name}\033[0m")
