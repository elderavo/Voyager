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

        # Cache for available items (populated on first use)
        self._available_items_cache = None

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

        # If skill exists, try executing it first
        if skill_name in self.skill_manager.skills:
            print(f"\033[36mSkill '{skill_name}' already exists — testing it\033[0m")
            success, events = self.execute_skill(skill_name)

            # If old skill still works, use it
            if success:
                return True, [ExecutionStep("skill", skill_name, [], success=True)]
            
            print(f"\033[33mSkill '{skill_name}' is outdated — re-discovering\033[0m")
            # FALL THROUGH to full skill discovery (DEPENDENCY PARSE + SYNTHESIS)

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

    def craft_item(self, item_name: str) -> Tuple[bool, List[Any], str]:
        """
        High-level helper to craft an item WITH QUANTITY SUPPORT.
        Always returns (success, events, normalized_name).
        """

        # =========================
        # 1. Extract quantity
        # =========================
        raw = item_name.strip()
        qty_match = re.match(r"^(\d+)\s+", raw)
        quantity = int(qty_match.group(1)) if qty_match else 1

        # =========================
        # 2. Normalize item name
        # =========================
        normalized = self._normalize_item_name(item_name)

        # Case A: direct match
        if isinstance(normalized, str):
            normalized_name = normalized

        # Case B: suggestion available → auto-accept suggestion
        elif isinstance(normalized, dict) and normalized.get("suggestions"):
            suggestion = normalized["suggestions"][0]
            print(f"[DEBUG] Normalizing '{item_name}' → '{suggestion}' (auto-correct)")
            normalized_name = suggestion

        # Case C: neither match nor suggestions
        else:
            print(f"[DEBUG] Could not normalize '{item_name}' → no usable match")
            return False, [], ""

        # =========================
        # 3. Build skill name
        # (skill ALWAYS crafts exactly 1 unit)
        # =========================
        skill_name = f"craft{self._to_camel_case(normalized_name)}"

        # =========================
        # 4. Ensure 1-unit skill exists
        # =========================
        skill_ok, _ = self.ensure_skill(skill_name, depth=0)
        if not skill_ok:
            print(f"\033[31mFailed to ensure skill for crafting {normalized_name}\033[0m")
            return False, [], normalized_name

        # =========================
        # 5. Quantity execution logic
        # =========================
        all_events = []
        for i in range(quantity):
            success, events = self.execute_skill(skill_name)
            all_events.extend(events)
            if not success:
                print(f"[DEBUG] Failed at batch craft {i+1}/{quantity}")
                return False, all_events, normalized_name

        return True, all_events, normalized_name

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
                message = event.get("onChat", "").lower()
                print(f"\033[36m[DEBUG] Chat message for success check: {message}\033[0m")
                if any(x in message for x in ["no ", "cannot", "can't", "failed", "not enough", "no nearby"]):
                    print(f"\033[31m[DEBUG] Chat indicates failure, returning False\033[0m")
                    return False
                if "i did the recipe" in message or "mined" in message:
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

    def _get_available_items(self) -> List[str]:
        """
        Get list of all available item names from Mineflayer mcData.

        Returns:
            List of valid item names
        """
        if self._available_items_cache is not None:
            return self._available_items_cache

        print(f"\033[36m[DEBUG] Fetching available items from mcData\033[0m")

        # Execute JavaScript to get all item names
        code = """
        const itemNames = Object.keys(bot.registry.itemsByName);
        bot.chat(`ITEMS_LIST:${itemNames.join(',')}`);
        """
        
        events = self.env.step(code=code, programs=self.skill_manager.programs)

        # Parse the chat message containing item names
        for event_type, event in events:
            if event_type == "onChat":
                message = event.get("onChat", "")
                if message.startswith("ITEMS_LIST:"):
                    items_str = message[11:]  # Remove "ITEMS_LIST:" prefix
                    self._available_items_cache = items_str.split(',')
                    print(f"\033[36m[DEBUG] Loaded {len(self._available_items_cache)} items from registry\033[0m")
                    return self._available_items_cache

        print(f"\033[31m[DEBUG] Failed to fetch items from mcData\033[0m")
        return []

    def _normalize_item_name(self, raw_name: str) -> Optional[str]:
        """
        Normalize a curriculum-supplied item name into a canonical Mineflayer item id.

        This version does NOT fetch or dump the entire item registry.
        It offloads matching to Mineflayer side via `_match_item_js()`.
        """

        print(f"\033[36m[DEBUG] Normalizing item name: '{raw_name}'\033[0m")

        # Remove quantity prefixes ("4 planks", "3 oak logs", "a log", "an apple")
        cleaned = re.sub(r'^\d+\s+', '', raw_name.strip())
        cleaned = re.sub(r'^an?\s+', '', cleaned)

        # Lowercase and convert spaces → underscores
        normalized = cleaned.lower().replace(" ", "_")

        print(f"\033[36m[DEBUG] After cleanup → '{normalized}'\033[0m")

        # Offload the fuzzy search to Mineflayer
        match = self._match_item_js(normalized)

        if match:
            print(f"\033[32m[DEBUG] Matched item: {match}\033[0m")
            return match
        
        suggestion = self._fallback_suggest_item(normalized)
        if suggestion:
            return {
                "match": None,
                "suggestions": suggestion,
                "raw": raw_name,
                "cleaned": normalized,
            }

        print(f"[DEBUG] No match and no suggestion for '{normalized}'")
        return {
            "match": None,
            "suggestions": [],
            "raw": raw_name,
            "cleaned": normalized,
        }

    def _fallback_suggest_item(self, normalized: str) -> Optional[List[str]]:
        """
        When Mineflayer cannot match the item, try inference based on inventory.
        E.g., 'wooden_planks' -> 'oak_planks'
            'planks' -> 'oak_planks' if oak_log present
            'log' -> 'oak_log' if oak_log present
        """
        # Use last known inventory
        inv = {}
        try:
            inv = self.env.last_observation["inventory"]
        except Exception:
            pass

        logs = [name for name in inv.keys() if name.endswith("_log")]

        # Heuristic 1: wooden_planks → oak_planks if only oak_log exists
        if normalized in ("planks", "wooden_planks"):
            if logs:
                # pick the only log type you actually have
                base = logs[0].split("_log")[0]
                return [f"{base}_planks"]
            # otherwise generic guess
            return ["oak_planks"]

        # Heuristic 2: "log" when only one log type exists
        if normalized == "log" and logs:
            return [logs[0]]

        return None

    def _match_item_js(self, normalized: str) -> Optional[str]:
        js_query = normalized.replace("'", "\\'")

        # Stricter matching order:
        # 1. exact
        # 2. startsWith
        # 3. underscore-insensitive exact
        # 4. substring
        # 5. underscore-insensitive substring
        code = f"""
            const q = '{js_query}';
            const qplain = q.replace(/_/g, '');

            let best = null;

            for (const name of Object.keys(bot.registry.itemsByName)) {{
                const plain = name.replace(/_/g, '');

                // 1. Exact match
                if (name === q) {{ best = name; break; }}

                // 2. Prefix match ("stick" → "stick", not "sticky_piston")
                if (name.startsWith(q)) {{ best = name; break; }}

                // 3. Underscore-insensitive exact
                if (plain === qplain) {{ best = name; break; }}

                // 4. Substring (only if q > 3 chars)
                if (q.length >= 4 && name.includes(q)) {{
                    best = name;
                    break;
                }}

                // 5. Underscore-insensitive substring
                if (q.length >= 4 && plain.includes(qplain)) {{
                    best = name;
                    break;
                }}
            }}

            bot.chat("MATCH_RESULT:" + (best || "null"));
        """

        events = self.env.step(code=code, programs=self.skill_manager.programs)

        for etype, data in events:
            if etype == "onChat":
                msg = data.get("onChat", "")
                if msg.startswith("MATCH_RESULT:"):
                    item = msg[len("MATCH_RESULT:"):]
                    return None if item == "null" else item

        return None

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
