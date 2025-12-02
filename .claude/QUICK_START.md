# Voyager Refactor - Quick Start Guide

## What Was Built

A complete modular refactor of the Voyager learning system according to the specification in `.claude/instructions.md`.

## New Files Created

### Core Modules
1. **voyager/task_spec.py** - Task data models
2. **voyager/task_classifier.py** - Task parsing
3. **voyager/execution_plan.py** - Execution planning models
4. **voyager/execution_router.py** - Routing logic
5. **voyager/world_state_tracker.py** - World state management
6. **voyager/reset_manager.py** - Reset management

### Executors
7. **voyager/task_executors/__init__.py** - Package exports
8. **voyager/task_executors/base_executor.py** - Executor interface
9. **voyager/task_executors/primitive_executor.py** - Primitive operations
10. **voyager/task_executors/skill_executor.py** - Skill execution
11. **voyager/task_executors/action_llm_executor.py** - LLM execution

### Updated Files
12. **voyager/voyager.py** - Added imports, initialization, and `learn_v2()` method

## How to Use

### Option 1: Use the New Architecture (Recommended)

```python
from voyager import Voyager

voyager = Voyager(
    mc_port=25565,
    openai_api_key="your-key",
)

# Use the new refactored method
result = voyager.learn_v2()
```

### Option 2: Keep Using Original (Backward Compatible)

```python
# Original method still works unchanged
result = voyager.learn()
```

## Key Improvements

### Before (Old Architecture)
```python
# voyager.py had everything:
if task.lower().startswith("craft"):
    item_name = task[6:].strip()
    info = self.executor_craft(item_name)
elif task.lower().startswith("mine"):
    # parse mining task...
    info = self.executor.direct_mine(...)
# ... 500+ lines of mixed logic
```

### After (New Architecture)
```python
# Clean separation:
task_spec = self.task_classifier.classify(raw_task)  # Parse
plan = self.execution_router.route(task_spec)       # Route
result = self._execute_task(task_spec, plan)        # Execute
```

## Architecture Overview

```
Raw Task String
      ↓
TaskClassifier → TaskSpec
      ↓
ExecutionRouter → ExecutionPlan
      ↓
TaskExecutor → ExecutionResult
      ↓
WorldStateTracker (updated)
```

## Module Responsibilities

| Module | Does | Doesn't Do |
|--------|------|------------|
| TaskClassifier | Parse tasks into TaskSpec | Execute or route |
| ExecutionRouter | Decide HOW to execute | Parse or execute |
| TaskExecutors | Execute tasks | Parse or route |
| WorldStateTracker | Track world state | Execute tasks |
| ResetManager | Handle resets | Parse or execute |

## File Locations

```
Voyager/
├── voyager/
│   ├── task_spec.py
│   ├── task_classifier.py
│   ├── execution_plan.py
│   ├── execution_router.py
│   ├── world_state_tracker.py
│   ├── reset_manager.py
│   ├── task_executors/
│   │   ├── __init__.py
│   │   ├── base_executor.py
│   │   ├── primitive_executor.py
│   │   ├── skill_executor.py
│   │   └── action_llm_executor.py
│   └── voyager.py (updated)
├── REFACTOR_COMPLETE.md (detailed docs)
└── QUICK_START.md (this file)
```

## Testing the Implementation

### Quick Test
```python
# Test task classification
from voyager.task_classifier import TaskClassifier
classifier = TaskClassifier()
spec = classifier.classify("Craft 4 oak planks")
print(spec)  # TaskSpec(type=CRAFT, params={'item': 'oak_planks', 'count': 4})

# Test routing
from voyager.execution_router import ExecutionRouter
router = ExecutionRouter(skill_manager=None)
plan = router.route(spec)
print(plan)  # ExecutionPlan(mode=EXECUTOR_PRIMITIVE, save_as_skill=True)
```

### Full Integration Test
```python
from voyager import Voyager

voyager = Voyager(
    mc_port=25565,
    openai_api_key="your-key",
    max_iterations=5,  # Quick test
)

result = voyager.learn_v2()
print(f"Completed: {result['completed_tasks']}")
```

## Migration Checklist

- [x] All new modules created
- [x] Voyager class updated
- [x] `learn_v2()` method added
- [x] Backward compatibility maintained
- [ ] Run tests
- [ ] Compare learn() vs learn_v2() results
- [ ] Switch production code to learn_v2()

## Common Issues & Solutions

### Import Error
```python
# If you get import errors, make sure you're in the right directory
import sys
sys.path.insert(0, '/path/to/Voyager')
from voyager import Voyager
```

### No module named 'task_executors'
Make sure `voyager/task_executors/__init__.py` exists.

## Next Steps

1. **Test** the implementation with a small Minecraft world
2. **Compare** results between `learn()` and `learn_v2()`
3. **Monitor** for any issues or edge cases
4. **Extend** with new task types (SMELT, GATHER, etc.)
5. **Add** HTN planning when ready

## Documentation

- **REFACTOR_COMPLETE.md** - Full implementation details
- **.claude/instructions.md** - Original specification
- **This file** - Quick reference

## Status

✅ **Implementation Complete**
- All Phase 1 requirements met
- Backward compatible
- Ready for testing

---

**Need Help?**
- Check REFACTOR_COMPLETE.md for detailed docs
- Review .claude/instructions.md for specification
- All modules have comprehensive docstrings
