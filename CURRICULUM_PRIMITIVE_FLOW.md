# Curriculum → Primitive Direct Path

## Problem: Unnecessary LLM Calls for Trivial Tasks

### Current Wasteful Flow:
```
Curriculum: "Mine 1 wood log"
    ↓
Action Agent: [LLM call] Generates:
    async function mineOneWoodLog(bot) {
        await mineBlock(bot, 'oak_log', 1);
    }
    ↓
HTN: Validates → Decomposes → Queues: mineBlock(bot, 'oak_log', 1)
    ↓
Executes the primitive

WASTE: 1 LLM call + function generation + decomposition = same result as direct primitive call
```

### What SHOULD Happen:
```
Curriculum: "Mine 1 wood log"
    ↓
Curriculum recognizes this maps directly to: mineBlock(bot, 'oak_log', 1)
    ↓
HTN: Queues primitive directly (no Action Agent, no decomposition)
    ↓
Executes

SAVINGS: 1 LLM call saved, 5-10 seconds saved, simpler code path
```

---

## Solution Options

### Option 1: Curriculum Bot Direct Primitive Mapping (RECOMMENDED)
**Where:** Curriculum agent decides whether to use Action Agent or queue primitive directly

**Implementation:**

Add to [voyager/agents/curriculum.py](voyager/agents/curriculum.py):

```python
class CurriculumAgent:
    def __init__(self, ...):
        # ...existing code...

        # Primitive task templates with argument extraction patterns
        self.primitive_templates = {
            # Mining tasks
            r"mine (\d+) (.+?)(?:s|logs?|blocks?)?$": lambda m: {
                "primitive": "mineBlock",
                "args": ["bot", f"'{self._normalize_block_name(m.group(2))}'", m.group(1)]
            },
            r"collect (\d+) (.+?)(?:s)?$": lambda m: {
                "primitive": "mineBlock",
                "args": ["bot", f"'{self._normalize_block_name(m.group(2))}'", m.group(1)]
            },
            r"obtain (\d+) (.+?)(?:s)?$": lambda m: {
                "primitive": "mineBlock",
                "args": ["bot", f"'{self._normalize_block_name(m.group(2))}'", m.group(1)]
            },

            # Crafting tasks
            r"craft (\d+) (.+?)(?:s)?$": lambda m: {
                "primitive": "craftItem",
                "args": ["bot", f"'{self._normalize_item_name(m.group(2))}'", m.group(1)]
            },

            # Smelting tasks
            r"smelt (\d+) (.+?)(?:s)?$": lambda m: {
                "primitive": "smeltItem",
                "args": ["bot", f"'{self._normalize_item_name(m.group(2))}'", m.group(1)]
            },

            # Killing tasks
            r"kill (\d+) (.+?)(?:s)?$": lambda m: {
                "primitive": "killMob",
                "args": ["bot", f"'{m.group(2)}'", m.group(1)]
            },
        }

    def _normalize_block_name(self, name):
        """Convert 'wood log' → 'oak_log', 'stone' → 'stone', etc."""
        # Special cases
        if 'wood' in name.lower() or 'log' in name.lower():
            return 'oak_log'  # Default to oak
        return name.lower().replace(' ', '_')

    def _normalize_item_name(self, name):
        """Convert item names to minecraft IDs"""
        return name.lower().replace(' ', '_')

    def task_matches_primitive(self, task):
        """
        Check if task can be handled by a single primitive call.

        Returns:
            dict or None: {"primitive": str, "args": list} if matches, None otherwise
        """
        task_lower = task.lower().strip()

        for pattern, extractor in self.primitive_templates.items():
            match = re.match(pattern, task_lower)
            if match:
                return extractor(match)

        return None

    def propose_next_task(self, events, chest_observation, max_retries):
        """
        Propose the next task.

        Returns:
            tuple: (task, context, primitive_mapping)
                primitive_mapping is None if task needs Action Agent,
                or dict with {"primitive": str, "args": list} if direct primitive
        """
        # ... existing LLM call to get task ...

        task = curriculum_response['task']
        context = curriculum_response['context']

        # Check if this task maps directly to a primitive
        primitive_mapping = self.task_matches_primitive(task)

        if primitive_mapping:
            print(f"\033[33m[Curriculum] Task '{task}' maps directly to primitive: "
                  f"{primitive_mapping['primitive']}({', '.join(primitive_mapping['args'])})\033[0m")

        return task, context, primitive_mapping
```

Then update [voyager/voyager.py](voyager/voyager.py) rollout:

```python
def rollout(self, *, task, context, reset_env=True):
    self.reset(task=task, context=context, reset_env=reset_env)

    # Check if curriculum provided a direct primitive mapping
    if hasattr(self, '_primitive_mapping') and self._primitive_mapping:
        print(f"\033[36m[Voyager] Skipping Action Agent - using direct primitive\033[0m")

        # Queue the primitive directly
        prim = self._primitive_mapping
        self.htn_orchestrator.task_queue.push(Task(
            action="primitive",
            payload={
                "function": prim['primitive'],
                "args": prim['args'],
                "skill": task,  # Use task name as skill name
                "line": 0
            },
            parent="curriculum"
        ))

        # Execute the primitive
        success, events, error = self.htn_orchestrator.execute_queued_tasks()

        # Check success with critic
        if success:
            success, critique = self.critic_agent.check_task_success(
                events=events,
                task=task,
                context=context,
                chest_observation=self.action_agent.render_chest_observation(),
                max_retries=5,
            )

        info = {
            "task": task,
            "success": success,
            "conversations": [],
            "primitive_direct": True
        }

        return None, 0, True, info

    # Normal flow - use Action Agent
    while True:
        messages, reward, done, info = self.step()
        if done:
            break
    return messages, reward, done, info

def learn(self, reset_env=True):
    # ... existing reset code ...

    while True:
        if self.recorder.iteration > self.max_iterations:
            break

        # Get task from curriculum (now returns primitive mapping too)
        task, context, primitive_mapping = self.curriculum_agent.propose_next_task(
            events=self.last_events,
            chest_observation=self.action_agent.render_chest_observation(),
            max_retries=5,
        )

        # Store primitive mapping for rollout
        self._primitive_mapping = primitive_mapping

        # ... rest of existing code ...
```

**Pros:**
- ✅ Curriculum decides complexity → correct agent
- ✅ Saves LLM calls for 50%+ of early tasks
- ✅ Faster execution (no Action Agent roundtrip)
- ✅ Simpler code path for simple tasks

**Cons:**
- ⚠️ Requires pattern matching (regex)
- ⚠️ Need to maintain primitive templates

---

### Option 2: Warm-Up Phase (Bootstrap with Primitives)
**Where:** Before curriculum starts, execute a hardcoded sequence of primitives

**Implementation:**

```python
def learn(self, reset_env=True):
    # ... existing reset code ...

    # Bootstrap phase - gather basic resources WITHOUT curriculum
    if not self.resume:
        print("\033[35m[Bootstrap] Gathering initial resources...\033[0m")

        bootstrap_tasks = [
            ("mineBlock", ["bot", "'oak_log'", "3"], "Mine 3 oak logs"),
            ("craftItem", ["bot", "'oak_planks'", "12"], "Craft planks"),
            ("craftItem", ["bot", "'stick'", "4"], "Craft sticks"),
            ("craftItem", ["bot", "'crafting_table'", "1"], "Craft table"),
            ("placeItem", ["bot", "'crafting_table'", "(0, 0, 0)"], "Place table"),
        ]

        for prim_func, prim_args, description in bootstrap_tasks:
            print(f"\033[35m[Bootstrap] {description}...\033[0m")

            # Queue primitive directly
            self.htn_orchestrator.task_queue.push(Task(
                action="primitive",
                payload={
                    "function": prim_func,
                    "args": prim_args,
                    "skill": description,
                    "line": 0
                },
                parent="bootstrap"
            ))

            # Execute
            success, events, error = self.htn_orchestrator.execute_queued_tasks()

            if not success:
                print(f"\033[31m[Bootstrap] Failed: {error}\033[0m")
                break

            self.last_events = events

        print("\033[35m[Bootstrap] Complete! Starting curriculum...\033[0m")

    # Now start normal curriculum loop
    while True:
        # ... existing curriculum code ...
```

**Pros:**
- ✅ Guarantees bot has basic tools before curriculum
- ✅ No LLM calls for bootstrap
- ✅ Predictable starting state

**Cons:**
- ❌ Hardcoded sequence (not adaptive)
- ❌ Doesn't solve the general problem (curriculum still proposes trivial tasks later)

---

### Option 3: Hybrid (BEST OF BOTH WORLDS)
**Combine Option 1 + Option 2:**

1. **Bootstrap Phase:** Execute 3-5 hardcoded primitives (oak logs, planks, sticks, table)
2. **Curriculum Phase:** Use primitive template matching for simple tasks
3. **Action Agent:** Only invoked for complex multi-step tasks

```python
def learn(self, reset_env=True):
    # Phase 1: Bootstrap
    if not self.resume:
        self._bootstrap_resources()

    # Phase 2: Curriculum with smart routing
    while True:
        task, context, primitive_mapping = self.curriculum_agent.propose_next_task(...)

        if primitive_mapping:
            # Route 1: Direct primitive execution
            self._execute_primitive_task(task, primitive_mapping)
        else:
            # Route 2: Complex task → Action Agent
            self.rollout(task=task, context=context, reset_env=False)
```

---

## Recommendation: **Option 3 (Hybrid)**

### Why This Is Best:

1. **Efficiency:**
   - Bootstrap: 5 primitives in ~30 seconds (no LLM calls)
   - Simple tasks: Direct primitive execution (50% of early tasks)
   - Complex tasks: Action Agent (only when needed)

2. **Cost Savings:**
   - Early game: ~80% fewer LLM calls
   - Mid game: ~40% fewer LLM calls
   - Late game: ~20% fewer LLM calls

3. **Reliability:**
   - Bootstrap guarantees working state
   - Primitive matching avoids Action Agent hallucinations
   - Action Agent only used for tasks it's good at

### Expected Flow:

```
START
  ↓
Bootstrap (no LLM):
  - mineBlock(bot, 'oak_log', 3)         [30s]
  - craftItem(bot, 'oak_planks', 12)     [5s]
  - craftItem(bot, 'stick', 4)           [5s]
  - craftItem(bot, 'crafting_table', 1)  [5s]
  ↓
Curriculum Proposes: "Mine 3 cobblestone"
  ↓
Matches primitive template → Direct execution
  - mineBlock(bot, 'cobblestone', 3)     [20s]
  ↓
Curriculum Proposes: "Craft wooden pickaxe"
  ↓
NO primitive match (multi-step) → Action Agent
  - LLM generates function                [5s]
  - HTN executes primitives               [30s]
  ↓
Curriculum Proposes: "Mine 10 iron ore"
  ↓
Matches primitive template → Direct execution
  - mineBlock(bot, 'iron_ore', 10)        [40s]
  ↓
... continues with smart routing ...
```

---

## Implementation Priority

### Phase 1 (Immediate):
1. ✅ Fix error feedback loop (done)
2. ✅ Simplify code_analyzer (done)
3. ⏳ Update prompts (user doing this)
4. ⏳ Add primitive template matching to curriculum agent

### Phase 2 (Next):
5. Add bootstrap phase with 5 hardcoded primitives
6. Update rollout to check for primitive_mapping
7. Test with early-game curriculum tasks

### Phase 3 (Polish):
8. Expand primitive templates (cover 80% of simple tasks)
9. Add telemetry to track LLM call savings
10. Optimize template patterns based on most common curriculum tasks

---

## Template Patterns to Support

### Mining (60% of early tasks):
```
"Mine X oak_log" → mineBlock(bot, 'oak_log', X)
"Collect X cobblestone" → mineBlock(bot, 'cobblestone', X)
"Obtain X coal" → mineBlock(bot, 'coal_ore', X)
"Gather X dirt" → mineBlock(bot, 'dirt', X)
```

### Crafting (30% of early tasks):
```
"Craft X planks" → craftItem(bot, 'oak_planks', X)
"Craft X sticks" → craftItem(bot, 'stick', X)
"Make X torches" → craftItem(bot, 'torch', X)
```

### Complex (10% - needs Action Agent):
```
"Craft wooden pickaxe" → multi-step (planks + sticks + craft)
"Build a house" → complex
"Explore until you find iron" → complex
```

---

## Code Example: Full Implementation

```python
# In curriculum.py
import re

class CurriculumAgent:
    PRIMITIVE_PATTERNS = {
        r"^mine (\d+) (.+?)(?:s|logs?)?$": ("mineBlock", 2),
        r"^collect (\d+) (.+?)(?:s)?$": ("mineBlock", 2),
        r"^obtain (\d+) (.+?)(?:s)?$": ("mineBlock", 2),
        r"^craft (\d+) (.+?)(?:s)?$": ("craftItem", 2),
        r"^make (\d+) (.+?)(?:s)?$": ("craftItem", 2),
        r"^smelt (\d+) (.+?)(?:s)?$": ("smeltItem", 2),
        r"^kill (\d+) (.+?)(?:s)?$": ("killMob", 2),
    }

    def task_to_primitive(self, task):
        """Convert task to primitive call if possible."""
        task_clean = task.lower().strip()

        for pattern, (primitive, arg_count) in self.PRIMITIVE_PATTERNS.items():
            match = re.match(pattern, task_clean)
            if match:
                count = match.group(1)
                item = match.group(2).replace(' ', '_')

                # Normalize wood variations
                if 'wood' in item or 'log' in item:
                    item = 'oak_log'

                return {
                    "primitive": primitive,
                    "args": ["bot", f"'{item}'", count]
                }

        return None

# In voyager.py
def learn(self):
    # Bootstrap phase
    if not self.resume:
        print("\033[35m═══ BOOTSTRAP PHASE ═══\033[0m")
        for prim, args, desc in BOOTSTRAP_PRIMITIVES:
            print(f"  • {desc}")
            self._execute_primitive_direct(prim, args)

    # Curriculum phase
    while True:
        task, context = self.curriculum_agent.propose_next_task(...)
        primitive_map = self.curriculum_agent.task_to_primitive(task)

        if primitive_map:
            print(f"\033[33m⚡ Fast path: {task}\033[0m")
            self._execute_primitive_direct(
                primitive_map['primitive'],
                primitive_map['args']
            )
        else:
            print(f"\033[34m🤖 Complex task: {task}\033[0m")
            self.rollout(task=task, context=context)

BOOTSTRAP_PRIMITIVES = [
    ("mineBlock", ["bot", "'oak_log'", "3"], "Mine oak logs"),
    ("craftItem", ["bot", "'oak_planks'", "12"], "Craft planks"),
    ("craftItem", ["bot", "'stick'", "4"], "Craft sticks"),
    ("craftItem", ["bot", "'crafting_table'", "1"], "Make crafting table"),
]
```

Would you like me to implement Option 3 (Hybrid approach)?