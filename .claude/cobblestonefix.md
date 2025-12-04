Below is a **tight, implementation-ready engineering spec patch document** describing the required architectural change to fix mining dependency resolution.
Short, direct, no fluff.

---

# **ENGINEERING SPEC – PATCH: Drop-Based Mining Dependency Resolution**

## **1. Problem Statement**

The current dependency resolver uses a hard-coded Python list (`gatherable_primitives`) and suffix heuristics (`_log`, `_ore`) to decide whether a missing item is “gatherable.”
This causes incorrect mining behavior such as:

* Attempting `mineBlock("cobblestone")` instead of `mineBlock("stone")`
* Treating **item names** as **block names**
* Failing on items like `coal`, `emerald`, `raw_iron`, etc.

The architecture incorrectly conflates **item space** and **block space**, leading to unstable skill synthesis and invalid primitives.

---

## **2. Design Goal**

Replace all heuristic-based gathering logic with a **single authoritative rule** derived from mcData:

> **An item is gatherable iff Minecraft defines at least one block that drops it.**

This ensures:

* Version correctness
* Accurate primitive generation
* Stable reusable skills
* No hard-coded physics rules in Python

---

## **3. New Core Invariant**

### **Invariant:**

**Before emitting any `mineBlock()` primitive, resolve the dependency using mcData:**

```
dep → getSourceBlocksForItem(dep) → [valid source blocks]
```

If `source_blocks` is:

* **non-empty** → the item is gatherable
* **empty** → the item must be crafted or synthesized via another skill

This eliminates `gatherable_primitives` entirely.

---

## **4. New JS Helper Module**

### File: `getSourceBlocksForItem.js`

**Purpose:** Return all blocks that drop the input item.

```js
function getSourceBlocksForItem(itemName, mcData) {
    const targetItem = mcData.itemsByName[itemName];
    if (!targetItem) return [];

    const valid = [];
    for (const block of Object.values(mcData.blocks)) {
        if (block?.drops?.includes(targetItem.id)) {
            valid.push(block.name);
        }
    }

    return valid;   // e.g., ["stone"] for "cobblestone"
}

module.exports = { getSourceBlocksForItem };
```

---

## **5. Required Python Integration Points**

### **5.1 Remove hard-coded gatherable list entirely**

Delete:

```python
self.gatherable_primitives = { ... }
```

Delete logic:

```python
if dep in self.gatherable_primitives or dep.endswith("_log") or dep.endswith("_ore"):
```

---

## **5.2 Patch: ensure_dependency() mining branch**

### **Before**

```python
if dep in self.gatherable_primitives or dep.endswith("_log") or dep.endswith("_ore"):
    print("Gathering primitive:", dep)
    success, events = actions_executor.direct_execute_gather(dep, count=1)
```

### **After (Correct Patch)**

```python
source_blocks = actions_executor.get_source_blocks_for_item(dep)

if source_blocks:
    chosen = source_blocks[0]  # placeholder selection policy
    print(f"\033[36mGathering primitive: {dep} via block {chosen}\033[0m")
    success, events = actions_executor.direct_execute_gather(chosen, count=1)

    if success and self.task_stack:
        step = ExecutionStep("primitive", "mineBlock", [chosen, "1"], success=True)
        self.task_stack[-1].execution_sequence.append(step)

    return success
```

---

## **6. Changes to Action Executor**

### Add a Python wrapper:

```python
def get_source_blocks_for_item(self, item):
    return self.env.call_js_function("getSourceBlocksForItem", item)
```

---

## **7. Optional Enhancement (Recommended)**

Embed the same logic inside **mineBlock.js** so skills that contain old forms:

```
await mineBlock(bot, 'cobblestone')
```

still resolve correctly via fallback to `stone`.

This adds backwards compatibility and stabilizes learned skills.

---

## **8. Acceptance Criteria**

### Functional

* Bot never emits `mineBlock(dep)` unless `dep` is a real block name present in the world.
* All mined items come from correct mcData-derived source blocks.
* No incorrect primitives appear in synthesized skills.
* Missing dependency resolution *never* relies on hard-coded item lists.

### Behavioral

Given craft failure:

```
Missing: cobblestone
```

The system must:

1. Call `getSourceBlocksForItem("cobblestone")`
2. Receive: `["stone"]`
3. Emit primitive: `mineBlock("stone")`
4. Correctly satisfy dependency and continue craft.

---

## **9. Risks & Mitigations**

| Risk                                                   | Mitigation                                                                    |
| ------------------------------------------------------ | ----------------------------------------------------------------------------- |
| Incorrect selection among multiple valid source blocks | Use heuristic: “first entry” initially; later upgrade to nearest-block search |
| Extra JS–Python roundtrip                              | Cache source-block lists in Python for repeated queries                       |
| Skills previously recorded with wrong block names      | Mitigated if mineBlock has fallback resolution                                |

---

## **10. Rollout Plan**

1. Add JS helper module
2. Patch Python dependency logic
3. Remove gatherable_primitives
4. Add ActionExecutor wrapper
5. Run integration tests on:

   * wood → planks
   * planks → sticks
   * sticks → tools
   * stone tools
6. Enable fallback in mineBlock.js (optional but recommended)
7. Final end-to-end test: craft wooden_pickaxe → stone_pickaxe → furnace

---

If you want, I can produce the exact code patches for each file in unified diff (`git diff`) format so you can paste directly into your repo.
