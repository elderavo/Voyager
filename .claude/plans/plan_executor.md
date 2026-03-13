# Plan: Executor (Structured Plan Execution)

**Module:** `voyager/production/executor.py`

---

## Overview

The PlanExecutor takes a list of PlanNodes (produced by the Resolver) and executes them one-by-one against the mineflayer environment. It maps each PlanNode's `method` to the corresponding mineflayer primitive call, sends the JavaScript to `env.step()`, and checks the result.

The Executor does NOT plan, re-plan, or modify the plan. If a node fails, it stops and reports. The caller decides what to do next.

This replaces `HTNOrchestrator.execute_queued_tasks()` for structured plans.

---

## 1. Result Dataclasses

```python
@dataclass
class ExecutionError:
    type: str         # "missing_resource", "missing_tool", "missing_workspace", "runtime_error"
    message: str      # raw error message from mineflayer
    details: dict     # parsed info, e.g., {"missing_items": ["coal"]}

@dataclass
class ExecutionResult:
    success: bool
    events: list                          # all events from all executed nodes
    completed_nodes: list[PlanNode]       # nodes that succeeded
    failed_node: PlanNode | None = None   # the node that failed, if any
    error: ExecutionError | None = None   # structured error info
    final_inventory: list[str] = field(default_factory=list)  # inventory after execution
```

---

## 2. PlanExecutor Class

```python
class PlanExecutor:
    def __init__(self, env: VoyagerEnv, skill_manager: SkillManager):
        self.env = env
        self.skill_manager = skill_manager
```

---

## 3. Core Method: `execute(plan) -> ExecutionResult`

```python
def execute(self, plan: list[PlanNode]) -> ExecutionResult:
    all_events = []
    completed = []
    current_inventory = []

    for node in plan:
        result = self._execute_node(node)
        all_events.extend(result.events)

        if not result.success:
            return ExecutionResult(
                success=False,
                events=all_events,
                completed_nodes=completed,
                failed_node=node,
                error=result.error,
                final_inventory=result.final_inventory or current_inventory,
            )

        completed.append(node)
        current_inventory = result.final_inventory

    return ExecutionResult(
        success=True,
        events=all_events,
        completed_nodes=completed,
        final_inventory=current_inventory,
    )
```

---

## 4. Node Execution: `_execute_node(node) -> NodeResult`

Maps `node.method` to JavaScript code and calls `env.step()`:

```python
def _execute_node(self, node: PlanNode) -> NodeResult:
    code = self._generate_code(node)
    programs = self.skill_manager.programs

    events = self.env.step(code=code, programs=programs)

    # Check for errors
    error = self._check_events(events)

    # Extract inventory from observe event
    inventory = self._extract_inventory(events)

    if error:
        return NodeResult(success=False, events=events, error=error, final_inventory=inventory)

    return NodeResult(success=True, events=events, final_inventory=inventory)
```

---

## 5. Code Generation: `_generate_code(node) -> str`

Simple string formatting — NOT an LLM call:

```python
def _generate_code(self, node: PlanNode) -> str:
    method = node.method
    args = node.args

    if method == "craft":
        item = args["item"]
        qty = args.get("qty", 1)
        return f'await craftItem(bot, "{item}", {qty});'

    elif method == "mine":
        block = args["block"]
        qty = args.get("qty", 1)
        return f'await mineBlock(bot, "{block}", {qty});'

    elif method == "smelt":
        item = args["item"]
        qty = args.get("qty", 1)
        return f'await smeltItem(bot, "{item}", {qty});'

    elif method == "kill":
        mob = args["mob"]
        qty = args.get("qty", 1)
        return f'await killMob(bot, "{mob}", {qty});'

    elif method == "place":
        item = args["item"]
        return f'await placeItem(bot, "{item}", bot.entity.position);'

    elif method == "skill":
        skill_name = args["skill_name"]
        return f'await {skill_name}(bot);'

    else:
        raise ValueError(f"Unknown method: {method}")
```

### Notes on code generation
- Each `env.step()` call is **one primitive per step**, not batched JS
- The `programs` parameter makes all primitives + learned skills available
- Item names must be minecraft-data canonical names (already validated by Resolver)
- The `place` method uses `bot.entity.position` — mineflayer's placeItem will find a suitable nearby position

---

## 6. Error Checking: `_check_events(events) -> ExecutionError | None`

```python
def _check_events(self, events) -> ExecutionError | None:
    if not events:
        return ExecutionError(type="runtime_error", message="No events returned", details={})

    for event_type, event_data in events:
        if event_type == "onError":
            error_msg = event_data.get("onError", "Unknown error")
            return self._parse_error(error_msg)

    return None  # no errors
```

---

## 7. Error Parsing: `_parse_error(error_msg) -> ExecutionError`

Extract structured failure info from mineflayer error messages:

```python
def _parse_error(self, error_msg: str) -> ExecutionError:
    # Pattern: "I cannot make X because I need: item1, item2"
    match = re.search(r"I cannot make .+ because I need: (.+)", error_msg)
    if match:
        items = [item.strip() for item in match.group(1).split(",")]
        return ExecutionError(
            type="missing_resource",
            message=error_msg,
            details={"missing_items": items},
        )

    # Pattern: "there is no crafting table nearby"
    if "no crafting table nearby" in error_msg.lower():
        return ExecutionError(
            type="missing_workspace",
            message=error_msg,
            details={"workspace": "crafting_table"},
        )

    # Pattern: "I need at least a X to mine Y"
    match = re.search(r"I need at least a (.+) to mine (.+)", error_msg)
    if match:
        return ExecutionError(
            type="missing_tool",
            message=error_msg,
            details={"tool": match.group(1).strip(), "block": match.group(2).strip()},
        )

    # Pattern: "no furnace nearby"
    if "no furnace nearby" in error_msg.lower() or "furnace" in error_msg.lower():
        return ExecutionError(
            type="missing_workspace",
            message=error_msg,
            details={"workspace": "furnace"},
        )

    # Unknown error
    return ExecutionError(
        type="runtime_error",
        message=error_msg,
        details={},
    )
```

---

## 8. Inventory Extraction

```python
def _extract_inventory(self, events) -> list[str]:
    """Extract inventory from the last observe event."""
    for event_type, event_data in reversed(events):
        if event_type == "observe":
            return event_data.get("inventory", [])
    return []
```

---

## 9. NodeResult (internal)

```python
@dataclass
class NodeResult:
    success: bool
    events: list
    error: ExecutionError | None = None
    final_inventory: list[str] = field(default_factory=list)
```

---

## 10. Design Constraints

- **No planning.** Receives a list, runs it sequentially. Period.
- **No re-planning.** If a node fails, return failure to caller.
- **No LLM calls.** Code generation is string formatting.
- **No skill saving.** Caller handles that after success.
- **No critic evaluation.** Caller handles that after success.
- **One primitive per `env.step()`.** Not batched.
- **Error parsing is best-effort.** Unknown errors get `type="runtime_error"`.
- **Stateless.** No state carried between `execute()` calls.

---

## 11. Integration

- **Called by:** `Voyager._try_structured_execution()`
- **Calls:** `VoyagerEnv.step()` (same interface everything else uses)
- **Uses:** `SkillManager.programs` for available primitives + skills
- **Replaces:** `HTNOrchestrator.execute_queued_tasks()` for structured plans

---

## 12. Edge Cases

| Scenario | Behavior |
|----------|----------|
| Empty plan (goal already satisfied) | Return `ExecutionResult(success=True, events=[], completed_nodes=[])` |
| First node fails | Return failure with `completed_nodes=[]` |
| Middle node fails | Return failure with partial `completed_nodes` |
| `env.step()` returns empty events | Treated as `runtime_error` |
| `env.step()` throws exception | Catch, wrap in `ExecutionError(type="runtime_error")` |
| Unknown method in PlanNode | `ValueError` — this is a bug in the Resolver, not a runtime error |
