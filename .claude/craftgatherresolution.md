# **CHANGE SPEC — Correct Craft-Then-Gather Dependency Resolution in ExecutorSkills**

## **Goal**

Modify the dependency-resolution logic in `ExecutorSkills.ensure_dependency()` so that **every missing dependency is resolved using this strict hierarchy**:

```
1. If the item is craftable → recursively ensure craft skill for that item
2. Else if the item is gatherable → mine its raw source block(s)
3. Else → fail
```

This ensures:

* Correct recursive dependency chains
* No attempts to craft raw materials (e.g., logs, ores)
* No attempts to mine crafted items (e.g., planks, sticks)
* Clean, minimal skill sequences containing the right primitives

---

# **Files Affected**

* `voyager/executor/executor_skills.py` 
* `voyager/executor/executor_utils.py`  (new function) 
* `voyager/executor/executor_actions.py` (no functional changes, but ensure JS call is safe)

---

# **Required Behavioral Outcome**

Given a craft request that fails due to missing dependencies:

```
craft sword
 → missing ['oak_planks', 'stick']
```

Resolution must proceed:

```
oak_planks:
    craft attempt fails → missing ['oak_log']
    oak_log:
        craft attempt has no recipe → not craftable
        gatherable? yes → mineBlock(oak_log)
    craft oak_planks → success
stick:
    craft stick → success
craft sword → success
```

The synthesized skill sequence:

```
mineBlock(oak_log)
craftItem(oak_planks)
craftItem(stick)
craftItem(wooden_sword)
```

---

# **SPECIFICATION – EXACT CODE CHANGES**

---

## **1. Add Craftability Check to ExecutorUtils**

Add this method to `executor_utils.py`:

```python
def is_craftable(self, item_name: str) -> bool:
    """
    Query mcData to determine if the item has any crafting recipes.
    """
    safe = item_name.replace("\\", "\\\\").replace("'", "\\'")
    code = f"""
const mcData = require('minecraft-data')(bot.version);
const recipes = mcData.recipes['{safe}'] || [];
bot.chat("CRAFTABLE:" + (recipes.length > 0 ? "yes" : "no"));
"""
    events = self.env.step(code=code, programs=self.skill_manager.programs)

    for etype, event in events:
        if etype == "onChat":
            msg = event.get("onChat", event) if isinstance(event, dict) else event
            if msg.startswith("CRAFTABLE:"):
                return msg.endswith("yes")

    return False
```

---

## **2. Modify ExecutorSkills.ensure_dependency() Resolution Order**

### Insert at the *very top* of `ensure_dependency()`:

```python
# Normalize dependency name
norm = self.utils.normalize_item_name(dep)
if isinstance(norm, dict):
    dep = norm["suggestions"][0]
else:
    dep = norm
```

---

### **PATCH: Replace existing gather-first logic with craft-first logic**

**Insert BEFORE `source_blocks = actions_executor.get_source_blocks_for_item(dep)`**:

```python
# ---- STEP 1: CRAFTABILITY CHECK (dominant path) ----
if self.utils.is_craftable(dep):
    dep_skill_name = f"craft{self.utils.to_camel_case(dep)}"
    print(f"[DEBUG] {dep} is craftable → ensuring skill {dep_skill_name}")

    # Known skill
    if dep_skill_name in self.skill_manager.skills:
        success, _ = actions_executor.execute_skill(dep_skill_name)
        if success and self.task_stack:
            self.task_stack[-1].execution_sequence.append(
                ExecutionStep("skill", dep_skill_name, [], success=True)
            )
        return success

    # Discover new craft skill
    success, _ = self.ensure_skill(
        dep_skill_name,
        depth=current_depth + 1,
        task_type=task_type,
        actions_executor=actions_executor
    )

    if success and self.task_stack:
        self.task_stack[-1].execution_sequence.append(
            ExecutionStep("skill", dep_skill_name, [], success=True)
        )
    return success
```

---

### **Existing gather logic stays**, but must now run only if craftability is FALSE.

After craftability block:

```python
# ---- STEP 2: GATHERABILITY CHECK (fallback path) ----
source_blocks = actions_executor.get_source_blocks_for_item(dep)

if source_blocks:
    for block in source_blocks[:3]:
        print(f"[DEBUG] {dep} is gatherable via {block}")
        success, _ = actions_executor.direct_execute_gather(block, count=1)

        if success:
            if self.task_stack:
                self.task_stack[-1].execution_sequence.append(
                    ExecutionStep("primitive", "mineBlock", [block, "1"], success=True)
                )
            return True

    print(f"[ERROR] Failed to gather {dep} from: {source_blocks[:3]}")
    return False
```

---

### Add final fallback:

```python
print(f"[ERROR] Cannot obtain dependency '{dep}' (not craftable, not gatherable)")
return False
```

---

## **3. Update get_source_blocks_for_item() Safety**

Modify your JS injector to escape item names and handle both dict and string events:

```python
safe = item_name.replace("\\", "\\\\").replace("'", "\\'")

code = f"""
try {{
  const {{ getSourceBlocksForItem }} = require('./voyager/control_primitives/getSourceBlocksForItem.js');
  const mcData = require('minecraft-data')(bot.version);
  const result = getSourceBlocksForItem('{safe}', mcData);
  bot.chat("SOURCE_BLOCKS:" + JSON.stringify(result));
}} catch (e) {{
  bot.chat("ERR:" + e.toString());
}}
"""
```

Add robust parsing:

```python
for etype, event in events:
    if etype == "onChat":
        msg = event.get("onChat", event) if isinstance(event, dict) else event
        if msg.startswith("SOURCE_BLOCKS:"):
            payload = msg.split("SOURCE_BLOCKS:", 1)[1].strip()
            return json.loads(payload)
```


# **6. Constraints**

* Do NOT modify `direct_execute_craft` or `direct_execute_gather` semantics.
* Do NOT modify the skill-manager interface.
* All recursion limits must remain intact.
* Implementation must remain synchronous on Python side using env.step.
