# Plan: Resolver (Recursive Dependency Resolution)

**Module:** `voyager/production/resolver.py`

---

## Overview

The Resolver is the core planner. It takes a Goal (e.g., `HaveItem("iron_pickaxe", 1)`) and recursively decomposes it into an ordered list of PlanNodes that the Executor can run sequentially.

This replaces the LLM-driven decomposition in `HTNOrchestrator` and the recipe-based dependency checking in `SkillExecutor` for structured tasks.

**Key principle:** The Resolver is a pure function — no side effects, no mineflayer calls, no LLM calls. It takes state in, returns a plan out.

---

## 1. Resolver Class

```python
class Resolver:
    def __init__(self, registry: MethodRegistry, skill_manager: SkillManager):
        self.registry = registry
        self.skill_manager = skill_manager

    MAX_DEPTH = 20  # prevent runaway recursion
```

---

## 2. Core Method: `resolve(goal, inventory, world_state) -> list[PlanNode]`

```python
def resolve(
    self,
    goal: Goal,
    inventory: list[str],
    world_state: dict,
) -> list[PlanNode]:
    """
    Resolve a goal into an ordered list of PlanNodes.

    Returns nodes in EXECUTION ORDER (dependencies first, target last).
    Raises ResolutionError if no method can satisfy the goal.
    """
    virtual_inv = VirtualInventory(inventory)
    resolving = set()  # for cycle detection
    return self._resolve(goal, virtual_inv, world_state, resolving, depth=0)
```

---

## 3. Recursive Implementation: `_resolve()`

```python
def _resolve(self, goal, virtual_inv, world_state, resolving, depth) -> list[PlanNode]:
    # Guard: max depth
    if depth > self.MAX_DEPTH:
        raise ResolutionError(f"Max recursion depth exceeded resolving {goal}")

    # 1. Already satisfied?
    if goal.satisfied(virtual_inv.items(), world_state):
        return []

    # 2. Cycle detection
    if goal in resolving:
        raise ResolutionError(f"Circular dependency detected: {goal}")
    resolving = resolving | {goal}  # immutable copy — don't mutate parent's set

    # 3. Dispatch by goal type
    if isinstance(goal, HaveItem):
        return self._resolve_have_item(goal, virtual_inv, world_state, resolving, depth)
    elif isinstance(goal, WorkspaceAvailable):
        return self._resolve_workspace(goal, virtual_inv, world_state, resolving, depth)
    else:
        raise ResolutionError(f"Unknown goal type: {type(goal)}")
```

---

## 4. Resolving HaveItem

```python
def _resolve_have_item(self, goal, virtual_inv, world_state, resolving, depth):
    item, qty = goal.item, goal.qty

    # Check for existing skill that produces this item
    skill_result = self.skill_manager.find_skill_by_output(item)
    if skill_result:
        skill_name, skill_data = skill_result
        node = PlanNode(
            goal=goal, method="skill", role="produce",
            args={"skill_name": skill_name}, save_as_skill=False
        )
        virtual_inv.add(item, skill_data.get("recipe", {}).get("output_qty", 1))
        return [node]

    # Look up production methods
    methods = self.registry.get_methods(item)
    if not methods:
        raise ResolutionError(f"No known method to produce: {item}")

    # Try each method in priority order
    errors = []
    for method_info in methods:
        try:
            plan = self._try_method(goal, method_info, virtual_inv, world_state, resolving, depth)
            return plan
        except ResolutionError as e:
            errors.append(f"{method_info.type}: {e}")
            continue

    raise ResolutionError(
        f"All methods failed for {goal}:\n" + "\n".join(f"  - {e}" for e in errors)
    )
```

---

## 5. Trying a Specific Method

```python
def _try_method(self, goal, method_info, virtual_inv, world_state, resolving, depth):
    plan = []
    item = goal.item
    qty = goal.qty

    if method_info.type == "craft":
        # Resolve workspace if needed
        if method_info.workspace:
            ws_goal = WorkspaceAvailable(method_info.workspace)
            plan.extend(self._resolve(ws_goal, virtual_inv, world_state, resolving, depth + 1))

        # Resolve each input ingredient
        # Scale quantities: if recipe makes 4 planks and we need 4, execute once
        # If we need 8, execute twice — but for v1, just resolve qty=ceil(need/output_qty)
        executions = math.ceil(qty / method_info.output_qty)
        for input_item, input_count in method_info.input_quantities.items():
            needed = input_count * executions
            have = virtual_inv.count(input_item)
            if have < needed:
                sub_goal = HaveItem(input_item, needed - have)
                plan.extend(self._resolve(sub_goal, virtual_inv, world_state, resolving, depth + 1))

        # Add the craft node itself (AFTER dependencies)
        node = PlanNode(
            goal=goal, method="craft", role="produce",
            args={"item": item, "qty": executions},
            save_as_skill=True,
        )
        plan.append(node)

        # Update virtual inventory
        for input_item, input_count in method_info.input_quantities.items():
            virtual_inv.remove(input_item, input_count * executions)
        virtual_inv.add(item, method_info.output_qty * executions)

    elif method_info.type == "smelt":
        # Resolve workspace (furnace)
        ws_goal = WorkspaceAvailable("furnace")
        plan.extend(self._resolve(ws_goal, virtual_inv, world_state, resolving, depth + 1))

        # Resolve raw material
        raw_item = method_info.inputs[0]  # e.g., "iron_ore"
        have = virtual_inv.count(raw_item)
        if have < qty:
            plan.extend(self._resolve(HaveItem(raw_item, qty - have), virtual_inv, world_state, resolving, depth + 1))

        # Resolve fuel
        fuel = "coal"  # default fuel; could be expanded
        have_fuel = virtual_inv.count(fuel)
        if have_fuel < qty:
            plan.extend(self._resolve(HaveItem(fuel, qty - have_fuel), virtual_inv, world_state, resolving, depth + 1))

        node = PlanNode(
            goal=goal, method="smelt", role="produce",
            args={"item": item, "qty": qty, "fuel": fuel},
            save_as_skill=True,
        )
        plan.append(node)
        virtual_inv.remove(raw_item, qty)
        virtual_inv.remove(fuel, qty)
        virtual_inv.add(item, qty)

    elif method_info.type == "mine":
        # Leaf node — no recursion into sub-dependencies
        # BUT: check tool requirement
        if method_info.tool:
            # Check if bot has an adequate tool
            if not self._has_adequate_tool(method_info.tool, virtual_inv):
                # Resolve crafting the minimum tool
                plan.extend(self._resolve(
                    HaveItem(method_info.tool, 1), virtual_inv, world_state, resolving, depth + 1
                ))

        node = PlanNode(
            goal=goal, method="mine", role="produce",
            args={"block": item, "qty": qty},
            save_as_skill=False,  # leaf nodes not saved
        )
        plan.append(node)
        virtual_inv.add(item, qty)

    elif method_info.type == "kill":
        # Leaf node
        mob = self.registry.mob_drops.get(item, "unknown")
        node = PlanNode(
            goal=goal, method="kill", role="produce",
            args={"mob": mob, "qty": qty},
            save_as_skill=False,
        )
        plan.append(node)
        virtual_inv.add(item, qty)  # optimistic

    return plan
```

---

## 6. Resolving WorkspaceAvailable

```python
def _resolve_workspace(self, goal, virtual_inv, world_state, resolving, depth):
    ws_type = goal.workspace_type

    # Already nearby?
    voxels = world_state.get("voxels", [])
    if ws_type in voxels:
        return []

    # In inventory? Just place it.
    if virtual_inv.count(ws_type) > 0:
        node = PlanNode(
            goal=goal, method="place", role="enable",
            args={"item": ws_type},
            save_as_skill=False,
        )
        virtual_inv.remove(ws_type, 1)
        return [node]

    # Need to obtain it first, then place it
    plan = []
    plan.extend(self._resolve(
        HaveItem(ws_type, 1), virtual_inv, world_state, resolving, depth + 1
    ))
    place_node = PlanNode(
        goal=goal, method="place", role="enable",
        args={"item": ws_type},
        save_as_skill=False,
    )
    plan.append(place_node)
    virtual_inv.remove(ws_type, 1)
    return plan
```

---

## 7. VirtualInventory

A mutable inventory tracker for planning purposes (local to a single `resolve()` call):

```python
class VirtualInventory:
    def __init__(self, real_inventory: list[str]):
        self._counts = Counter(real_inventory)

    def count(self, item: str) -> int:
        return self._counts.get(item, 0)

    def add(self, item: str, qty: int):
        self._counts[item] = self._counts.get(item, 0) + qty

    def remove(self, item: str, qty: int):
        current = self._counts.get(item, 0)
        self._counts[item] = max(0, current - qty)

    def items(self) -> list[str]:
        """Return as flat list (mineflayer inventory format)."""
        result = []
        for item, count in self._counts.items():
            result.extend([item] * count)
        return result
```

### Why this matters
Without virtual inventory tracking, the resolver would over-plan. Example:
- Goal: `HaveItem("wooden_pickaxe", 1)` needs 3 planks + 2 sticks
- Sticks need 2 planks
- Without tracking: resolver plans for 3 + 2 = 5 planks worth of logs
- With tracking: resolver knows the planks recipe produces 4, so 1 log → 4 planks → enough for both sticks and pickaxe

---

## 8. Tool Adequacy Check

```python
# Tool tier ordering
TOOL_TIERS = {
    "wooden_pickaxe": 1, "stone_pickaxe": 2, "iron_pickaxe": 3,
    "golden_pickaxe": 1, "diamond_pickaxe": 4, "netherite_pickaxe": 5,
    "wooden_axe": 1, "stone_axe": 2, "iron_axe": 3,
    "wooden_shovel": 1, "stone_shovel": 2, "iron_shovel": 3,
}

def _has_adequate_tool(self, required_tool: str, virtual_inv: VirtualInventory) -> bool:
    required_tier = TOOL_TIERS.get(required_tool, 0)
    # Extract tool type (pickaxe, axe, shovel)
    tool_type = required_tool.split("_")[-1]  # "pickaxe" from "stone_pickaxe"

    for item, count in virtual_inv._counts.items():
        if count > 0 and item.endswith(f"_{tool_type}"):
            item_tier = TOOL_TIERS.get(item, 0)
            if item_tier >= required_tier:
                return True
    return False
```

---

## 9. ResolutionError

```python
class ResolutionError(Exception):
    """Raised when the resolver cannot produce a valid plan."""
    pass
```

Simple exception with a descriptive message. The caller catches this and falls back to ActionAgent.

---

## 10. Example Trace

Goal: `HaveItem("wooden_pickaxe", 1)`

```
resolve(HaveItem(wooden_pickaxe, 1))
  methods: [craft(planks×3 + stick×2, workspace=crafting_table)]

  resolve(WorkspaceAvailable(crafting_table))
    not in voxels, not in inventory
    resolve(HaveItem(crafting_table, 1))
      methods: [craft(planks×4, workspace=None)]  # 2x2 recipe
      resolve(HaveItem(oak_planks, 4))
        methods: [craft(oak_log×1, workspace=None)]
        resolve(HaveItem(oak_log, 1))
          methods: [mine]
          → PlanNode(mine oak_log ×1)
          virtual_inv: {oak_log: 1}
        → PlanNode(craft oak_planks ×1)  # produces 4
        virtual_inv: {oak_planks: 4}
      → PlanNode(craft crafting_table ×1)
      virtual_inv: {oak_planks: 0, crafting_table: 1}
    → PlanNode(place crafting_table)
    virtual_inv: {crafting_table: 0}

  resolve(HaveItem(oak_planks, 3))  # for pickaxe
    need 3, have 0 → need more
    resolve(HaveItem(oak_log, 1))
      → PlanNode(mine oak_log ×1)
    → PlanNode(craft oak_planks ×1)  # produces 4
    virtual_inv: {oak_planks: 4}

  resolve(HaveItem(stick, 2))
    methods: [craft(planks×2)]
    have 4 planks, need 2 → satisfied
    → PlanNode(craft stick ×1)  # produces 4
    virtual_inv: {oak_planks: 2, stick: 4}

  → PlanNode(craft wooden_pickaxe ×1)

Final plan:
  1. mine oak_log ×1
  2. craft oak_planks (→ 4 planks)
  3. craft crafting_table
  4. place crafting_table
  5. mine oak_log ×1
  6. craft oak_planks (→ 4 planks)
  7. craft stick
  8. craft wooden_pickaxe
```

---

## 11. Design Constraints

- **Pure function.** No side effects, no mineflayer calls, no mutations outside VirtualInventory.
- **Stateless between calls.** No mutable state carried across `resolve()` invocations.
- **Cycle detection via immutable set copies.** Each recursive branch gets its own resolving set.
- **First-match method selection.** Try methods in priority order, return first that works.
- **Max depth = 20.** More than enough for any Minecraft production chain.
- **No LLM calls.** Pure algorithmic planning.
- **No JS generation.** Returns PlanNodes, not code.

---

## 12. Error Cases

| Scenario | Behavior |
|----------|----------|
| Unknown item | `ResolutionError("No known method to produce: xyz")` |
| Circular dependency | `ResolutionError("Circular dependency detected: ...")` |
| Max depth exceeded | `ResolutionError("Max recursion depth exceeded...")` |
| All methods fail | `ResolutionError("All methods failed for ...: [reasons]")` |
| Item only obtainable by kill but mob killing not implemented | Same as unknown — falls through to ActionAgent |
