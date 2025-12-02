"""
Task Classification Module

Converts raw task strings into structured TaskSpec objects.
Provides stable, testable parsing to replace string slicing logic.
"""

import re
from typing import Dict, Optional, Any
from .task_spec import TaskSpec, TaskType


class TaskClassifier:
    """
    Classifies raw task strings into structured TaskSpec objects.

    Responsibilities:
    - Normalize task strings (lowercase, trim punctuation, map synonyms)
    - Extract task type (craft, mine, gather, etc.)
    - Extract parameters (item/block names, counts)
    - Return complete TaskSpec
    """

    # Text number mapping
    TEXT_NUMBERS = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
        "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
        "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
        "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
        "ninety": 90, "hundred": 100,
        "a": 1, "an": 1,
    }

    # Action synonyms mapping
    ACTION_SYNONYMS = {
        # Crafting
        "craft": TaskType.CRAFT,
        "make": TaskType.CRAFT,
        "create": TaskType.CRAFT,
        "build": TaskType.CRAFT,  # Note: BUILD could be separate for placement tasks

        # Mining
        "mine": TaskType.MINE,
        "dig": TaskType.MINE,
        "extract": TaskType.MINE,

        # Gathering
        "obtain": TaskType.GATHER,
        "gather": TaskType.GATHER,
        "collect": TaskType.GATHER,
        "get": TaskType.GATHER,
        "find": TaskType.GATHER,

        # Smelting
        "smelt": TaskType.SMELT,
        "cook": TaskType.SMELT,
        "furnace": TaskType.SMELT,

        # Exploration
        "explore": TaskType.EXPLORE,
        "travel": TaskType.EXPLORE,
        "go": TaskType.EXPLORE,
    }

    def __init__(self):
        """Initialize the TaskClassifier."""
        pass

    def classify(
        self,
        raw_task: str,
        context: str = "",
        world_state: Optional[Any] = None
    ) -> TaskSpec:
        """
        Classify a raw task string into a structured TaskSpec.

        Args:
            raw_task: Raw task string (e.g., "Craft 4 oak planks")
            context: Additional context about the task
            world_state: Optional world state for context-aware classification

        Returns:
            TaskSpec with normalized representation and extracted parameters
        """
        # Normalize the task string
        normalized = self._normalize_text(raw_task)

        # Extract task type and parameters
        task_type, params = self._extract_task_info(normalized, raw_task)

        # Determine origin (default to curriculum if not specified)
        origin = "curriculum"  # Can be enhanced based on context

        return TaskSpec(
            raw_text=raw_task,
            normalized=normalized,
            type=task_type,
            params=params,
            origin=origin,
            metadata={"context": context}
        )

    def _normalize_text(self, text: str) -> str:
        """
        Normalize task text.

        - Lowercase
        - Trim extra whitespace
        - Remove trailing punctuation
        """
        normalized = text.lower().strip()
        # Remove trailing punctuation
        normalized = re.sub(r'[.!?]+$', '', normalized)
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    def _extract_task_info(self, normalized: str, raw_text: str) -> tuple[TaskType, Dict]:
        """
        Extract task type and parameters from normalized text.

        Returns:
            (TaskType, params_dict)
        """
        # Try to match action verb at the start
        words = normalized.split()
        if not words:
            return TaskType.UNKNOWN, {}

        action_verb = words[0]
        task_type = self.ACTION_SYNONYMS.get(action_verb, TaskType.UNKNOWN)

        # Extract count and item/block name
        count, item_name = self._extract_count_and_name(normalized, words)

        # Build params dict based on task type
        if task_type == TaskType.CRAFT:
            params = {"item": item_name, "count": count}
        elif task_type == TaskType.MINE:
            params = {"block": item_name, "count": count}
        elif task_type == TaskType.GATHER:
            # Gather could be mining or collecting - treat as MINE for now
            task_type = TaskType.MINE
            params = {"block": item_name, "count": count}
        elif task_type == TaskType.SMELT:
            params = {"item": item_name, "count": count}
        else:
            params = {"target": item_name, "count": count}

        return task_type, params

    def _extract_count_and_name(self, normalized: str, words: list) -> tuple[int, str]:
        """
        Extract count and item/block name from the task text.

        Handles:
        - "craft 4 oak planks" -> (4, "oak planks")
        - "craft oak planks" -> (1, "oak planks")
        - "mine three cobblestone" -> (3, "cobblestone")
        - "craft a crafting table" -> (1, "crafting table")
        """
        # Pattern: <action> [count] <item_name>
        # Remove action verb
        remaining = words[1:] if len(words) > 1 else []

        if not remaining:
            return 1, ""

        count = 1
        item_words = []

        # Check first word for count
        first_word = remaining[0]

        # Try parsing as number
        if first_word.isdigit():
            count = int(first_word)
            item_words = remaining[1:]
        # Try parsing as text number
        elif first_word in self.TEXT_NUMBERS:
            count = self.TEXT_NUMBERS[first_word]
            item_words = remaining[1:]
        # No count specified
        else:
            item_words = remaining

        # Join remaining words as item name
        item_name = " ".join(item_words).strip()

        # Clean up common minecraft item name issues
        item_name = item_name.replace(" log", "_log")
        item_name = item_name.replace(" ", "_")

        return count, item_name

    def parse_task_legacy(self, task: str) -> tuple[str, str, int]:
        """
        Legacy parsing method for backward compatibility.

        Returns:
            (task_type, item_name, count)
        """
        spec = self.classify(task)

        task_type = spec.type.value
        item_name = spec.params.get("item") or spec.params.get("block") or spec.params.get("target", "")
        count = spec.params.get("count", 1)

        return task_type, item_name, count
