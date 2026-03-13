# Plan: MethodRegistry

**Module:** `voyager/production/method_registry.py`

---

## Overview

The MethodRegistry maps items to how they can be produced. It answers "how do I get X?" without doing any planning or execution. It's a DATA LAYER — a lookup table loaded from minecraft-data, not a polymorphic class hierarchy.

This replaces the deleted `RecipeFacts` class and the `ProductionMethod` ABC from the earlier (over-engineered) spec.

---

## 1. MethodInfo Dataclass

```python
from dataclasses import dataclass, field

@dataclass
class MethodInfo:
    type: str                      # "craft", "smelt", "mine", "kill"
    inputs: list[str] = field(default_factory=list)  # items/resources needed
    input_quantities: dict[str, int] = field(default_factory=dict)  # item -> count needed
    workspace: str | None = None   # "crafting_table", "furnace", None
    tool: str | None = None        # minimum tool required (e.g., "stone_pickaxe")
    output_qty: int = 1            # how many items produced per execution
```

### Notes
- `inputs` is a flat list of unique item names needed
- `input_quantities` maps each input to how many are needed (e.g., `{"oak_log": 1}` for planks)
- `workspace` is None for: mining, killing, 2x2 crafting recipes (player inventory)
- `tool` is None for most things, set for mining blocks that need a specific tier

---

## 2. MethodRegistry Class

```python
class MethodRegistry:
    def __init__(self, env: VoyagerEnv):
        self.recipes: dict[str, list[dict]] = {}     # item -> crafting recipes from minecraft-data
        self.mineable: dict[str, str | None] = {}    # block -> minimum tool (None = hand)
        self.smeltable: dict[str, str] = {}          # output_item -> input_item
        self.mob_drops: dict[str, str] = {}          # item -> mob that drops it
        self._load_data(env)
```

---

## 3. Data Loading: `_load_data(env)`

### Crafting recipes
```python
registry_data = env.get_registry("recipes")
# Parse into self.recipes dict
# Key: output item name
# Value: list of recipe dicts, each with:
#   - inputs: list of {item: str, count: int}
#   - output_qty: int
#   - needs_table: bool (3x3 vs 2x2)
```

### Mineable blocks
```python
blocks_data = env.get_registry("blocks")
# Parse into self.mineable dict
# Key: block name (which is also the dropped item in most cases)
# Value: minimum tool needed (None if hand-mineable)
# Use block.harvestTools field from minecraft-data
```

### Smelting recipes
Minecraft-data has smelting recipes but they may not be exposed via the `/registry` endpoint. Two options:
1. **Preferred:** Add a "smelting" registry type to the mineflayer server's `/registry` endpoint
2. **Fallback:** Hardcode the common smelting recipes:
```python
self.smeltable = {
    "iron_ingot": "iron_ore",
    "gold_ingot": "gold_ore",
    "glass": "sand",
    "stone": "cobblestone",
    "cooked_beef": "beef",
    "cooked_porkchop": "porkchop",
    "cooked_chicken": "chicken",
    "brick": "clay_ball",
    "charcoal": "oak_log",  # any log works
    "smooth_stone": "stone",
    "cooked_mutton": "mutton",
    "cooked_cod": "cod",
    "cooked_salmon": "salmon",
}
```

### Mob drops
Hardcoded to start (minecraft-data loot tables are complex):
```python
self.mob_drops = {
    "leather": "cow",
    "beef": "cow",
    "porkchop": "pig",
    "chicken": "chicken",
    "feather": "chicken",
    "wool": "sheep",
    "mutton": "sheep",
    "string": "spider",
    "spider_eye": "spider",
    "bone": "skeleton",
    "arrow": "skeleton",
    "rotten_flesh": "zombie",
    "ender_pearl": "enderman",
    "blaze_rod": "blaze",
    "gunpowder": "creeper",
    "ghast_tear": "ghast",
    "slime_ball": "slime",
}
```

---

## 4. Key Methods

### `get_methods(item: str) -> list[MethodInfo]`

Returns all known ways to produce `item`, ordered by priority:

```python
def get_methods(self, item: str) -> list[MethodInfo]:
    methods = []

    # 1. Crafting (highest priority for craftable items)
    if item in self.recipes:
        for recipe in self.recipes[item]:
            methods.append(MethodInfo(
                type="craft",
                inputs=list(recipe["input_quantities"].keys()),
                input_quantities=recipe["input_quantities"],
                workspace="crafting_table" if recipe["needs_table"] else None,
                output_qty=recipe["output_qty"],
            ))

    # 2. Smelting
    if item in self.smeltable:
        raw = self.smeltable[item]
        methods.append(MethodInfo(
            type="smelt",
            inputs=[raw, "coal"],  # fuel needed
            input_quantities={raw: 1, "coal": 1},
            workspace="furnace",
        ))

    # 3. Mining
    if item in self.mineable:
        methods.append(MethodInfo(
            type="mine",
            inputs=[],
            tool=self.mineable[item],
            output_qty=1,
        ))

    # 4. Mob killing
    if item in self.mob_drops:
        mob = self.mob_drops[item]
        methods.append(MethodInfo(
            type="kill",
            inputs=[],
            output_qty=1,
        ))

    return methods
```

### `get_recipe(item: str) -> list[dict] | None`

Returns crafting recipes for item, or None.

### `is_mineable(item: str) -> bool`

Returns `item in self.mineable`.

### `get_smelt_input(item: str) -> str | None`

Returns `self.smeltable.get(item)`.

### `get_tool_for_block(block: str) -> str | None`

Returns minimum tool tier needed to harvest block.

### `normalize_item_name(name: str) -> str | None`

Normalizes free-form item names to minecraft-data canonical form:
- Lowercase, replace spaces with underscores
- Handle plurals: "sticks" → "stick", "planks" stays "planks"
- Validate against known items
- Returns None if unrecognized

---

## 5. Recipe Parsing Details

Minecraft-data recipe format (from `/registry` endpoint) needs translation:

```javascript
// minecraft-data recipe for oak_planks:
{
  "inShape": [["oak_log"]],  // or null for shapeless
  "ingredients": null,        // for shapeless recipes
  "result": { "id": 5, "count": 4 }
}
```

The parser needs to:
1. Resolve item IDs to names (using items registry)
2. Count input quantities from inShape grid
3. Determine if recipe needs crafting table (inShape > 2x2)
4. Handle both shaped (`inShape`) and shapeless (`ingredients`) recipes

---

## 6. Block-to-Item Mapping

Some blocks drop different items than their block name:
- `stone` → drops `cobblestone` (unless silk touch)
- `oak_leaves` → may drop `apple`, `stick`, `oak_sapling`
- `iron_ore` → drops `iron_ore` (raw_iron in 1.17+)
- `coal_ore` → drops `coal`
- `diamond_ore` → drops `diamond`
- `lapis_ore` → drops `lapis_lazuli`
- `redstone_ore` → drops `redstone`

This mapping affects the `mineable` dict — the key should be the DROPPED ITEM, not the block name, since the Resolver asks "how do I get cobblestone?" not "how do I get stone block?"

For simplicity in v1: assume block name = dropped item for most blocks, add exceptions for the common cases above.

---

## 7. Design Constraints

- **Read-only after init.** Load once, never mutate.
- **No execution logic.** This is a lookup table, not an executor.
- **No planning logic.** The Resolver uses this data but the registry doesn't plan.
- **No LLM calls.** Pure data.
- **No skill awareness.** The Resolver checks SkillManager separately; the registry only knows about game mechanics.
- **No ProductionMethod ABC.** MethodInfo is a flat dataclass, not a polymorphic class.

---

## 8. Integration Points

- **Loaded by:** `Voyager.__init__()` (lazy, after env connects)
- **Used by:** `Resolver.resolve()` to look up how to produce prerequisites
- **Data source:** `VoyagerEnv.get_registry()` which calls mineflayer's `/registry` endpoint
- **NOT used by:** Executor (it calls primitives directly), SkillManager, ActionAgent

---

## 9. Mineflayer `/registry` Endpoint

The existing endpoint in `index.js` needs to support returning recipe data in a parseable format. Check what it currently returns and potentially add:
- Item ID → name mapping (if not already returned)
- Recipe data with resolved item names (not just IDs)
- Block harvest tool requirements

If the endpoint doesn't return enough data, the fallback is to load `minecraft-data` directly via the npm package in the Node server and expose a richer endpoint.
