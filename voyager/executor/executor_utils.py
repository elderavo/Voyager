"""
Executor utilities: Helper functions for normalization, matching, and conversions.

This module contains utility functions used by the Executor for:
- Item name normalization and matching
- Case conversions (snake_case <-> CamelCase)
- Item registry queries
- Event parsing
"""

import re
from typing import Optional, List, Tuple, Any, Dict


class ExecutorUtils:
    """Utility functions for the Executor."""

    def __init__(self, env, skill_manager):
        """
        Initialize ExecutorUtils.

        Args:
            env: VoyagerEnv instance for direct code execution
            skill_manager: SkillManager instance for skill storage/retrieval
        """
        self.env = env
        self.skill_manager = skill_manager
        self._available_items_cache = None


    def get_available_items(self) -> List[str]:
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

    def normalize_item_name(self, raw_name: str) -> Optional[str]:
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

        # Try exact match first
        match = self.match_item_js(normalized)
        if match:
            print(f"\033[32m[DEBUG] Matched item: {match}\033[0m")
            return match

        # If no match and ends with 's', try singular form (e.g., "sticks" -> "stick")
        if normalized.endswith('s') and len(normalized) > 1:
            singular = normalized[:-1]
            print(f"\033[36m[DEBUG] Trying singular form: '{singular}'\033[0m")
            match = self.match_item_js(singular)
            if match:
                print(f"\033[32m[DEBUG] Matched singular item: {match}\033[0m")
                return match

        suggestion = self.fallback_suggest_item(normalized)
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

    def fallback_suggest_item(self, normalized: str) -> Optional[List[str]]:
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

    def match_item_js(self, normalized: str) -> Optional[str]:
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

    def extract_item_name(self, skill_name: str) -> str:
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

    def to_camel_case(self, snake_str: str) -> str:
        """
        Convert snake_case to CamelCase.

        Args:
            snake_str: String in snake_case

        Returns:
            camel_case: String in CamelCase
        """
        components = snake_str.split('_')
        return ''.join(x.title() for x in components)

    def parse_dependencies(self, events: List[Tuple[str, Any]]) -> List[str]:
        """
        Parse missing dependencies from event chat messages.

        Looks for messages like:
        "I cannot make stick because I need: 2 more planks"

        Also handles error messages like:
        "No crafting table nearby" -> ["crafting_table"]

        Returns list of item names: ["planks"]
        """
        dependencies = []

        pattern = r"I cannot make .+ because I need: (.*)"

        print(f"\033[36m[DEBUG] Parsing dependencies from {len(events)} events\033[0m")
        # TODO: NEED TO IMPLEMENT QUANTITY-BASED DEPENDENCIES
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

                # Check for "No crafting table nearby" error
                if "No crafting table nearby" in error_msg or "no crafting table nearby" in error_msg:
                    #dependencies.append("crafting_table")
                    print(f"\033[36m[DEBUG] Detected missing crafting_table from error\033[0m")

        print(f"\033[36m[DEBUG] Final dependencies list: {dependencies}\033[0m")
        return dependencies

    def check_execution_success(self, events: List[Tuple[str, Any]]) -> bool:
        """
        Check if execution was successful by examining events.

        Success indicators:
        - No onError events (except recoverable ones like missing dependencies)
        - Chat messages indicate success (e.g., "[CRAFT:DONE]" or "I did the recipe")

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
                # Check for failure indicators
                if any(x in message for x in ["[craft:fail]", "[craft:no_recipe]", "[ct:missing]",
                                               "failed", "i cannot make", "because i need"]):
                    print(f"\033[31m[DEBUG] Chat indicates failure, returning False\033[0m")
                    return False
                # Check for success indicators
                if any(x in message for x in ["[craft:done]", "i did the recipe", "mined",]):
                    print(f"\033[32m[DEBUG] Chat indicates success, returning True\033[0m")
                    return True

        # Default to success if no errors
        print(f"\033[33m[DEBUG] No explicit success/failure indicators, defaulting to True\033[0m")
        return True

