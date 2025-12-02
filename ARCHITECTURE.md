# Voyager Refactor - Architecture Diagram

## High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         Voyager.learn_v2()                       │
│                      (Thin Orchestrator)                         │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
         ┌───────────────────────────────────────┐
         │      1. Reset Manager                  │
         │   (Initial/Between-Task Resets)        │
         └───────────────────────────────────────┘
                                 │
                                 ▼
         ┌───────────────────────────────────────┐
         │      2. Curriculum Agent               │
         │   (Propose Next Task String)           │
         └───────────────────────────────────────┘
                                 │
                                 ▼
         ┌───────────────────────────────────────┐
         │      3. Task Classifier                │
         │   String → TaskSpec                    │
         └───────────────────────────────────────┘
                                 │
                                 ▼
         ┌───────────────────────────────────────┐
         │      4. Execution Router               │
         │   TaskSpec → ExecutionPlan             │
         └───────────────────────────────────────┘
                                 │
                ┌────────────────┴────────────────┐
                │                                  │
                ▼                                  ▼
    ┌───────────────────┐              ┌───────────────────┐
    │  Existing Skill?  │              │  CRAFT/MINE?     │
    └───────────────────┘              └───────────────────┘
                │                                  │
                ▼                                  ▼
    ┌───────────────────┐              ┌───────────────────┐
    │ Skill Executor    │              │Primitive Executor │
    └───────────────────┘              └───────────────────┘
                │                                  │
                └────────────────┬─────────────────┘
                                 │
                                 ▼
                        ┌───────────────────┐
                        │ Action LLM        │
                        │ Executor          │
                        │ (Fallback)        │
                        └───────────────────┘
                                 │
                                 ▼
         ┌───────────────────────────────────────┐
         │      5. World State Tracker            │
         │   (Update from ExecutionResult)        │
         └───────────────────────────────────────┘
                                 │
                                 ▼
         ┌───────────────────────────────────────┐
         │      6. Curriculum Update              │
         │   (Mark success/failure)               │
         └───────────────────────────────────────┘
                                 │
                                 ▼
         ┌───────────────────────────────────────┐
         │      7. Skill Manager                  │
         │   (Save if not primitive)              │
         └───────────────────────────────────────┘
                                 │
                                 ▼
                           Loop Back ↑
```

## Module Dependencies

```
┌─────────────────┐
│  Voyager Class  │
└────────┬────────┘
         │
         ├──────────────────────────────────────────────────┐
         │                                                   │
         ▼                                                   ▼
┌──────────────────┐                              ┌──────────────────┐
│ Task Classifier  │                              │ Execution Router │
│                  │                              │                  │
│ • TaskSpec       │                              │ • ExecutionPlan  │
│ • TaskType       │                              │ • ExecutionMode  │
└──────────────────┘                              └──────────────────┘
         │                                                   │
         │                                                   │
         ▼                                                   ▼
┌──────────────────┐                              ┌──────────────────┐
│World State       │                              │ Task Executors   │
│Tracker           │◄─────────────────────────────┤                  │
│                  │                              │ • Primitive      │
│ • Inventory      │                              │ • Skill          │
│ • Position       │                              │ • Action LLM     │
│ • Health         │                              │                  │
└──────────────────┘                              └──────────────────┘
         │                                                   │
         │                                                   ▼
         │                                          ┌──────────────────┐
         │                                          │ Execution Result │
         │◄─────────────────────────────────────────┤                  │
         │                                          │ • Success        │
         │                                          │ • Events         │
         │                                          │ • Code           │
         │                                          └──────────────────┘
         │
         ▼
┌──────────────────┐
│ Reset Manager    │
│                  │
│ • Hard Clear     │
│ • Soft Refresh   │
└──────────────────┘
```

## Data Flow Example: "Craft 4 oak planks"

```
1. Raw Input
   "Craft 4 oak planks" (string)
          │
          ▼
2. TaskClassifier.classify()
   TaskSpec(
     type=TaskType.CRAFT,
     params={'item': 'oak_planks', 'count': 4},
     origin='curriculum'
   )
          │
          ▼
3. ExecutionRouter.route()
   ExecutionPlan(
     mode=ExecutionMode.EXECUTOR_PRIMITIVE,
     save_as_skill=True
   )
          │
          ▼
4. PrimitiveExecutor.execute()
   - Calls executor.craft_item("4 oak_planks")
   - Returns ExecutionResult
          │
          ▼
5. ExecutionResult
   ExecutionResult(
     success=True,
     events=[...mineflayer events...],
     program_code="async function craftOakPlanks(bot) {...}",
     program_name="craftOakPlanks",
     is_one_line_primitive=False
   )
          │
          ▼
6. WorldStateTracker.update_from_events()
   - Updates inventory
   - Updates position
   - Updates other state
          │
          ▼
7. SkillManager.add_new_skill()
   - Saves "craftOakPlanks" skill
          │
          ▼
8. Loop Back for Next Task
```

## Separation of Concerns

### Before Refactor (voyager.py had everything)
```
┌─────────────────────────────────────────┐
│              voyager.py                 │
│ ┌─────────────────────────────────────┐ │
│ │ Task Parsing (string slicing)       │ │
│ ├─────────────────────────────────────┤ │
│ │ Routing Logic (if/elif chains)      │ │
│ ├─────────────────────────────────────┤ │
│ │ Execution (executor calls)          │ │
│ ├─────────────────────────────────────┤ │
│ │ State Management (event indexing)   │ │
│ ├─────────────────────────────────────┤ │
│ │ Reset Logic (mode switching)        │ │
│ └─────────────────────────────────────┘ │
│         ~550 lines of mixed logic       │
└─────────────────────────────────────────┘
```

### After Refactor (Clean Separation)
```
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ TaskClassifier │  │ExecutionRouter │  │ TaskExecutors  │
│                │  │                │  │                │
│  Parsing only  │  │  Routing only  │  │ Execution only │
└────────────────┘  └────────────────┘  └────────────────┘

┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│  WorldState    │  │ ResetManager   │  │  Voyager.py    │
│  Tracker       │  │                │  │                │
│  State only    │  │  Resets only   │  │Orchestration   │
└────────────────┘  └────────────────┘  └────────────────┘
```

## Execution Modes

```
                    ┌─────────────────┐
                    │  TaskSpec       │
                    │  from Classifier│
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Execution Router│
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ EXISTING     │   │ EXECUTOR     │   │ ACTION_LLM   │
│ SKILL        │   │ PRIMITIVE    │   │              │
│              │   │              │   │              │
│ • Skill name │   │ • CRAFT      │   │ • Complex    │
│   in library │   │ • MINE       │   │   tasks      │
│ • Fast       │   │ • GATHER     │   │ • Learning   │
│ • Reliable   │   │ • Direct     │   │ • Flexible   │
└──────────────┘   └──────────────┘   └──────────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Execution Result│
                    └─────────────────┘
```

## WorldStateTracker vs Direct Event Access

### Old Way (Brittle)
```python
# Direct indexing - can fail with IndexError
inventory = events[-1][1]["inventory"]
position = events[-1][1]["status"]["position"]
```

### New Way (Safe)
```python
# Safe accessors - never fail
inventory = world_state.get_inventory()      # Returns {} if missing
position = world_state.get_position()        # Returns None if missing
```

## Reset Modes

```
┌──────────────────────────────────────────────────────┐
│                   Reset Manager                       │
└───────────────────────┬──────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ HARD_CLEAR   │ │HARD_KEEP_INV │ │    SOFT      │
│              │ │              │ │              │
│ • Clear inv  │ │ • Keep inv   │ │ • Minimal    │
│ • Restart    │ │ • Restart    │ │ • Quick      │
│ • Initial    │ │ • Error      │ │ • Between    │
│   setup      │ │   recovery   │ │   tasks      │
└──────────────┘ └──────────────┘ └──────────────┘
```

## Extension Points

### Adding a New Task Type
```
1. Add to TaskType enum
   └─> task_spec.py

2. Add parsing logic
   └─> task_classifier.py

3. Add routing rule
   └─> execution_router.py

4. Add executor or use existing
   └─> task_executors/
```

### Adding HTN Planning
```
1. Already defined: ExecutionMode.HTN_PLAN

2. Implement HTN executor
   └─> task_executors/htn_executor.py

3. Update router
   └─> execution_router.py (add HTN routing logic)

4. Use in _execute_task
   └─> voyager.py (already has placeholder)
```

## Comparison: Lines of Code

```
┌─────────────────────┬──────────┬──────────┐
│ Component           │ Before   │  After   │
├─────────────────────┼──────────┼──────────┤
│ voyager.py          │   564    │   733*   │
│ Task parsing        │   ~80    │    0     │
│ Routing logic       │   ~100   │    0     │
│ State management    │  mixed   │    0     │
│ Reset logic         │   ~60    │    0     │
├─────────────────────┼──────────┼──────────┤
│ learn_v2() method   │    N/A   │   ~120   │
│ task_classifier.py  │    N/A   │   ~180   │
│ execution_router.py │    N/A   │   ~140   │
│ world_state_tracker │    N/A   │   ~200   │
│ reset_manager.py    │    N/A   │   ~140   │
│ task_executors/     │    N/A   │   ~400   │
└─────────────────────┴──────────┴──────────┘

* Includes both old learn() and new learn_v2()
```

## Key Takeaways

1. **Separation**: Each module has ONE responsibility
2. **Testability**: Each module can be tested independently
3. **Extensibility**: Easy to add new features
4. **Maintainability**: Clear code organization
5. **Compatibility**: Old code still works

---

**Architecture Status**: ✅ Complete and Production-Ready
