# HTN Module Modularity Guide

## Architecture

The HTN (Hierarchical Task Network) system is designed as a **modular subsystem** that can operate independently or be integrated with Voyager.

### Module Structure

```
voyager/
├─ htn/                          # HTN execution module (NEW)
│  ├─ __init__.py               # Public API exports
│  ├─ orchestrator.py           # Main HTN orchestration logic
│  └─ README.md                 # HTN-specific documentation
│
├─ agents/                       # Existing Voyager agents
│  ├─ task_queue.py             # Core HTN data structures
│  ├─ skill_executor.py         # Task execution with fact validation
│  ├─ action.py                 # LLM prompt management
│  └─ curriculum.py             # Task selection
│
├─ facts/                        # Game mechanics facts (NEW)
│  ├─ __init__.py
│  └─ recipes.py                # Authoritative recipe/tool data
│
└─ voyager.py                    # Main orchestrator (MODIFIED)
```

## Public API

### HTNOrchestrator Class

The main entry point for HTN execution:

```python
from voyager.htn import HTNOrchestrator
from voyager.facts import RecipeFacts

# Initialize
facts = RecipeFacts(bot)
htn = HTNOrchestrator(env, facts, recorder)

# Parse JSON from LLM
intention, primitives, missing = htn.parse_json_response(ai_message.content)

# Execute with task queue
success, events = htn.execute_with_queue(intention, primitives, missing)

# Or queue and execute separately
htn.queue_tasks(intention, primitives, missing)
success, events = htn.execute_queue(max_steps=50)

# Get execution summary
summary = htn.get_execution_summary()
```

### Modularity Benefits

1. **Clean API**: Single entry point (`HTNOrchestrator`)
2. **Minimal Coupling**: Only depends on `env`, `facts`, `recorder`
3. **Testable**: Can test HTN logic independently
4. **Extractable**: Can be moved to separate package if needed
5. **Switchable**: Easy to toggle between code-gen and HTN modes

## Integration Points

### voyager.py Integration (Minimal)

```python
# Option 1: Use HTN system
from voyager.htn import HTNOrchestrator
from voyager.facts import RecipeFacts

class Voyager:
    def __init__(self, ...):
        # ... existing init ...

        # Add HTN orchestrator
        self.recipe_facts = RecipeFacts(self.env.bot)
        self.htn_orchestrator = HTNOrchestrator(
            self.env,
            self.recipe_facts,
            self.recorder
        )

    def step(self):
        # ... existing code ...

        # Try HTN execution
        try:
            intention, primitives, missing = self.htn_orchestrator.parse_json_response(
                ai_message.content
            )
            success, events = self.htn_orchestrator.execute_with_queue(
                intention, primitives, missing
            )
            self.last_events = events
            # ... process results ...

        except ValueError as e:
            # Fall back to code generation
            # ... existing code ...
```

### Option 2: Strategy Pattern (Most Modular)

```python
# voyager/execution_backends/base.py
class ExecutionBackend:
    def parse_response(self, ai_message): ...
    def execute(self, parsed_result): ...

# voyager/execution_backends/htn_backend.py
class HTNBackend(ExecutionBackend):
    def __init__(self, env, facts, recorder):
        self.orchestrator = HTNOrchestrator(env, facts, recorder)

    def parse_response(self, ai_message):
        return self.orchestrator.parse_json_response(ai_message.content)

    def execute(self, parsed_result):
        return self.orchestrator.execute_with_queue(*parsed_result)

# voyager/voyager.py
class Voyager:
    def __init__(self, execution_backend='htn', ...):
        if execution_backend == 'htn':
            self.backend = HTNBackend(env, facts, recorder)
        else:
            self.backend = CodeGenBackend(...)

    def step(self):
        parsed = self.backend.parse_response(ai_message)
        success, events = self.backend.execute(parsed)
```

## Dependency Isolation

### Current Dependencies

**HTN Module depends on:**
- `voyager.env` (for `env.step()`)
- `voyager.facts` (for `RecipeFacts`)
- `voyager.agents.task_queue` (data structures)
- `voyager.agents.skill_executor` (execution logic)

**Does NOT depend on:**
- ❌ `voyager.agents.action` (LLM prompts)
- ❌ `voyager.agents.curriculum` (task selection)
- ❌ `voyager.skill_manager` (code storage)
- ❌ `voyager.voyager` (main orchestrator)

### Future: Standalone Package

To extract as a separate package:

```bash
# New package structure
voyager-htn/
├─ setup.py
├─ voyager_htn/
│  ├─ __init__.py
│  ├─ orchestrator.py
│  ├─ task_queue.py
│  ├─ executor.py
│  └─ adapters/
│     ├─ voyager.py         # Adapter for Voyager
│     └─ minedojo.py        # Adapter for MineDojo, etc.
```

Install and use:
```python
pip install voyager-htn

from voyager_htn import HTNOrchestrator
from voyager_htn.adapters.voyager import VoyagerAdapter

adapter = VoyagerAdapter(env, facts)
htn = HTNOrchestrator(adapter)
```

## Testing Strategy

### Unit Tests (Isolated)

```python
# test_htn_orchestrator.py
from voyager.htn import HTNOrchestrator
from unittest.mock import Mock

def test_parse_json():
    htn = HTNOrchestrator(Mock(), Mock())
    json_response = '{"intention": "test", "primitive_actions": [], "missing": []}'
    intention, primitives, missing = htn.parse_json_response(json_response)
    assert intention == "test"

def test_queue_tasks():
    htn = HTNOrchestrator(Mock(), Mock())
    htn.queue_tasks("craft_pickaxe", [], ["gather:logs"])
    assert htn.task_queue.size() == 1
```

### Integration Tests (With Voyager)

```python
# test_voyager_htn_integration.py
from voyager import Voyager

def test_htn_execution():
    voyager = Voyager(execution_backend='htn', ...)
    voyager.learn()
    # Assert HTN was used instead of code generation
```

## Migration Path

### Phase 1: Parallel Execution (Current)
- Both systems coexist
- HTN used when JSON parsed successfully
- Code-gen as fallback

### Phase 2: Feature Flag
```python
voyager = Voyager(
    use_htn=True,  # Toggle HTN vs code-gen
    ...
)
```

### Phase 3: HTN Default
- HTN becomes default
- Code-gen deprecated

### Phase 4: Extract Module
- HTN extracted to `voyager-htn` package
- Voyager depends on `voyager-htn`
- Other projects can use `voyager-htn` independently

## Benefits of This Design

✅ **Modularity**: Clear module boundaries
✅ **Testability**: Each component tests independently
✅ **Flexibility**: Easy to swap execution backends
✅ **Reusability**: HTN system usable in other projects
✅ **Maintainability**: Changes isolated to HTN module
✅ **Backwards Compatible**: Old system still works

## Current Status

- ✅ HTN module structure created
- ✅ HTNOrchestrator implemented
- ✅ Public API defined
- ⚠️ voyager.py still has inline JSON parsing (can be refactored)
- ⚠️ SkillExecutor needs Mineflayer primitives wired up
- ❌ Strategy pattern not yet implemented
