"""
Trace module - immutable wrapper for environment execution events.

Phase 0: Type introduction only, no behavior changes.
"""
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass


@dataclass(frozen=True)
class Trace:
    """
    Immutable wrapper for raw environment events.

    In Phase 0, this is purely a type wrapper with no semantic changes.
    Future phases will add observation extraction and decision logic.

    Attributes:
        events: Raw event list from environment
                Format: List[Tuple[event_type: str, event_data: Dict]]
                event_type: "onChat", "onError", "onSave", "observe"
    """
    events: Tuple[Tuple[str, Dict[str, Any]], ...]

    @staticmethod
    def from_events(events: List[Tuple[str, Dict[str, Any]]]) -> 'Trace':
        """
        Create Trace from raw event list.

        Args:
            events: Raw events from environment

        Returns:
            Immutable Trace wrapping events
        """
        return Trace(events=tuple(events))

    def to_list(self) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Convert back to list format for backward compatibility.

        Returns:
            Mutable list of events
        """
        return list(self.events)

    def __len__(self) -> int:
        """Number of events in trace."""
        return len(self.events)

    def __iter__(self):
        """Allow iteration over events."""
        return iter(self.events)

    def __getitem__(self, index):
        """Allow indexing into events."""
        return self.events[index]
