"""
World State Management Module

Maintains consistent world state across iterations.
Provides safe accessors to replace direct event indexing.
"""

from typing import List, Dict, Tuple, Optional, Any


class WorldStateTracker:
    """
    Tracks and provides safe access to world state.

    Responsibilities:
    - Parse Mineflayer events into canonical fields
    - Provide safe accessors (no IndexError)
    - Replace direct event indexing like events[-1][1]["inventory"]
    - Maintain state consistency across task iterations
    """

    def __init__(self):
        """Initialize the WorldStateTracker."""
        self._last_events: List[Tuple[str, Dict]] = []
        self._inventory: Dict[str, int] = {}
        self._position: Optional[Dict[str, float]] = None
        self._nearby_chests: Dict[str, Any] = {}
        self._voxels: List[Any] = []
        self._health: Optional[float] = None
        self._hunger: Optional[float] = None
        self._equipment: List[Any] = []
        self._biome: Optional[str] = None
        self._time_of_day: Optional[int] = None
        self._nearby_entities: List[Any] = []

    def update_from_events(self, events: List[Tuple[str, Dict]]):
        """
        Update world state from Mineflayer events.

        Events are in the format: List[(event_type, event_data)]
        The last event typically contains the full state.

        Args:
            events: List of Mineflayer event tuples
        """
        if not events:
            return

        self._last_events = events

        # Extract state from last event
        if events:
            last_event = events[-1]
            if len(last_event) >= 2:
                event_data = last_event[1]
                self._update_from_event_data(event_data)

    def _update_from_event_data(self, event_data: Dict):
        """
        Update internal state from event data dictionary.

        Args:
            event_data: Event data dictionary from Mineflayer
        """
        # Update inventory
        if "inventory" in event_data:
            self._inventory = event_data["inventory"]

        # Update position
        if "status" in event_data and "position" in event_data["status"]:
            self._position = event_data["status"]["position"]

        # Update nearby chests
        if "nearbyChests" in event_data:
            self._nearby_chests = event_data["nearbyChests"]

        # Update voxels
        if "voxels" in event_data:
            self._voxels = event_data["voxels"]

        # Update health
        if "status" in event_data and "health" in event_data["status"]:
            self._health = event_data["status"]["health"]

        # Update hunger
        if "status" in event_data and "food" in event_data["status"]:
            self._hunger = event_data["status"]["food"]

        # Update equipment
        if "status" in event_data and "equipment" in event_data["status"]:
            self._equipment = event_data["status"]["equipment"]

        # Update biome
        if "status" in event_data and "biome" in event_data["status"]:
            self._biome = event_data["status"]["biome"]

        # Update time
        if "status" in event_data and "timeOfDay" in event_data["status"]:
            self._time_of_day = event_data["status"]["timeOfDay"]

        # Update nearby entities
        if "status" in event_data and "entities" in event_data["status"]:
            self._nearby_entities = event_data["status"]["entities"]

    # Safe accessor methods

    def get_inventory(self) -> Dict[str, int]:
        """Get current inventory. Returns empty dict if not available."""
        return self._inventory.copy() if self._inventory else {}

    def get_position(self) -> Optional[Dict[str, float]]:
        """Get current position. Returns None if not available."""
        return self._position.copy() if self._position else None

    def get_nearby_chests(self) -> Dict[str, Any]:
        """Get nearby chests. Returns empty dict if not available."""
        return self._nearby_chests.copy() if self._nearby_chests else {}

    def get_voxels(self) -> List[Any]:
        """Get nearby voxels. Returns empty list if not available."""
        return self._voxels.copy() if self._voxels else []

    def get_health(self) -> Optional[float]:
        """Get current health. Returns None if not available."""
        return self._health

    def get_hunger(self) -> Optional[float]:
        """Get current hunger/food level. Returns None if not available."""
        return self._hunger

    def get_equipment(self) -> List[Any]:
        """Get current equipment. Returns empty list if not available."""
        return self._equipment.copy() if self._equipment else []

    def get_biome(self) -> Optional[str]:
        """Get current biome. Returns None if not available."""
        return self._biome

    def get_time_of_day(self) -> Optional[int]:
        """Get current time of day. Returns None if not available."""
        return self._time_of_day

    def get_nearby_entities(self) -> List[Any]:
        """Get nearby entities. Returns empty list if not available."""
        return self._nearby_entities.copy() if self._nearby_entities else []

    def get_last_events(self) -> List[Tuple[str, Dict]]:
        """Get raw last events. Returns empty list if not available."""
        return self._last_events.copy() if self._last_events else []

    def has_item(self, item_name: str) -> bool:
        """
        Check if inventory contains an item.

        Args:
            item_name: Item name to check

        Returns:
            True if item exists in inventory with count > 0
        """
        return self._inventory.get(item_name, 0) > 0

    def get_item_count(self, item_name: str) -> int:
        """
        Get count of an item in inventory.

        Args:
            item_name: Item name to check

        Returns:
            Item count (0 if not in inventory)
        """
        return self._inventory.get(item_name, 0)

    def to_dict(self) -> Dict[str, Any]:
        """
        Export world state as a dictionary.

        Returns:
            Dictionary with all state fields
        """
        return {
            "inventory": self.get_inventory(),
            "position": self.get_position(),
            "nearby_chests": self.get_nearby_chests(),
            "voxels": self.get_voxels(),
            "health": self.get_health(),
            "hunger": self.get_hunger(),
            "equipment": self.get_equipment(),
            "biome": self.get_biome(),
            "time_of_day": self.get_time_of_day(),
            "nearby_entities": self.get_nearby_entities(),
        }

    def __repr__(self) -> str:
        inv_count = len(self._inventory)
        pos = f"({self._position['x']:.1f}, {self._position['y']:.1f}, {self._position['z']:.1f})" if self._position else "unknown"
        return f"WorldState(inventory={inv_count} items, position={pos}, health={self._health})"
