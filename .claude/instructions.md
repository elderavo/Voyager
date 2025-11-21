# ✅ **SUMMARY OF REQUIRED CHANGES**

You must implement **four modifications** across the Voyager+Executor stack:

1. **Tag tasks as “mine” or “craft” inside voyager.py**
2. **Propagate this task_type into the Executor (craft_item / ensure_skill / _ensure_dependency)**
3. **Prevent mining tasks from invoking crafting logic**
4. **Prevent mining tasks from being saved as skills**

Each modification is listed in exact order below.

---

# 🟦 **FILE 1 — voyager.py**

**Path:** `voyager.py`

## **Step 1 — Add task_type detection before calling executor or skills**

Find the section in `voyager.py` where tasks are executed:

Search for:

```python
if use_executor and task.lower().startswith("craft "):
```

Modify it to classify task type:

```python
if task.lower().startswith("craft"):
    task_type = "craft"
elif task.lower().startswith("mine"):
    task_type = "mine"
else:
    task_type = "unknown"
```

Then pass this into the executor calls:

### For crafting tasks:

Replace:

```python
success, events, normalized_name = self.executor.craft_item(item_name)
```

with:

```python
success, events, normalized_name = self.executor.craft_item(item_name, task_type="craft")
```

### For mining tasks:

Wherever you call a mining skill or LLM-generated mining function, modify to:

```python
success, events = self.executor.direct_mine(block_type, count, task_type="mine")
```

(You will add direct_mine in the Executor below.)

---

# 🟦 **FILE 2 — executor.py**

**Path:** `executor.py`

You must modify **three** methods:

* `craft_item`
* `ensure_skill`
* `_ensure_dependency`

And add **one new primitive**: `_direct_execute_mine`

---

## **Step 2 — Modify craft_item signature to accept task_type**

### Find:

```python
def craft_item(self, item_name: str) -> Tuple[bool, List[Any], str]:
```

### Change to:

```python
def craft_item(self, item_name: str, task_type="craft") -> Tuple[bool, List[Any], str]:
```

Then pass task_type to ensure_skill:

Replace:

```python
success, _ = self.ensure_skill(skill_name, depth=0)
```

with:

```python
success, _ = self.ensure_skill(skill_name, depth=0, task_type=task_type)
```

---

## **Step 3 — Modify ensure_skill signature to accept task_type**

### Find:

```python
def ensure_skill(self, skill_name: str, depth: int = 0) -> Tuple[bool, List[ExecutionStep]]:
```

### Change to:

```python
def ensure_skill(self, skill_name: str, depth: int = 0, task_type="craft") -> Tuple[bool, List[ExecutionStep]]:
```

Now modify the section that checks if skill already exists:

### Replace this:

```python
if skill_name in self.skill_manager.skills:
    print(f"Skill '{skill_name}' already exists")
    return True, [ExecutionStep("skill", skill_name, [], success=True)]
```

### With this:

```python
if skill_name in self.skill_manager.skills:
    print(f"Skill '{skill_name}' already exists — testing it")
    success, events = self.execute_skill(skill_name)
    if success:
        return True, [ExecutionStep("skill", skill_name, [], success=True)]

    print(f"Skill '{skill_name}' is outdated — re-discovering")
    # FALL THROUGH to dependency discovery
```

Critically: now add task_type to dependency resolution:

Find:

```python
dep_success = self._ensure_dependency(dep, depth)
```

Replace with:

```python
dep_success = self._ensure_dependency(dep, depth, task_type=task_type)
```

---

## **Step 4 — Modify _ensure_dependency so MINING cannot trigger crafting**

### Find:

```python
def _ensure_dependency(self, dep: str, current_depth: int) -> bool:
```

### Change to:

```python
def _ensure_dependency(self, dep: str, current_depth: int, task_type="craft") -> bool:
```

Now add this block **at the beginning**:

```python
# MINING tasks are forbidden from invoking crafting dependencies
if task_type == "mine":
    print(f"[DEBUG] Mining task cannot auto-craft dependency '{dep}'. Failing only.")
    return False
```

This enforces:

### ✔ Mining NEVER calls crafting

### ✔ Crafting CAN call mining recursively

### ✔ Mining → crafting direction is blocked

### ✔ Crafting → mining direction remains allowed

---

## **Step 5 — Add a dedicated mining primitive executor**

Add at bottom of `executor.py`:

```python
def direct_mine(self, item_name: str, count: int = 1, task_type="mine"):
    # mining primitive, bypasses skill synthesis and crafting logic
    print(f"[DEBUG] Direct mining: {count} x {item_name}")
    success, events = self._direct_execute_gather(item_name, count)
    return success, events
```

---

# 🟦 **FILE 3 — skill_manager.py (if exists)**

If your SkillManager saves mining skills, prevent that.

Search for:

```python
if step.step_type == "primitive":
```

Add before saving:

```python
if "mineBlock" in program_code:
    print("[DEBUG] Not saving mining primitive as skill")
    return
```

This prevents junk functions like:

```
mineOakLogs
mineClayBlocks
mineOneWoodLog
```

from ever polluting your skill library.

---

# 🟦 **FILE 4 — voyager.py (final cleanup)**

Find any place that calls mining functions via ensure_skill.
Replace ALL:

```python
self.executor.ensure_skill(mine_skill_name, ...)
```

with:

```python
self.executor.direct_mine(block_type, count, task_type="mine")
```

This ensures mining is always:

### ✔ direct mining primitive

### ✔ no skill synthesis

### ✔ no dependency resolution

### ✔ no crafting recursion

### ✔ no LLM-wrapped functions

---

# 🎯 FINAL RESULT (AFTER CODER APPLIES THESE CHANGES)

### ✔ Mining never triggers crafting dependencies

### ✔ Crafting tasks dynamically re-synthesize outdated skills

### ✔ Mining tasks stay flat, simple, deterministic

### ✔ Skills remain exclusively for crafting (with recursive dependencies)

### ✔ No more polluted skill library with mineX functions

### ✔ Executor becomes a correct hierarchical task planner

### ✔ Coal-mining no longer inherits pickaxe-building chains

### ✔ Crafting remains self-updating as inventory changes

