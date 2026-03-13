# Plan: SkillStore Upgrades

**Module:** Modifications to `voyager/agents/skill.py` (SkillManager) + new `voyager/production/skill_codegen.py`

---

## Overview

The existing SkillManager needs minor upgrades to support the structured production path. The changes are:
1. Add `find_skill_by_output()` — lookup by what a skill produces
2. Add `get_all_producible_items()` — quick check for resolver
3. Document the recipe schema
4. Add JS code generation utility for structured skills

The existing SkillManager stays where it is, keeps its current interface, and gets 3 new methods. No SkillGraph DAG, no transactional writes, no force_relearn.

---

## 1. New Method: `find_skill_by_output(item_name)`

```python
def find_skill_by_output(self, item_name: str) -> tuple[str, dict] | None:
    """
    Find a skill that produces the given item.

    Args:
        item_name: minecraft-data canonical item name (e.g., "oak_planks")

    Returns:
        (skill_name, skill_data) tuple, or None if no skill produces this item.
    """
    for skill_name, skill_data in self.skills.items():
        recipe = skill_data.get("recipe")
        if recipe and recipe.get("output") == item_name:
            return (skill_name, skill_data)
    return None
```

### Notes
- This replaces `HTNOrchestrator.find_skill_for_output()` which does the exact same thing
- Linear scan is fine — skill count is small (tens to low hundreds)
- Called by the Resolver to check "do we already know how to make X?"

---

## 2. New Method: `get_all_producible_items()`

```python
def get_all_producible_items(self) -> set[str]:
    """
    Returns set of all item names that have a producing skill.
    Used by Resolver for quick "can we already make this?" checks.
    """
    items = set()
    for skill_data in self.skills.values():
        recipe = skill_data.get("recipe")
        if recipe and recipe.get("output"):
            items.add(recipe["output"])
    return items
```

### Notes
- Convenience method for the Resolver
- Could be cached if performance matters, but with small skill counts it won't

---

## 3. New Method: `find_skill_by_name(skill_name)`

```python
def find_skill_by_name(self, skill_name: str) -> dict | None:
    """Lookup skill data by name. Returns None if not found."""
    return self.skills.get(skill_name)
```

Trivial convenience wrapper.

---

## 4. Recipe Schema (documentation, no code changes)

The `recipe` field in skill data already exists. Standardize the schema:

```python
recipe = {
    "output": "oak_planks",           # minecraft-data item name produced
    "output_qty": 4,                  # items produced per execution
    "inputs": ["oak_log"],            # list of input item names
    "input_quantities": {             # NEW: detailed input counts
        "oak_log": 1
    },
    "workspace": "crafting_table",    # or None for 2x2 / hand-craftable
    "method": "craft",               # "craft", "smelt", etc.
}
```

### Backward compatibility
- Existing skills that don't have `input_quantities` still work — code should handle missing keys with `.get()` defaults
- Existing skills that don't have `method` default to `"craft"`
- The `inputs` list (flat, no quantities) is kept for backward compat

---

## 5. JS Code Generation for Structured Skills

New utility module: `voyager/production/skill_codegen.py`

```python
def generate_skill_code(skill_name: str, plan_nodes: list[PlanNode], skill_manager) -> str:
    """
    Generate JavaScript function code from completed plan nodes.

    For single-primitive skills (most common):
        async function craftOakPlanks(bot) {
            await craftItem(bot, "oak_planks", 1);
        }

    For multi-step skills with dependencies:
        async function craftWoodenPickaxe(bot) {
            await obtainOakPlanks(bot);
            await obtainStick(bot);
            await craftItem(bot, "wooden_pickaxe", 1);
        }
    """
```

### Algorithm

```python
def generate_skill_code(skill_name, plan_nodes, skill_manager):
    lines = []

    for node in plan_nodes:
        if not node.save_as_skill:
            # Leaf nodes (mine, kill, place) → emit primitive call directly
            code = _node_to_primitive_call(node)
            if code:
                lines.append(f"  {code}")
        else:
            # Check if this sub-skill already exists
            sub_skill_name = _node_to_skill_name(node)
            existing = skill_manager.find_skill_by_output(node.args.get("item", ""))
            if existing:
                # Call existing skill
                lines.append(f"  await {existing[0]}(bot);")
            else:
                # Emit primitive call (skill will be created separately)
                code = _node_to_primitive_call(node)
                if code:
                    lines.append(f"  {code}")

    body = "\n".join(lines)
    return f"async function {skill_name}(bot) {{\n{body}\n}}"


def _node_to_primitive_call(node):
    method = node.method
    args = node.args

    if method == "craft":
        return f'await craftItem(bot, "{args["item"]}", {args.get("qty", 1)});'
    elif method == "mine":
        return f'await mineBlock(bot, "{args["block"]}", {args.get("qty", 1)});'
    elif method == "smelt":
        return f'await smeltItem(bot, "{args["item"]}", {args.get("qty", 1)});'
    elif method == "kill":
        return f'await killMob(bot, "{args["mob"]}", {args.get("qty", 1)});'
    elif method == "place":
        return f'await placeItem(bot, "{args["item"]}", bot.entity.position);'
    elif method == "skill":
        return f'await {args["skill_name"]}(bot);'
    return None


def _node_to_skill_name(node):
    """Generate camelCase skill name from a PlanNode."""
    if node.method in ("craft", "smelt"):
        item = node.args.get("item", "unknown")
        parts = item.split("_")
        camel = "".join(p.capitalize() for p in parts)
        verb = node.method
        return f"{verb}{camel}"
    return None
```

---

## 6. What NOT to Change

| Thing | Why not |
|-------|---------|
| SkillGraph / DAG | Flat dict + recipe metadata is sufficient |
| VectorDB / retrieval | Works fine as-is |
| LLM skill description generation | Works fine as-is |
| Transactional writes | Over-engineered for current scale |
| Force relearn / versioning | Not needed yet |
| Rename SkillManager | Stays where it is, same name |
| `add_new_skill()` | Already handles `recipe` field — no changes needed |
| `retrieve_skills()` | Unchanged |
| `programs` property | Unchanged |

---

## 7. Integration Points

| Who calls | What | Why |
|-----------|------|-----|
| `Resolver` | `find_skill_by_output()` | Check if we already know how to make an item |
| `Resolver` | `get_all_producible_items()` | Quick set membership check |
| `Voyager._save_structured_skills()` | `add_new_skill()` | Save after structured execution success |
| `Voyager._save_structured_skills()` | `generate_skill_code()` | Generate JS for the saved skill |
| `PlanExecutor` | `programs` property | Get all available JS code for env.step() |

---

## 8. Testing Notes

- `find_skill_by_output("oak_planks")` should return the skill if one exists with `recipe.output == "oak_planks"`
- `find_skill_by_output("nonexistent")` should return `None`
- `get_all_producible_items()` should return a set matching all skills with recipe.output
- Generated JS code should be syntactically valid (testable with Babel parser in code_analyzer.py)
- Skills saved via structured path should be retrievable via existing `retrieve_skills()` semantic search
