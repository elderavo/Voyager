Below is your **clean, implementation-ready .md spec**.
It is written for a **software engineering team**—explicit, directive, and structured so that your developers can build this architecture without ambiguity.

---

# Voyager Refactor Specification

### Modular Task Classification, Routing, Execution, and World State Management

**Version:** 1.0
**Intent:** Replace hacky/brittle paths in `voyager.py` with a clean, extensible architecture supporting crafting, mining, smelting, gathering, HTN integration, and future curriculum/task generators.

---

# 1. Overview

Current Voyager logic mixes:

* task parsing
* execution routing
* primitive vs. LLM decision-making
* skill management
* environment reset semantics
* inventory / world-state tracking

This produces non-deterministic behavior, hard-to-debug branches, and brittle string parsing.

This spec defines **new core modules** that fully separate concerns:

1. `TaskSpec` (data model)
2. `TaskClassifier` (task → structured representation)
3. `ExecutionPlan` (routing decision)
4. `ExecutionRouter` (choose executor based on task + world state)
5. `TaskExecutor` interface + implementations
6. `WorldStateTracker` (safe access to inventory, chests, voxels)
7. `ResetManager` (standardized reset semantics)
8. Revised `Voyager.learn()` pipeline (thin orchestration)

This is the minimal foundation required for stable crafting, mining, smelting, and future HTN integration.

---

# 2. Data Models

## 2.1 `TaskType` Enum

**Define an enum**:

```text
CRAFT
MINE
GATHER
SMELT
BUILD
EXPLORE
UNKNOWN
```

---

## 2.2 `TaskSpec` Model

Create a Python dataclass:

* `raw_text: str`
* `normalized: str`
* `type: TaskType`
* `params: dict`

  * examples:

    * `{ item: "oak_log", count: 4 }`
    * `{ block: "cobblestone", count: 8 }`
* `origin: str`

  * `"curriculum" | "manual" | "htn_subtask"`
* `metadata: dict`

  * optional difficulty, priority, etc.

**Purpose**:
All downstream logic relies on **TaskSpec**, not free-form strings.

---

# 3. Task Classification Module

Create file: `task_classifier.py`

## Responsibilities:

* Convert a raw curriculum string (e.g., “Mine a wood log”) into a valid `TaskSpec`.
* Provide stable, testable parsing.
* Remove all string slicing/startswith logic from `voyager.py`.

## Requirements:

1. Implement normalization:

   * lowercase
   * trim punctuation
   * map synonyms:

     * obtain/gather/collect → GATHER/MINE based on ontology
     * make/build/create → CRAFT
     * smelt/cook/furnace → SMELT

2. Use robust regex, not string slicing.

3. Extract:

   * item/block name
   * counts (incl. text numbers: “three torches” → count=3)

4. Return complete `TaskSpec`.

## Deliverables:

* `class TaskClassifier`
* `def classify(raw_task, context, world_state) -> TaskSpec`

---

# 4. Execution Routing Module

Create file: `execution_router.py`

## Responsibilities:

* Decide **how** a task should be executed.
* Choose between primitive executors, skill executors, HTN, or LLM.

You must NOT reference Mineflayer, LLM prompts, or skill code here—only return metadata.

---

## 4.1 `ExecutionMode` Enum

```text
EXISTING_SKILL
EXECUTOR_PRIMITIVE
HTN_PLAN
ACTION_LLM
```

---

## 4.2 `ExecutionPlan` Data Model

Fields:

* `mode: ExecutionMode`
* `skill_name: Optional[str]`
* `plan_steps: Optional[List[PrimitiveStep]]` (for HTN)
* `fallback_mode: Optional[ExecutionMode]`
* `save_as_skill: bool`

---

## 4.3 Decision Logic (Initial Implementation)

For **Phase 1**, implement the current behavior but clean:

1. If a matching skill exists → `EXISTING_SKILL`.
2. If `TaskSpec.type == CRAFT` → `EXECUTOR_PRIMITIVE`.
3. If `TaskSpec.type == MINE` → `EXECUTOR_PRIMITIVE`.
4. Else → `ACTION_LLM`.

HTN integration will add a new branch later.

---

# 5. Task Executors

Create folder: `executors/`

Define interface in `executors/base_executor.py`:

```python
class TaskExecutor:
    def execute(self, task_spec, plan, world_state) -> ExecutionResult:
        raise NotImplementedError
```

---

## 5.1 `ExecutionResult` Model

Fields:

* `success: bool`
* `events: List[MineflayerEvent]`
* `program_code: Optional[str]`
* `program_name: Optional[str]`
* `is_one_line_primitive: bool`
* `errors: Optional[List[str]]`

---

## 5.2 Implementations:

### 1. `PrimitiveExecutor`

Wrap your existing `Executor` class:

* `craft_item()`
* `direct_mine()`
* future: `smelt_item()`, `place_block()`

### 2. `SkillExecutor`

Executes existing JS skill code from SkillManager.

### 3. `ActionLLMExecutor`

Wraps your current:

* LLM step
* critic call
* retry loop
* message reconstruction

**Important**: Move all LLM logic out of Voyager.

---

# 6. World State Management

Create file: `world_state_tracker.py`

## Responsibilities:

* Maintain consistent world state across iterations.
* Provide safe accessors instead of direct event indexing.
* Replace usages like `events[-1][1]["inventory"]`.

---

## Required API:

### `update_from_events(events)`

* Parse Mineflayer events into canonical fields.

### Access methods:

* `get_inventory()`
* `get_position()`
* `get_nearby_chests()`
* `get_voxels()`
* `get_health()`
* `get_hunger()`

### Safety:

All getters must return defaults (`{}`, `[]`, or `None`) if missing.

---

# 7. Reset Manager

Create file: `reset_manager.py`

## Responsibilities:

Standardize environment resets.

---

## 7.1 Reset Modes Enum

```text
HARD_CLEAR
HARD_KEEP_INV
SOFT
NONE
```

---

## 7.2 API

* `apply_initial_reset(world_state)`
* `soft_refresh(world_state, result)`
* `handle_error_reset(world_state)`

---

# 8. New Voyager Learn Loop

Refactor `Voyager.learn()` to do **only orchestration**.

---

## 8.1 Required Process Flow

```
1. Reset world state according to ResetManager.
2. Loop until iteration limit:
    a. Ask CurriculumAgent for next raw task.
    b. Classify the task via TaskClassifier → TaskSpec.
    c. Route via ExecutionRouter → ExecutionPlan.
    d. Execute via chosen TaskExecutor.
    e. Update world state from ExecutionResult.
    f. Update CurriculumAgent.
    g. Save skill if allowed.
    h. Soft refresh state for next iteration.
3. Return summary.
```

Voyager must NOT:

* parse task strings
* choose craft vs mine logic
* index into event tuples
* decide on whether to save a skill
* decide whether something is primitive

All such decisions belong to the modules defined above.

---

# 9. Implementation Milestones

## Phase 1 (Week 1–2)

* Implement `TaskSpec`
* Implement `TaskClassifier` (CRAFT + MINE only)
* Implement `ExecutionMode`, `ExecutionPlan`, `ExecutionRouter`
* Implement `PrimitiveExecutor` & `ActionLLMExecutor` wrappers
* Add `WorldStateTracker` and remove indexing into events

## Phase 2 (Week 3)

* Move all LLM logic to `ActionLLMExecutor`
* Implement `ResetManager`
* Clean and shrink Voyager.learn()

## Phase 3 (Week 4)

* Add GATHER and SMELT to TaskClassifier
* Add HTN execution path (EXPERIMENTAL)
* Add SkillExecutor for fallback

---

# 10. Acceptance Criteria

The refactor is considered complete when:

1. **No parsing logic exists inside `Voyager.learn()`**

   * All tasks must route through `TaskClassifier`.

2. **No direct indexing into event structures**

   * All world data must come from `WorldStateTracker`.

3. **No branching logic like “if startswith(craft/mine)”**

   * All routing must use `ExecutionRouter`.

4. **Voyager is less than 300 LOC**

   * It must be a thin orchestrator.

5. **Primitive crafting and mining behave identically to current behavior**, but:

   * with better error handling
   * deterministic routing
   * no spurious retries
   * no “list index out of range” failures

---

# 11. Developer Notes

* Keep modules small and independently testable.
* All parsing and routing code must be unit tested.
* Executors should be integration-tested with Mineflayer.
* Keep consistent naming conventions and enums.
* Document all new APIs with docstrings and examples.

---

