"""
Shared Agents Module

Centralizes common functionality across all agents:
- World state extraction from Mineflayer events
- Observation formatting for LLM prompts
- Structured execution results
- JSON parsing helpers
- Primitive detection

This eliminates duplicated parsing logic and provides consistent world-state representation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import json
import re


@dataclass
class WorldState:
    """
    Structured representation of the Minecraft world state.

    Extracted from Mineflayer observation events and used by all agents
    for consistent world-state representation.
    """
    biome: str = ""
    time_of_day: str = ""
    voxels: List[str] = field(default_factory=list)
    block_records: List[str] = field(default_factory=list)
    entities: Dict[str, float] = field(default_factory=dict)
    health: float = 0.0
    hunger: float = 0.0
    position: Dict[str, float] = field(default_factory=dict)
    equipment: List[Any] = field(default_factory=list)
    inventory_used: int = 0
    inventory: Dict[str, int] = field(default_factory=dict)
    chest_observation: str = ""
    completed_tasks: List[str] = field(default_factory=list)
    failed_tasks: List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        inv_count = len(self.inventory)
        pos_str = f"({self.position.get('x', 0):.1f}, {self.position.get('y', 0):.1f}, {self.position.get('z', 0):.1f})"
        return f"WorldState(biome={self.biome}, pos={pos_str}, inventory={inv_count} items, health={self.health})"


class WorldStateBuilder:
    """
    Builder for constructing WorldState from Mineflayer events.

    Centralizes event parsing logic that was previously duplicated
    across CurriculumAgent, ActionAgent, and CriticAgent.
    """

    @staticmethod
    def from_events(
        events: List[Tuple[str, Dict]],
        chest_observation: str = "",
        completed_tasks: Optional[List[str]] = None,
        failed_tasks: Optional[List[str]] = None
    ) -> WorldState:
        """
        Extract WorldState from Mineflayer events.

        Args:
            events: List of (event_type, event_data) tuples from Mineflayer
            chest_observation: Formatted chest observation string
            completed_tasks: List of completed tasks (for curriculum context)
            failed_tasks: List of failed tasks (for curriculum context)

        Returns:
            WorldState with extracted information

        Raises:
            ValueError: If no valid observation event is found
        """
        if not events:
            raise ValueError("Cannot build WorldState from empty events list")

        # Find the last observation event
        observe_event = None
        for event_type, event_data in reversed(events):
            if event_type in ("observe", "onSave"):
                observe_event = event_data
                break

        if not observe_event:
            # Try to use the last event
            if len(events) > 0 and len(events[-1]) >= 2:
                observe_event = events[-1][1]
            else:
                raise ValueError("No valid observation event found in events list")

        # Extract status fields
        status = observe_event.get("status", {})

        return WorldState(
            biome=status.get("biome", ""),
            time_of_day=str(status.get("timeOfDay", "")),
            voxels=observe_event.get("voxels", []),
            block_records=observe_event.get("blockRecords", []),
            entities=status.get("entities", {}),
            health=status.get("health", 0.0),
            hunger=status.get("food", 0.0),
            position=status.get("position", {}),
            equipment=status.get("equipment", []),
            inventory_used=status.get("inventoryUsed", 0),
            inventory=observe_event.get("inventory", {}),
            chest_observation=chest_observation,
            completed_tasks=completed_tasks or [],
            failed_tasks=failed_tasks or [],
        )


class ObservationFormatter:
    """
    Formats WorldState into text observations for LLM prompts.

    Provides consistent formatting across all agents while allowing
    agent-specific customization of what information to include.
    """

    @staticmethod
    def format_for_curriculum(
        world: WorldState,
        warm_up_config: Optional[Dict[str, int]] = None,
        qa_context: Optional[str] = None,
        progress: int = 0
    ) -> Dict[str, str]:
        """
        Format world state for curriculum agent.

        Returns a dict of observation components that can be selectively
        included based on warm-up configuration.

        Args:
            world: WorldState to format
            warm_up_config: Dict mapping observation keys to minimum progress thresholds
            qa_context: Optional QA context string
            progress: Current curriculum progress (number of completed tasks)

        Returns:
            Dict mapping observation keys to formatted strings
        """
        observations = {}

        # Context (always included)
        observations["context"] = qa_context or ""

        # Biome
        observations["biome"] = f"Biome: {world.biome}\n\n"

        # Time
        observations["time"] = f"Time: {world.time_of_day}\n\n"

        # Nearby blocks
        if world.voxels:
            observations["other_blocks"] = f"Nearby blocks: {', '.join(world.voxels)}\n\n"
        else:
            observations["other_blocks"] = ""

        # Nearby entities
        if world.entities:
            entities_str = ", ".join([f"{k}: {v:.2f}" for k, v in world.entities.items()])
            observations["nearby_entities"] = f"Nearby entities: {entities_str}\n\n"
        else:
            observations["nearby_entities"] = ""

        # Health
        observations["health"] = f"Health: {world.health:.1f}/20\n\n"

        # Hunger
        observations["hunger"] = f"Hunger: {world.hunger:.1f}/20\n\n"

        # Position
        if world.position:
            pos_str = f"({world.position.get('x', 0):.1f}, {world.position.get('y', 0):.1f}, {world.position.get('z', 0):.1f})"
            observations["position"] = f"Position: {pos_str}\n\n"
        else:
            observations["position"] = ""

        # Equipment
        if world.equipment:
            observations["equipment"] = f"Equipment: {world.equipment}\n\n"
        else:
            observations["equipment"] = ""

        # Chests
        observations["chests"] = world.chest_observation

        # Inventory
        observations["optional_inventory_items"] = ""
        if world.inventory:
            inv_str = ", ".join([f"{k}: {v}" for k, v in world.inventory.items()])
            observations["optional_inventory_items"] = f"Inventory ({world.inventory_used}/36): {inv_str}\n\n"

        return observations

    @staticmethod
    def format_for_action(
        world: WorldState,
        *,
        code: str,
        task: str,
        context: str,
        critique: str,
        include_errors: bool = True,
        include_chat: bool = True,
        chat_messages: Optional[List[str]] = None,
        error_messages: Optional[List[str]] = None
    ) -> str:
        """
        Format world state for action agent.

        Args:
            world: WorldState to format
            code: Previous code executed
            task: Current task
            context: Task context
            critique: Critic feedback
            include_errors: Whether to include error messages
            include_chat: Whether to include chat messages
            chat_messages: List of chat messages to include
            error_messages: List of error messages to include

        Returns:
            Formatted observation string
        """
        parts = []

        # Status
        if world.biome:
            parts.append(f"Biome: {world.biome}")

        parts.append(f"Time: {world.time_of_day}")

        # Nearby information
        if world.voxels:
            parts.append(f"Nearby blocks: {', '.join(world.voxels)}")

        if world.block_records:
            parts.append(f"Block records: {', '.join(world.block_records)}")

        if world.entities:
            entities_str = ", ".join([f"{k}: {v:.2f}" for k, v in world.entities.items()])
            parts.append(f"Nearby entities: {entities_str}")

        # Player state
        parts.append(f"Health: {world.health:.1f}/20")
        parts.append(f"Hunger: {world.hunger:.1f}/20")

        if world.position:
            pos_str = f"({world.position.get('x', 0):.1f}, {world.position.get('y', 0):.1f}, {world.position.get('z', 0):.1f})"
            parts.append(f"Position: {pos_str}")

        # Inventory
        if world.inventory:
            inv_str = ", ".join([f"{k}: {v}" for k, v in world.inventory.items()])
            parts.append(f"Inventory ({world.inventory_used}/36): {inv_str}")

        # Equipment
        if world.equipment:
            parts.append(f"Equipment: {world.equipment}")

        # Chests
        if world.chest_observation:
            parts.append(world.chest_observation.strip())

        # Chat messages
        if include_chat and chat_messages:
            parts.append("Chat log:")
            parts.extend(chat_messages)

        # Error messages
        if include_errors and error_messages:
            parts.append("Execution errors:")
            parts.extend(error_messages)

        # Task and context
        parts.append(f"\nTask: {task}")
        if context:
            parts.append(f"Context: {context}")

        # Previous code and critique
        if code:
            parts.append(f"\nPrevious code:\n```javascript\n{code}\n```")

        if critique:
            parts.append(f"\nCritique: {critique}")

        return "\n\n".join(parts)

    @staticmethod
    def format_for_critic(
        world: WorldState,
        *,
        task: str,
        context: str
    ) -> str:
        """
        Format world state for critic agent.

        Args:
            world: WorldState to format
            task: Current task
            context: Task context

        Returns:
            Formatted observation string
        """
        parts = []

        # Biome and time
        if world.biome:
            parts.append(f"Biome: {world.biome}")
        parts.append(f"Time: {world.time_of_day}")

        # Nearby information
        if world.voxels:
            parts.append(f"Nearby blocks: {', '.join(world.voxels)}")

        if world.entities:
            entities_str = ", ".join([f"{k}: {v:.2f}" for k, v in world.entities.items()])
            parts.append(f"Nearby entities: {entities_str}")

        # Inventory
        if world.inventory:
            inv_str = ", ".join([f"{k}: {v}" for k, v in world.inventory.items()])
            parts.append(f"Inventory ({world.inventory_used}/36): {inv_str}")

        # Chests
        if world.chest_observation:
            parts.append(world.chest_observation.strip())

        # Task
        parts.append(f"\nTask: {task}")
        if context:
            parts.append(f"Context: {context}")

        return "\n\n".join(parts)


@dataclass
class ExecutionResult:
    """
    Unified execution result container.

    Used by executors and Voyager to represent the outcome of task execution
    with consistent structure across all execution modes.
    """
    success: bool
    events: List[Any]
    world_state: Optional[WorldState] = None
    errors: List[str] = field(default_factory=list)
    program_code: Optional[str] = None
    program_name: Optional[str] = None
    is_one_line_primitive: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    conversations: List[Any] = field(default_factory=list)

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        parts = [f"status={status}", f"events={len(self.events)}"]
        if self.program_name:
            parts.append(f"program={self.program_name}")
        if self.is_one_line_primitive:
            parts.append("primitive")
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        return f"ExecutionResult({', '.join(parts)})"


class LLMJsonParser:
    """
    Helper for parsing JSON from LLM outputs with retry logic.

    Centralizes JSON parsing that was previously duplicated across agents.
    """

    @staticmethod
    def parse_json_or_fail(text: str, *, who: str = "agent") -> Dict:
        """
        Parse JSON from text, applying fixes for common LLM issues.

        Args:
            text: Text containing JSON
            who: Agent name for error messages

        Returns:
            Parsed JSON dict

        Raises:
            ValueError: If JSON cannot be parsed
        """
        from voyager.utils.json_utils import fix_and_parse_json

        try:
            return fix_and_parse_json(text)
        except Exception as e:
            raise ValueError(f"[{who}] Failed to parse JSON: {e}\nText: {text[:200]}")

    @staticmethod
    def parse_json_with_retry(
        llm_client,
        system_message,
        human_message,
        *,
        who: str = "agent",
        max_retries: int = 5
    ) -> Dict:
        """
        Parse JSON from LLM with retry logic.

        Args:
            llm_client: LLM client to invoke
            system_message: System message
            human_message: Human message
            who: Agent name for logging
            max_retries: Maximum retry attempts

        Returns:
            Parsed JSON dict

        Raises:
            RuntimeError: If all retries exhausted
        """
        from voyager.utils.json_utils import fix_and_parse_json

        for attempt in range(max_retries):
            try:
                ai_message = llm_client.invoke([system_message, human_message])
                response = fix_and_parse_json(ai_message.content)
                return response
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[{who}] JSON parse failed (attempt {attempt + 1}/{max_retries}): {e}")
                    print(f"[{who}] Retrying...")
                else:
                    print(f"[{who}] All retries exhausted")
                    raise RuntimeError(f"[{who}] Failed to parse JSON after {max_retries} attempts") from e

        raise RuntimeError(f"[{who}] Unexpected exit from retry loop")


class PrimitiveDetector:
    """
    Detects whether a JavaScript function is a one-line primitive.

    Externalizes primitive detection logic that was previously private to ActionAgent.
    """

    @staticmethod
    def is_one_line_primitive(js_ast: Dict, main_function_name: str) -> bool:
        """
        Check if a JavaScript function is a one-line primitive.

        A function is considered a one-line primitive if it consists of
        a single await expression calling a bot method.

        Args:
            js_ast: JavaScript AST from Babel parse
            main_function_name: Name of the main function to check

        Returns:
            True if function is a one-line primitive
        """
        try:
            # Find the main function in the AST
            for node in js_ast.get("program", {}).get("body", []):
                if node.get("type") == "FunctionDeclaration":
                    if node.get("id", {}).get("name") == main_function_name:
                        # Check if body has exactly one statement
                        body = node.get("body", {}).get("body", [])
                        if len(body) != 1:
                            return False

                        statement = body[0]

                        # Check if it's a return statement with await expression
                        if statement.get("type") == "ReturnStatement":
                            argument = statement.get("argument", {})
                            if argument.get("type") == "AwaitExpression":
                                # It's an await expression - likely a primitive
                                return True

                        # Check if it's an expression statement with await
                        if statement.get("type") == "ExpressionStatement":
                            expression = statement.get("expression", {})
                            if expression.get("type") == "AwaitExpression":
                                return True

                        return False

            return False
        except Exception:
            # If parsing fails, assume not primitive
            return False


# Curriculum domain-specific helpers

def suggest_inventory_management_task(
    world: WorldState,
    chest_observation: str
) -> Optional[Tuple[str, str]]:
    """
    Suggest inventory management tasks when inventory is full.

    Extracted from CurriculumAgent to separate domain logic from core agent.

    Args:
        world: Current world state
        chest_observation: Formatted chest observation

    Returns:
        (task, context) tuple if inventory management needed, None otherwise
    """
    if world.inventory_used >= 33:
        if chest_observation == "Chests: None\n\n":
            return (
                "Craft 1 chest",
                "You have so many things to do! You need to craft a chest to store your items."
            )
        else:
            # Parse chest observation to find a chest position
            # Format: "Chest_position: {items}"
            import re
            chest_match = re.search(r"([-\d.]+,\s*[-\d.]+,\s*[-\d.]+):", chest_observation)
            if chest_match:
                chest_position = chest_match.group(1)
                return (
                    f"Deposit useless items into the chest at {chest_position}",
                    f"Your inventory is full, deposit useless items into the chest at {chest_position}."
                )

    return None
