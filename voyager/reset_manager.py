"""
Reset Management Module

Standardizes environment reset semantics.
Provides consistent reset behavior across different scenarios.
"""

from enum import Enum
from typing import Any, Dict, Optional


class ResetMode(Enum):
    """Reset mode enum."""
    HARD_CLEAR = "hard_clear"  # Clear inventory and state
    HARD_KEEP_INV = "hard_keep_inv"  # Reset environment but keep inventory
    SOFT = "soft"  # Soft refresh, keep everything
    NONE = "none"  # No reset


class ResetManager:
    """
    Manages environment resets.

    Responsibilities:
    - Standardize reset semantics
    - Handle initial vs. between-task resets
    - Manage inventory preservation
    - Error recovery resets
    """

    def __init__(self, env: Any, env_wait_ticks: int = 40):
        """
        Initialize the ResetManager.

        Args:
            env: VoyagerEnv instance
            env_wait_ticks: Ticks to wait during reset
        """
        self.env = env
        self.env_wait_ticks = env_wait_ticks

    def apply_initial_reset(
        self,
        world_state: Any,
        resume: bool = False
    ) -> list:
        """
        Apply initial reset at the start of learning.

        Args:
            world_state: WorldStateTracker to update
            resume: If True, keep inventory (soft). If False, clear inventory (hard).

        Returns:
            Events from reset
        """
        if resume:
            # Keep inventory - soft reset
            print(f"\033[36m[ResetManager] Initial reset: SOFT (keeping inventory)\033[0m")
            events = self._soft_reset()
        else:
            # Clear inventory - hard reset
            print(f"\033[36m[ResetManager] Initial reset: HARD (clearing inventory)\033[0m")
            events = self._hard_reset_clear()

        # Update world state
        world_state.update_from_events(events)

        return events

    def soft_refresh(
        self,
        world_state: Any,
        result: Optional[Any] = None
    ) -> list:
        """
        Soft refresh between tasks.

        Just gets fresh state without restarting server or clearing anything.

        Args:
            world_state: WorldStateTracker to update
            result: Optional ExecutionResult (not used currently)

        Returns:
            Events from refresh
        """
        print(f"\033[36m[ResetManager] Soft refresh (no restart)\033[0m")
        events = self.env.step("")

        # Update world state
        world_state.update_from_events(events)

        return events

    def handle_error_reset(
        self,
        world_state: Any,
        preserve_inventory: bool = True
    ) -> list:
        """
        Handle reset after error.

        Args:
            world_state: WorldStateTracker to update
            preserve_inventory: Whether to preserve inventory

        Returns:
            Events from reset
        """
        if preserve_inventory:
            print(f"\033[36m[ResetManager] Error recovery: SOFT (keeping inventory)\033[0m")
            events = self._soft_reset()
        else:
            print(f"\033[36m[ResetManager] Error recovery: HARD (clearing inventory)\033[0m")
            events = self._hard_reset_clear()

        # Update world state
        world_state.update_from_events(events)

        return events

    def _hard_reset_clear(self) -> list:
        """
        Hard reset with inventory clear.

        Returns:
            Events from reset
        """
        return self.env.reset(
            options={
                "mode": "hard",
                "wait_ticks": self.env_wait_ticks,
                # Explicitly do NOT pass inventory - let it default to {}
            }
        )

    def _hard_reset_keep_inv(self, inventory: Dict) -> list:
        """
        Hard reset keeping inventory.

        Args:
            inventory: Inventory to preserve

        Returns:
            Events from reset
        """
        return self.env.reset(
            options={
                "mode": "hard",
                "wait_ticks": self.env_wait_ticks,
                "inventory": inventory,
            }
        )

    def _soft_reset(self) -> list:
        """
        Soft reset (minimal disruption).

        Returns:
            Events from reset
        """
        return self.env.reset(
            options={
                "mode": "soft",
                "wait_ticks": self.env_wait_ticks,
            }
        )

    def apply_reset_mode(
        self,
        mode: ResetMode,
        world_state: Any,
        inventory: Optional[Dict] = None
    ) -> list:
        """
        Apply a specific reset mode.

        Args:
            mode: ResetMode to apply
            world_state: WorldStateTracker to update
            inventory: Optional inventory to preserve (for HARD_KEEP_INV)

        Returns:
            Events from reset
        """
        if mode == ResetMode.HARD_CLEAR:
            events = self._hard_reset_clear()
        elif mode == ResetMode.HARD_KEEP_INV:
            inv = inventory if inventory else world_state.get_inventory()
            events = self._hard_reset_keep_inv(inv)
        elif mode == ResetMode.SOFT:
            events = self._soft_reset()
        elif mode == ResetMode.NONE:
            events = self.env.step("")
        else:
            raise ValueError(f"Unknown reset mode: {mode}")

        # Update world state
        world_state.update_from_events(events)

        return events
