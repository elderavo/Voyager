# Plan: Learn Loop Integration

**Module:** Modifications to `voyager/voyager.py` + minor additions

---

## Overview

This plan covers how the new production system integrates into the existing Voyager learn loop. The key change: before sending a task to the ActionAgent (LLM), try to handle it with the structured production path (Resolver → Executor). Only fall back to ActionAgent if structured resolution fails or encounters an unrecoverable error.

The existing code is PRESERVED — the structured path is an addition, not a replacement.

---

## 1. Task Classification (inline method, not a separate class)

Add to `Voyager`:

```python
import re

def _classify_task(self, task: str) -> tuple[bool, Goal | None]:
    """
    Classify a curriculum task as structured (production) or open-ended.

    Returns (is_structured, goal) where goal is None for open-ended tasks.
    """
    task_lower = task.lower().strip()

    # Pattern: "Craft [N] <item>"
    match = re.match(r"craft\s+(?:(\d+)\s+)?(.+)", task_lower)
    if match:
        qty = int(match.group(1)) if match.group(1) else 1
        item = self._normalize_task_item(match.group(2))
        if item:
            return True, HaveItem(item, qty)

    # Pattern: "Mine/Gather/Collect [N] <item>"
    match = re.match(r"(?:mine|gather|collect)\s+(?:(\d+)\s+)?(.+)", task_lower)
    if match:
        qty = int(match.group(1)) if match.group(1) else 1
        item = self._normalize_task_item(match.group(2))
        if item:
            return True, HaveItem(item, qty)

    # Pattern: "Smelt [N] <item>"
    match = re.match(r"smelt\s+(?:(\d+)\s+)?(.+)", task_lower)
    if match:
        qty = int(match.group(1)) if match.group(1) else 1
        item = self._normalize_task_item(match.group(2))
        if item:
            return True, HaveItem(item, qty)

    # Pattern: "Obtain/Get [N] <item>"
    match = re.match(r"(?:obtain|get)\s+(?:(\d+)\s+)?(.+)", task_lower)
    if match:
        qty = int(match.group(1)) if match.group(1) else 1
        item = self._normalize_task_item(match.group(2))
        if item:
            return True, HaveItem(item, qty)

    # Everything else: not structured
    # "Explore ...", "Build ...", "Go to ...", "Find ...", "Kill ..." etc.
    return False, None
```

### Item name normalization helper

```python
def _normalize_task_item(self, raw: str) -> str | None:
    """Normalize free-form item name to minecraft-data canonical form."""
    name = raw.strip().lower().replace(" ", "_")
    # Remove articles
    name = re.sub(r"^(a|an|the|some)\s+", "", name).strip().replace(" ", "_")
    # Handle plurals
    if name.endswith("s") and not name.endswith("ss"):
        singular = name[:-1]
        # Check if singular is valid in registry
        if self.method_registry and self.method_registry.is_known_item(singular):
            return singular
    # Check as-is
    if self.method_registry and self.method_registry.is_known_item(name):
        return name
    return None  # unknown item — fall through to ActionAgent
```

### Design decisions
- **Conservative classification.** When in doubt, return `(False, None)` — let ActionAgent handle it.
- **No LLM call** for classification. Pure regex.
- **"Kill X" falls through.** Kill is a leaf action, not decomposable. ActionAgent handles combat.
- **"Build X" falls through.** Building is open-ended.
- **"Explore X" falls through.** Exploration is open-ended.

---

## 2. Production System Initialization

Add lazy initialization to `Voyager`:

```python
# In __init__:
self.method_registry = None
self.resolver = None
self.plan_executor = None
self._production_initialized = False

# New method:
def _initialize_production_system(self):
    """Lazy init of production system after env connects."""
    if self._production_initialized:
        return

    try:
        from voyager.production import MethodRegistry, Resolver, PlanExecutor
        self.method_registry = MethodRegistry(self.env)
        self.resolver = Resolver(self.method_registry, self.skill_manager)
        self.plan_executor = PlanExecutor(self.env, self.skill_manager)
        self._production_initialized = True
        logger.info("Production system initialized")
    except Exception as e:
        logger.error(f"Failed to initialize production system: {e}", exc_info=True)
        self._production_initialized = False
```

**When to init:** Call from `learn()` after the first `env.reset()`, or from `rollout()` before task classification.

---

## 3. Modified Rollout Flow

```python
def rollout(self, *, task, context, reset_env=True):
    self.reset(task=task, context=context, reset_env=reset_env)

    # Initialize production system if needed
    self._initialize_production_system()

    # Try structured production path first
    if self._production_initialized:
        is_structured, goal = self._classify_task(task)
        if is_structured and goal:
            result = self._try_structured_execution(goal, task, context)
            if result is not None:
                return result  # structured path handled it (success or definitive failure)
            # result is None → fall through to ActionAgent
            logger.info(f"Structured execution failed for '{task}', falling back to ActionAgent")

    # Existing ActionAgent loop (unchanged)
    while True:
        messages, reward, done, info = self.step()
        if done:
            break
    return messages, reward, done, info
```

---

## 4. Structured Execution Method

```python
MAX_REPAIR_ATTEMPTS = 3

def _try_structured_execution(self, goal, task, context):
    """
    Attempt structured production planning and execution.

    Returns (messages, reward, done, info) on success or definitive failure.
    Returns None to signal "fall back to ActionAgent".
    """
    # Get current state
    if not self.last_events or len(self.last_events) == 0:
        return None  # no state to work with

    inventory = self.last_events[-1][1].get("inventory", [])
    world_state = self.last_events[-1][1]

    attempt = 0
    while attempt < self.MAX_REPAIR_ATTEMPTS:
        # Resolve
        try:
            plan = self.resolver.resolve(goal, inventory, world_state)
        except ResolutionError as e:
            logger.warning(f"Resolution failed (attempt {attempt + 1}): {e}")
            return None  # can't resolve → fall back to ActionAgent

        if not plan:
            # Goal already satisfied
            logger.info(f"Goal already satisfied: {goal}")
            # Still run critic to confirm
            break

        logger.info(f"Resolved plan ({len(plan)} steps): {[str(n.goal) for n in plan]}")

        # Execute
        result = self.plan_executor.execute(plan)

        if result.success:
            logger.info(f"Structured execution succeeded for: {goal}")
            break

        # Execution failed — check if repairable
        if result.error and result.error.type in ("missing_resource", "missing_tool", "missing_workspace"):
            logger.warning(
                f"Repairable failure (attempt {attempt + 1}): {result.error.type} — {result.error.message}"
            )
            # Update state from latest observation and retry
            inventory = result.final_inventory
            world_state = self._extract_world_state(result.events) or world_state
            attempt += 1
            continue
        else:
            # Non-repairable error
            logger.warning(f"Non-repairable execution error: {result.error}")
            return None  # fall back to ActionAgent
    else:
        # Exhausted repair attempts
        logger.warning(f"Exhausted {self.MAX_REPAIR_ATTEMPTS} repair attempts for: {goal}")
        return None  # fall back to ActionAgent

    # --- Post-execution: critic + skill saving ---

    # Use latest events for critic evaluation
    events = result.events if result and result.events else self.last_events

    # Run critic
    success, critique = self.critic_agent.check_task_success(
        events=events,
        task=task,
        context=context,
        chest_observation=self.action_agent.render_chest_observation(),
        max_retries=5,
    )

    # Build info dict (same shape as existing code)
    info = {
        "task": task,
        "success": success,
        "conversations": [],
    }

    if success:
        # Save skills for completed production nodes
        self._save_structured_skills(result.completed_nodes, task)

        # Populate program info for skill manager
        skill_name = self._generate_skill_name(goal)
        info["program_name"] = skill_name
        info["program_code"] = self._generate_skill_code(skill_name, result.completed_nodes)

    self.last_events = events if events else self.last_events
    self.recorder.record(events, task)

    done = True  # structured path always completes in one shot (no multi-step retry)
    return self.messages, 0, done, info
```

---

## 5. Helper Methods

### Extract world state from events

```python
def _extract_world_state(self, events):
    """Extract the latest observation from events."""
    for event_type, event_data in reversed(events):
        if event_type == "observe":
            return event_data
    return None
```

### Generate skill name

```python
def _generate_skill_name(self, goal):
    """Generate camelCase skill name from goal."""
    if isinstance(goal, HaveItem):
        # "oak_planks" → "craftOakPlanks" or "mineOakLog"
        parts = goal.item.split("_")
        camel = "".join(p.capitalize() for p in parts)
        return f"obtain{camel}"
    return "unknownSkill"
```

### Save structured skills

```python
def _save_structured_skills(self, completed_nodes, task):
    """Save reusable skills from completed plan nodes."""
    for node in completed_nodes:
        if not node.save_as_skill:
            continue
        # Generate skill info compatible with skill_manager.add_new_skill()
        skill_name = self._node_to_skill_name(node)
        # Check if skill already exists
        if skill_name in self.skill_manager.skills:
            continue

        code = self._generate_node_skill_code(skill_name, node)
        recipe = None
        if node.method == "craft":
            recipe = {
                "output": node.args["item"],
                "output_qty": node.args.get("qty", 1),
                "inputs": [],  # populated from registry
                "workspace": None,
                "method": "craft",
            }

        info = {
            "task": task,
            "success": True,
            "program_code": code,
            "program_name": skill_name,
            "recipe": recipe,
        }
        self.skill_manager.add_new_skill(info)
```

### Generate JS code for a node

```python
def _generate_node_skill_code(self, skill_name, node):
    """Generate JavaScript function for a single plan node."""
    method = node.method
    args = node.args

    if method == "craft":
        item = args["item"]
        qty = args.get("qty", 1)
        body = f'  await craftItem(bot, "{item}", {qty});'
    elif method == "smelt":
        item = args["item"]
        qty = args.get("qty", 1)
        body = f'  await smeltItem(bot, "{item}", {qty});'
    else:
        return ""  # don't generate for mine/kill/place

    return f"async function {skill_name}(bot) {{\n{body}\n}}"
```

---

## 6. What Stays the Same

| Component | Changes? |
|-----------|----------|
| `CurriculumAgent` | No changes |
| `CriticAgent` | No changes |
| `ActionAgent` | No changes |
| `SkillManager` | Minor additions (see plan_skill_store.md) |
| `VoyagerEnv` | No changes |
| `Voyager.step()` | No changes (still used for ActionAgent fallback) |
| `Voyager.learn()` | No changes (calls rollout which has new logic) |
| `Voyager.reset()` | No changes |

---

## 7. What Gets Deprecated

| Component | Status |
|-----------|--------|
| `HTNOrchestrator` | Keep for now. Structured tasks bypass it. Remove later. |
| `SkillExecutor` | Absorbed into Resolver + Executor. Can be deleted. |
| `_request_skill_for_prereq()` | Replaced by Resolver's recursive resolution. Mark deprecated. |
| `voyager/facts/` | Already deleted. MethodRegistry replaces it. |

---

## 8. Migration Strategy

### Phase 1: Add production system alongside existing code
- Create `voyager/production/` module
- Add lazy initialization
- Add `_classify_task()` and `_try_structured_execution()`
- Both paths available, structured path tried first

### Phase 2: Validate
- Run with logging to see which tasks get classified as structured
- Verify structured execution produces correct results
- Compare with ActionAgent path for same tasks

### Phase 3: Clean up
- Remove `HTNOrchestrator` usage for structured tasks
- Delete `SkillExecutor`
- Remove `_request_skill_for_prereq()`

---

## 9. Design Constraints

- **Additive, not destructive.** All existing functionality preserved.
- **Conservative classification.** Unrecognized tasks always fall through to ActionAgent.
- **No changes to existing method signatures.** `rollout()` and `learn()` return types unchanged.
- **Fail-safe.** If production system init fails, everything works as before.
- **No curriculum changes.** The curriculum agent doesn't need to know about the production path.
