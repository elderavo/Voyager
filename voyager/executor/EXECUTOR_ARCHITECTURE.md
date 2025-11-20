## Executor Architecture Documentation

### Overview

The **Executor** is a parallel execution path that runs alongside the existing Action Agent in Voyager. It provides:

1. **Direct Primitive Execution**: Execute mineflayer primitives directly via HTTP without LLM overhead
2. **Recursive Dependency Resolution**: Automatically discover and learn crafting dependencies
3. **Skill Composition**: Synthesize composite skills from successful execution sequences
4. **Zero Breaking Changes**: Existing Action Agent flow remains completely intact

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Voyager Class                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐              ┌──────────────────┐   │
│  │  Action Agent    │              │    Executor      │   │
│  │  (LLM-based)     │              │  (Direct Exec)   │   │
│  └────────┬─────────┘              └────────┬─────────┘   │
│           │                                 │             │
│           │  rollout()                     │ executor_   │
│           │                                │ craft()     │
│           ▼                                 ▼             │
│  ┌──────────────────┐              ┌──────────────────┐   │
│  │ Generate JS Code │              │ Direct Primitive │   │
│  │ via LLM          │              │ Execution        │   │
│  └────────┬─────────┘              └────────┬─────────┘   │
│           │                                 │             │
│           │                                 │             │
│           └───────┬─────────────────────────┘             │
│                   ▼                                       │
│         ┌───────────────────┐                            │
│         │  VoyagerEnv.step  │                            │
│         │  (HTTP to         │                            │
│         │   Mineflayer)     │                            │
│         └─────────┬─────────┘                            │
│                   │                                       │
└───────────────────┼───────────────────────────────────────┘
                    │
                    ▼
          ┌──────────────────┐
          │  Mineflayer Bot  │
          │  (JavaScript)    │
          └──────────────────┘
```

---

## Core Components

### 1. Executor Class (`voyager/executor/executor.py`)

**Responsibilities:**
- Execute existing skills via `execute_skill(skill_name)`
- Recursively discover new skills via `ensure_skill(skill_name)`
- High-level crafting via `craft_item(item_name)`
- Parse dependencies from mineflayer chat feedback
- Synthesize JavaScript skills from execution sequences

**Key Methods:**

#### `execute_skill(skill_name: str) -> (success, events)`
Executes an existing JavaScript skill from the skill library.

```python
success, events = executor.execute_skill("craftPlanks")
```

#### `ensure_skill(skill_name: str, depth: int = 0) -> (success, execution_sequence)`
Ensures a skill exists, discovering it recursively if needed.

**Discovery Process:**
1. Check if skill already exists → return immediately
2. Attempt direct craftItem execution
3. If fails, parse missing dependencies from chat
4. For each dependency:
   - If gatherable primitive → execute mineBlock
   - If known skill → execute existing skill
   - If unknown skill → **RECURSE** to discover it
5. Retry craft after dependencies satisfied
6. Synthesize composite skill from execution sequence
7. Register skill in skill library

```python
success, steps = executor.ensure_skill("craftSticks", depth=0)
# Discovers that sticks need planks, planks need logs
# Synthesizes: [mineBlock(spruce_log), craftItem(planks), craftItem(stick)]
```

#### `craft_item(item_name: str) -> (success, events)`
High-level helper that combines ensure_skill + execute_skill.

```python
success, events = executor.craft_item("wooden_pickaxe")
# Handles entire dependency tree automatically
```

---

### 2. Data Structures

#### `ExecutionStep`
Records a single execution step.

```python
@dataclass
class ExecutionStep:
    step_type: str  # "primitive" or "skill"
    name: str       # e.g., "mineBlock", "craftPlanks"
    args: List[str] # e.g., ["oak_log", "1"]
    success: bool
```

#### `SkillDiscoveryTask`
Tracks state during recursive skill discovery.

```python
@dataclass
class SkillDiscoveryTask:
    skill_name: str                          # e.g., "craftSticks"
    item_name: str                           # e.g., "stick"
    depth: int                               # Recursion depth
    parent_task: Optional[str]               # Parent skill name
    execution_sequence: List[ExecutionStep] # Steps executed
    missing_dependencies: List[str]          # Items needed
    status: str                              # "pending", "in_progress", "completed", "failed"
```

---

### 3. Integration with Voyager

**In `voyager.py`:**

```python
# Initialize Executor alongside existing agents
self.executor = Executor(
    env=self.env,
    skill_manager=self.skill_manager,
    ckpt_dir=ckpt_dir,
    max_recursion_depth=5,
)

# New method for executor-based crafting
def executor_craft(self, item_name: str) -> Dict:
    """Execute crafting using Executor (parallel to rollout)"""
    success, events = self.executor.craft_item(item_name)
    return info_dict

# Modified learn() with optional executor mode
def learn(self, reset_env=True, use_executor=False):
    while True:
        task = curriculum.propose_next_task()

        if use_executor and task.startswith("Craft "):
            # Use Executor path
            info = self.executor_craft(item_name)
        else:
            # Use existing Action Agent path
            info = self.rollout(task, context)

        # Rest of learn() unchanged
```

---

## Usage Examples

### Example 1: Direct Executor Usage

```python
from voyager import Voyager

voyager = Voyager(
    mc_port=25565,
    openai_api_key="sk-...",
    ckpt_dir="ckpt"
)

# Craft planks using executor
info = voyager.executor_craft("spruce_planks")
print(f"Success: {info['success']}")
```

### Example 2: Executor Mode in Learning Loop

```python
# Use executor for all crafting tasks
voyager.learn(reset_env=True, use_executor=True)
# Curriculum proposes "Craft sticks"
# → Executor handles recursively: logs → planks → sticks
```

### Example 3: Mixed Mode

```python
# Use executor only for specific tasks
task = curriculum.propose_next_task()

if task == "Craft wooden_pickaxe":
    info = voyager.executor_craft("wooden_pickaxe")
else:
    info = voyager.rollout(task, context)
```

---

## Recursive Discovery Example

**Task**: Craft wooden pickaxe

**Execution Flow**:

```
ensure_skill("craftWoodenPickaxe")
├─ Try craftItem(wooden_pickaxe)
│  └─ FAIL: need stick, planks
├─ ensure_dependency("stick")
│  ├─ ensure_skill("craftStick")
│  │  ├─ Try craftItem(stick)
│  │  │  └─ FAIL: need planks
│  │  ├─ ensure_dependency("planks")
│  │  │  ├─ ensure_skill("craftPlanks")
│  │  │  │  ├─ Try craftItem(planks)
│  │  │  │  │  └─ FAIL: need oak_log
│  │  │  │  ├─ ensure_dependency("oak_log")
│  │  │  │  │  └─ mineBlock(oak_log, 1) ✓
│  │  │  │  ├─ Retry craftItem(planks) ✓
│  │  │  │  └─ Synthesize craftPlanks: [mineBlock(oak_log), craftItem(planks)]
│  │  │  └─ Execute craftPlanks ✓
│  │  ├─ Retry craftItem(stick) ✓
│  │  └─ Synthesize craftStick: [craftPlanks, craftItem(stick)]
│  └─ Execute craftStick ✓
├─ ensure_dependency("planks")
│  └─ Execute craftPlanks ✓ (already exists)
├─ Retry craftItem(wooden_pickaxe) ✓
└─ Synthesize craftWoodenPickaxe: [craftStick, craftPlanks, craftItem(wooden_pickaxe)]
```

**Result**: Three new skills saved:
1. `craftPlanks` → `[mineBlock(oak_log, 1), craftItem(planks, 1)]`
2. `craftStick` → `[craftPlanks(), craftItem(stick, 1)]`
3. `craftWoodenPickaxe` → `[craftStick(), craftPlanks(), craftItem(wooden_pickaxe, 1)]`

---

## Dependency Parsing

The Executor parses dependencies from mineflayer chat messages:

**Chat Message**:
```
"I cannot make stick because I need: 2 more planks"
```

**Parsed**:
```python
["planks"]
```

**Dependency Classification**:

1. **Gatherable Primitive**: Items obtained via `mineBlock`
   - Logs, stone, ores, dirt, etc.
   - Listed in `executor.gatherable_primitives`

2. **Known Skill**: Skill exists in skill library
   - Check `skill_name in skill_manager.skills`
   - Execute directly

3. **Unknown Skill**: Needs to be discovered
   - Trigger recursive `ensure_skill()`

---

## Skill Synthesis

After successful recursive discovery, the Executor synthesizes a JavaScript skill:

**Execution Sequence**:
```python
[
    ExecutionStep("primitive", "mineBlock", ["oak_log", "1"], True),
    ExecutionStep("primitive", "craftItem", ["planks", "1"], True),
]
```

**Generated JavaScript**:
```javascript
async function craftPlanks(bot) {
  await mineBlock(bot, 'oak_log', 1);
  await craftItem(bot, 'planks', 1);
}
```

**Registration**: Skill is added to `skill_manager.skills` and saved to disk.

---

## Benefits vs Action Agent

| Feature | Action Agent | Executor |
|---------|-------------|----------|
| **Execution Speed** | Slow (LLM call per attempt) | Fast (direct primitives) |
| **Token Cost** | High (multiple LLM calls) | Zero (no LLM) |
| **Reliability** | Depends on LLM quality | Deterministic |
| **Dependency Handling** | Manual retries | Automatic recursion |
| **Skill Composition** | LLM-generated | Programmatic |
| **Code Quality** | Variable | Consistent |

---

## Configuration

**Executor Parameters**:

```python
Executor(
    env=voyager_env,              # VoyagerEnv instance
    skill_manager=skill_manager,  # SkillManager instance
    ckpt_dir="ckpt",              # Skill storage directory
    max_recursion_depth=5,        # Max dependency depth
)
```

**Gatherable Primitives**:
Configure which items can be obtained via `mineBlock` by modifying:

```python
executor.gatherable_primitives = {
    "oak_log", "spruce_log", "stone", "coal_ore", ...
}
```

---

## Error Handling

**Recursion Depth Limit**:
```python
if depth > max_recursion_depth:
    return False, []
```

**Execution Failures**:
- Parse chat for errors
- Return `(False, [])` to unwind recursion
- Parent task marked as failed

**Missing Dependencies**:
- If no dependencies parsed from chat → fail
- Cannot proceed without clear next steps

---

## Testing

**Run Tests**:
```bash
python test_executor.py --mode executor
```

**Test Cases**:
1. **Simple Craft**: Craft planks (requires gathering logs)
2. **One-Level Recursion**: Craft sticks (needs planks → logs)
3. **Two-Level Recursion**: Craft wooden pickaxe (needs sticks → planks → logs)

---

## Future Enhancements

1. **Inventory Awareness**: Check inventory before gathering
2. **Quantity Optimization**: Gather exact amounts needed
3. **Parallel Dependency Resolution**: Solve independent deps in parallel
4. **Caching**: Cache failed attempts to avoid retrying impossible crafts
5. **Smarter Primitive Detection**: Auto-detect which items are gatherable
6. **Multi-step Primitives**: Support smeltItem, killMob recursion

---

## Compatibility

**Fully Compatible With**:
- Existing Action Agent flow
- Skill Manager
- Curriculum Agent
- Critic Agent
- All existing skills

**No Breaking Changes**:
- Executor is opt-in via `use_executor=True`
- Default behavior unchanged
- Existing checkpoints still work

---

## Summary

The Executor provides a **fast, deterministic, zero-cost** alternative to LLM-based crafting while maintaining full compatibility with the existing Voyager architecture. It implements the recursive crafting concept from `crafting_concept.md` without breaking any existing functionality.

**Key Innovation**: Automatic dependency discovery and skill composition through recursive primitive execution.
