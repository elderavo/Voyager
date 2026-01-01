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
        self.new_skills: List[tuple[str, str]] = []  # (skill_name, code) tuples synthesized during execution

    def ensure_skill(self, skill_name: str, depth: int = 0, task_type: str = "craft",
                actions_executor=None, item_name: str = None) -> Tuple[bool, List[ExecutionStep]]:

        if actions_executor is None:
            raise ValueError("actions_executor is required for ensure_skill")

        if depth > self.max_recursion_depth:
            print(f"[ERR] Max recursion depth exceeded for {skill_name}")
            return False, []

        # -----------------------------------------------------------
        # If known, validate skill BEFORE using it
        # -----------------------------------------------------------
        if skill_name in self.skill_manager.skills:
            ok, _ = actions_executor.execute_skill(skill_name)
            if ok:
                return True, [ExecutionStep("skill", skill_name, [], success=True)]
            else:
                print(f"[WARN] Skill '{skill_name}' failed → rediscovering")
                del self.skill_manager.skills[skill_name]  # clean slate

        # -----------------------------------------------------------
        # Begin new skill discovery context
        # -----------------------------------------------------------
        # Use provided item_name if available, otherwise extract from skill_name
        if item_name is None:
            item_name = self.utils.extract_item_name(skill_name)
        discovery = SkillDiscoveryTask(skill_name, item_name, depth, None)
        discovery.status = "in_progress"
        self.task_stack.append(discovery)

        MAX_RETRIES = 5

        # Scratchpad — accumulates across all retry attempts
        scratch = []

        for attempt in range(MAX_RETRIES):

            # -------------------------------------------------------
            # Attempt direct craft
            # -------------------------------------------------------
            success, events = actions_executor.direct_execute_craft(item_name)

            if success:
                # finalize this attempt's execution sequence
                scratch.append(
                    ExecutionStep("primitive", "craftItem", [item_name, "1"], success=True)
                )

                # merge scratch into discovery context
                discovery.execution_sequence = scratch
                discovery.status = "completed"

                self.task_stack.pop()

                # synthesize skill and track it for later persistence
                name, code = self.synthesize_skill(skill_name, discovery.execution_sequence)
                self.new_skills.append((name, code))

                # Temporarily register in memory so skill can be executed during same session
                self.skill_manager.skills[skill_name] = {"code": code}

                return True, [ExecutionStep("skill", skill_name, [], success=True)]


            # -------------------------------------------------------
            # Missing deps
            # -------------------------------------------------------
            deps = self.utils.parse_dependencies(events)
            if not deps:
                print(f"[ERR] Cannot craft {item_name}: no dependencies to resolve")
                discovery.status = "failed"
                self.task_stack.pop()
                return False, []

            print(f"[INFO] Missing deps for {item_name}: {deps}")

            # -------------------------------------------------------
            # Resolve each dependency with quantities
            # -------------------------------------------------------
            dep_success = True
            for dep_name, quantity in deps.items():
                ok, dep_steps = self.ensure_dependency(
                    dep_name,
                    count=quantity,
                    current_depth=depth + 1,
                    task_type=task_type,
                    actions_executor=actions_executor
                )
                if not ok:
                    dep_success = False
                    break
                scratch.extend(dep_steps)

            if not dep_success:
                discovery.status = "failed"
                self.task_stack.pop()
                return False, []

            # -------------------------------------------------------
            # Retry craft (next iteration)
            # -------------------------------------------------------
            print(f"[LOOP] Retrying craft {item_name} (attempt {attempt+2}/{MAX_RETRIES})")

        # -----------------------------------------------------------
        # All retries failed → AI fallback required
        # -----------------------------------------------------------
        print(f"[FALLBACK] Could not discover skill '{skill_name}' automatically")
        self.task_stack.pop()

        # Stub: this signals the Orchestrator to call ActionBot
        return False, [{"action_bot_fallback": skill_name}]

    def ensure_dependency(self, dep: str, count: int = 1, current_depth: int = 0,
                        task_type: str = "craft", actions_executor=None) -> Tuple[bool, List[ExecutionStep]]:

        if actions_executor is None:
            raise ValueError("actions_executor is required for ensure_dependency")

        # -----------------------------------------------------------
        # Dependencies come from mineflayer chat messages, which are
        # already normalized. Skip normalization to save time.
        # -----------------------------------------------------------
        # (Normalization only needed at curriculum entry point)

        # Mining tasks never auto-craft dependencies
        if task_type == "mine":
            print(f"[ERR] Mining task cannot craft '{dep}'")
            return False, []

        # -----------------------------------------------------------
        # CRAFTABLE
        # -----------------------------------------------------------
        if self.utils.is_craftable(dep):
            skill_name = "craft" + self.utils.to_camel_case(dep)

            # Execute skill 'count' times (each skill crafts 1 item)
            all_steps = []
            for i in range(count):
                # Known skill
                if skill_name in self.skill_manager.skills:
                    ok, _ = actions_executor.execute_skill(skill_name)
                    if ok:
                        all_steps.append(ExecutionStep("skill", skill_name, [], success=True))
                        continue
                    else:
                        print(f"[WARN] Known skill {skill_name} failed → rediscovering")
                        del self.skill_manager.skills[skill_name]

                # Discover new skill - pass item_name directly to avoid extraction
                ok, _ = self.ensure_skill(
                    skill_name,
                    depth=current_depth + 1,
                    task_type="craft",
                    actions_executor=actions_executor,
                    item_name=dep  # Pass the dependency name directly
                )
                if ok:
                    all_steps.append(ExecutionStep("skill", skill_name, [], success=True))
                else:
                    return False, []

            return True, all_steps

        # -----------------------------------------------------------
        # GATHERABLE - gather all at once
        # -----------------------------------------------------------
        blocks = actions_executor.get_source_blocks_for_item(dep)
        if blocks:
            for blk in blocks[:3]:
                ok, _ = actions_executor.direct_execute_gather(blk, count=count)
                if ok:
                    return True, [
                        ExecutionStep("primitive", "mineBlock", [blk, str(count)], success=True)
                    ]
            print(f"[ERR] Failed to gather {count}x '{dep}' via {blocks[:3]}")
            return False, []

        # -----------------------------------------------------------
        # AI fallback
        # -----------------------------------------------------------
        print(f"[FALLBACK] '{dep}' is not craftable or gatherable — requiring ActionBot")
        return False, [{"action_bot_fallback": dep}]


    def synthesize_skill(self, skill_name: str, execution_sequence: List[ExecutionStep]) -> tuple[str, str]:
        """
        Synthesize a JavaScript skill from execution sequence.

        Args:
            skill_name: Name for the new skill
            execution_sequence: List of ExecutionStep objects

        Returns:
            (skill_name, program_code) tuple

        NOTE:
        - execution_sequence is assumed to be CLEAN:
          it should already contain only:
            * local primitives (mineBlock / craftItem)
            * skill calls (step_type == "skill")
          because ensure_dependency/ensure_skill never push sub-skill primitives
          into parent skills.
        - This method ONLY synthesizes code - it does NOT mutate skill_manager
        - The orchestrator (voyager.py) decides when to persist via add_new_skill()
        """
        # Generate JavaScript code
        code_lines = []
        for step in execution_sequence:
            if step.step_type == "primitive":
                if step.name == "mineBlock":
                    code_lines.append(
                        f"  await mineBlock(bot, '{step.args[0]}', {step.args[1]});"
                    )
                elif step.name == "craftItem":
                    code_lines.append(
                        f"  await craftItem(bot, '{step.args[0]}', {step.args[1]});"
                    )
            elif step.step_type == "skill":
                code_lines.append(f"  await {step.name}(bot);")

        code_body = "\n".join(code_lines)
        program_code = f"async function {skill_name}(bot) {{\n{code_body}\n}}"

        print(f"\033[32mSynthesized skill {skill_name}:\033[0m")
        print(f"\033[90m{program_code}\033[0m")

        return (skill_name, program_code)
