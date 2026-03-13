# Plan: Goal/Predicate System

**Module:** `voyager/production/goals.py`
**Also creates:** `voyager/production/__init__.py`

---

## Overview

The Goal/Predicate system is the foundational data model for the structured production path. All other modules (Resolver, Executor, MethodRegistry) operate on these types. Goals are pure data objects with one predicate method (`satisfied()`). No business logic.

---

## 1. Goal Base Class

```python
from dataclasses import dataclass
from collections import Counter

@dataclass(frozen=True)
class Goal:
    """Base class for all planning goals."""

    def satisfied(self, inventory: list[str], world_state: dict) -> bool:
        """Check if this goal is already met given current state."""
        raise NotImplementedError
```

- `frozen=True` for hashability (used in sets for cycle detection)
- `inventory` is the mineflayer format: list of strings like `["oak_log", "oak_log", "stick"]`
- `world_state` is the observation dict from `events[-1][1]` with keys: `"status"`, `"voxels"`, `"inventory"`

---

## 2. HaveItem

```python
@dataclass(frozen=True)
class HaveItem(Goal):
    item: str    # minecraft-data canonical name, e.g. "oak_log", "iron_ingot"
    qty: int = 1

    def satisfied(self, inventory: list[str], world_state: dict) -> bool:
        count = Counter(inventory).get(self.item, 0)
        return count >= self.qty

    def __repr__(self):
        return f"HaveItem({self.item}, {self.qty})"
```

### Notes
- Item names are minecraft-data canonical: `oak_log`, `iron_ingot`, `crafting_table`
- Inventory from mineflayer is a flat list of item name strings — use `Counter` to count
- `qty` defaults to 1 for most use cases

---

## 3. WorkspaceAvailable

```python
@dataclass(frozen=True)
class WorkspaceAvailable(Goal):
    workspace_type: str  # "crafting_table", "furnace", "anvil", "brewing_stand"

    def satisfied(self, inventory: list[str], world_state: dict) -> bool:
        # Check nearby blocks (voxels)
        voxels = world_state.get("voxels", [])
        if self.workspace_type in voxels:
            return True

        # Check inventory (bot can place it)
        if self.workspace_type in inventory:
            return True

        return False

    def __repr__(self):
        return f"WorkspaceAvailable({self.workspace_type})"
```

### Notes
- Satisfied if the block is nearby (in voxels) OR in inventory (bot can place it)
- The Resolver handles the "place it" step if it's in inventory but not nearby
- For crafting_table: some recipes only need 2x2 grid (player crafting). The MethodRegistry should indicate this, not the Goal. The Goal just checks availability.

---

## 4. PlanNode

```python
@dataclass
class PlanNode:
    goal: Goal
    method: str          # "craft", "mine", "smelt", "kill", "place", "skill"
    role: str            # "produce" or "enable"
    args: dict           # method-specific: {"item": "oak_planks", "qty": 1}
    save_as_skill: bool = True
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `goal` | `Goal` | What this node achieves when executed |
| `method` | `str` | Which primitive to invoke: `"craft"`, `"mine"`, `"smelt"`, `"kill"`, `"place"`, `"skill"` |
| `role` | `str` | `"produce"` = target output, `"enable"` = environment setup (e.g., placing crafting table) |
| `args` | `dict` | Passed to the executor. Keys vary by method (see below) |
| `save_as_skill` | `bool` | `True` for craft/smelt nodes, `False` for mine/kill/place (leaf/ephemeral nodes) |

### Args by method

- **craft**: `{"item": "oak_planks", "qty": 1}`
- **mine**: `{"block": "oak_log", "qty": 1}`
- **smelt**: `{"item": "iron_ingot", "qty": 1, "fuel": "coal"}`
- **kill**: `{"mob": "cow", "qty": 1}`
- **place**: `{"item": "crafting_table"}`
- **skill**: `{"skill_name": "craftOakPlanks"}`

---

## 5. Future Goal Types (document only, DO NOT implement)

These will be added when their production methods are implemented:

- **`CanHarvest(block_type: str)`** — checks if bot has a tool that can harvest the block. Satisfied by checking `bot.pathfinder.bestHarvestTool(block)` via mineflayer.
- **`FuelAvailable(amount: int)`** — checks if bot has fuel items (coal, charcoal, planks, etc.) for smelting.
- **`EntityAccessible(entity_type: str)`** — checks if a mob/villager is nearby.

---

## 6. `__init__.py`

```python
# voyager/production/__init__.py
from .goals import Goal, HaveItem, WorkspaceAvailable, PlanNode
```

---

## 7. Design Constraints

- **No inheritance beyond Goal base.** HaveItem and WorkspaceAvailable are the only subclasses for now.
- **No ABC/metaclass.** Just frozen dataclasses.
- **No business logic.** Goals answer one question: "am I satisfied?" Nothing else.
- **No mineflayer interaction.** Goals receive state, they don't fetch it.
- **No method registry or resolver logic.** Those are separate modules.
- **Inventory format:** list of strings from mineflayer, NOT a dict. Use `Counter()` to count.

---

## 8. Testing Notes

- `HaveItem("oak_log", 3).satisfied(["oak_log", "oak_log", "oak_log", "stick"], {})` → `True`
- `HaveItem("oak_log", 4).satisfied(["oak_log", "oak_log", "oak_log", "stick"], {})` → `False`
- `WorkspaceAvailable("crafting_table").satisfied([], {"voxels": ["crafting_table", "dirt"]})` → `True`
- `WorkspaceAvailable("furnace").satisfied(["furnace"], {"voxels": []})` → `True`
- `WorkspaceAvailable("furnace").satisfied([], {"voxels": []})` → `False`
- Goals are hashable: `{HaveItem("oak_log", 1), HaveItem("oak_log", 1)}` has length 1
