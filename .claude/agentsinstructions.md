Here’s a concrete **file + class plan** to implement the 8 changes, while keeping the 4 original files mostly intact and only adding **one new shared module**.

I’ll refer to the existing files as:

* `curriculum.py` → CurriculumAgent 
* `skill.py` → SkillManager 
* `action.py` → ActionAgent 
* `critic.py` → CriticAgent 

---

# 0. High-Level Goals (8 Changes)

We want to implement:

1. Central world state extraction
2. Shared observation formatter
3. Structured JSON outputs for all LLMs
4. Transactional SkillManager writes
5. Move domain-specific curriculum logic out of the core agent
6. Externalize primitive-vs-skill detection
7. Unified ExecutionResult + error handling
8. Replace regex-based JS extraction with structured LLM output (with fallback)

We’ll do this with **minimal disruption** by:

* Adding **one shared module**: `agents_common.py`
* Lightly refactoring the four existing agents to depend on that module instead of duplicating logic.

---

# 1. New Shared Module: `agents_common.py`

## 1.1 Purpose

Centralize:

* world state parsing from Mineflayer events
* observation formatting (for curriculum, action, critic)
* structured execution result + error handling
* JSON parsing helpers shared across agents
* primitive-vs-skill detection (so it’s not buried in ActionAgent)

This is the backbone that the existing agents will call into, rather than each re-parsing events.

---

## 1.2 New Types

### 1.2.1 `WorldState`

A dataclass representing the *last known* observation:

* `biome: str`
* `time_of_day: int | str`
* `voxels: list[str]`
* `block_records: list[str]`
* `entities: dict[str, float]`
* `health: float`
* `hunger: float`
* `position: dict[str, float]`
* `equipment: dict[str, any]`
* `inventory_used: int`
* `inventory: dict[str, int]`
* `chest_observation: str` (comes from ActionAgent’s chest memory)
* `completed_tasks: list[str]` (optional, for curriculum context)
* `failed_tasks: list[str]` (optional)

### 1.2.2 `WorldStateBuilder`

Utility with:

* `from_events(events, chest_observation, completed_tasks=None, failed_tasks=None) -> WorldState`

Implementation notes:

* Find the **last `observe` event** in `events` rather than assuming `events[-1]` is observe.
* If no observe event -> raise a clear error (or return a sentinel state).
* Extract the same fields currently used by CurriculumAgent, ActionAgent, CriticAgent.

All places where those agents currently do `events[-1][1]["status"]["..."]` should go through this.

---

### 1.2.3 `ObservationFormatter`

Responsible for generating the textual “views” consumed by the LLMs.

Methods:

* `format_for_curriculum(world: WorldState, warm_up_config, qa_context: str | None) -> dict[str, str]`

  * Returns a dict keyed by `curriculum_observations` (`context`, `biome`, `time`, etc.) with formatted strings.
* `format_for_action(world: WorldState, *, code, task, context, critique, include_errors, include_chat, chat_messages, error_messages) -> str`
* `format_for_critic(world: WorldState, *, task, context, chest_observation) -> str`

This replaces env-parsing and string assembly in the three agents.

---

### 1.2.4 `ExecutionResult`

Dataclass used by Voyager + executors + critic:

* `success: bool`
* `events: list`
* `world_state: WorldState | None`
* `errors: list[str]`
* `program_code: str | None`
* `program_name: str | None`
* `is_one_line_primitive: bool`
* `metadata: dict[str, any]` (optional: for debug info, trace IDs, etc.)

This is your unified “what happened” container.

---

### 1.2.5 `LLMJsonParser`

Helper for all LLM agents:

* `parse_json_or_fail(text: str, *, who: str) -> dict`

  * Uses `fix_and_parse_json()` under the hood.
  * Logs clear error with `who="critic"`, `"curriculum"`, etc.

* `parse_json_with_retry(client, system_message, human_message, schema_hint, *, who: str, max_retries: int) -> dict`

  * Wraps the retry logic currently in CurriculumAgent and CriticAgent.

---

### 1.2.6 `PrimitiveDetector`

Move the one-line primitive detection out of ActionAgent:

* `is_one_line_primitive(js_ast, main_function_name: str) -> bool`

This is essentially your current `_is_one_line_primitive` method, but in the shared module.

---

# 2. Changes to `curriculum.py` (CurriculumAgent) 

### 2.1 Use `WorldStateBuilder` and `ObservationFormatter`

**Today**: `render_observation()` takes raw events, index into `events[-1]`, and manually builds a dict of strings.

**Change**:

1. `render_observation(events, chest_observation)`:

   * Build `WorldState` via `WorldStateBuilder.from_events(...)`.
   * Call `ObservationFormatter.format_for_curriculum(world, self.warm_up, qa_context)` to get the observation dict.
   * Remove direct event indexing from this file.

2. `render_human_message()`:

   * Use the observation dict from above.
   * Keep the warm-up gating logic (`if self.progress >= warm_up[key]`), but operate on already formatted pieces.

This implements:

* Change 1: **Central world state extraction**
* Change 2: **Shared observation formatter**

---

### 2.2 Enforce JSON for `propose_next_ai_task`

**Today**: `parse_ai_message()` searches for lines starting with `Task:`. Hugely brittle.

**Change**:

1. Update the curriculum prompt (`load_prompt("curriculum")`) to require a JSON like:

   ```json
   { "next_task": "Craft 1 furnace" }
   ```

2. Modify `propose_next_ai_task` to use:

   * `LLMJsonParser.parse_json_with_retry(...)` returning a dict.
   * Extract `next_task` from that dict.

3. Delete `parse_ai_message()` or keep it as a debug fallback, but the main flow must be JSON-based.

This implements:

* Change 3: **Structured outputs for all LLMs**

---

### 2.3 Move domain-specific inventory-full logic out of CurriculumAgent

**Today**: `propose_next_task()` has inline logic like:

* If `inventoryUsed >= 33` → generate chest tasks, deposit tasks, etc.

**Change**:

1. Introduce a small helper function in a new or existing module (e.g., `curriculum_domain.py` *or* just a top-level function in `curriculum.py` to keep the file count low):

   * `def suggest_inventory_management_task(world: WorldState, chest_observation: str) -> tuple[str, str] | None`

2. `propose_next_task()`:

   * Build `WorldState` first.
   * Call `suggest_inventory_management_task(world, chest_observation)`.
   * If it returns a `(task, context)`, return that early.
   * Otherwise, fall through to LLM-based task proposal.

This implements:

* Change 5: **Move domain-specific logic out of core agent** (at least into a clearly isolated helper)

---

# 3. Changes to `skill.py` (SkillManager) 

### 3.1 Make `add_new_skill()` transactional

**Today**: `add_new_skill` updates vectordb, writes code/description to disk, writes `skills.json`. A failure mid-way can desync.

**Change (minimal but safer):**

1. Inside `add_new_skill()`:

   * Build `new_skill_record = { "code": ..., "description": ... }` first.
   * Write code and description to temporary files:

     * e.g., `code_tmp_path = f"{...}/{dumped_program_name}.js.tmp"`
   * Write updated `skills` dict to an in-memory copy, then to a temp JSON file:

     * `skills_tmp = dict(self.skills); skills_tmp[program_name] = new_skill_record`
   * Only after files + JSON are successfully written:

     * Add skill text to vectordb.
     * Assign `self.skills = skills_tmp`.
     * Rename temp files to final names.
     * Persist vectordb.

2. In case of an exception before commit:

   * Do not modify `self.skills`.
   * Temp files can be cleaned up at startup.

This implements:

* Change 4: **Transactional SkillManager writes**

---

### 3.2 Move primitive detection here or into `agents_common`

Once `PrimitiveDetector.is_one_line_primitive` lives in `agents_common`, SkillManager can eventually use it when deciding what to save. For now:

* Ensure ActionAgent sets `is_one_line_primitive` using the shared helper instead of its own private method.

This contributes to:

* Change 6: **Externalize primitive-vs-skill detection**

---

# 4. Changes to `action.py` (ActionAgent) 

### 4.1 Use `WorldStateBuilder` and `ObservationFormatter`

**Today**: `render_human_message()`:

* Re-parses `events`, extracts biome/time/entities/inventory, etc.
* Duplicates logic from CurriculumAgent and CriticAgent.

**Change**:

1. Build `WorldState` via `WorldStateBuilder.from_events(events, chest_observation=self.render_chest_observation())` (or chest mem passed in).
2. Build the observation string via `ObservationFormatter.format_for_action(world, code=..., task=..., context=..., critique=..., include_errors=self.execution_error, include_chat=self.chat_log, chat_messages, error_messages)`.

This implements:

* Change 1 + 2 again: shared world state and formatting.

---

### 4.2 Convert `process_ai_message` to prefer structured JSON

**Today**:

* Extracts JS code via regex on ` ` fences.
* Uses Babel to parse, extract functions, then constructs `program_code` and `exec_code`.
* Then `_is_one_line_primitive` uses AST to check if it’s a single await call.

**Change (two-phase, backwards compatible):**

1. Update `action` system prompt to *prefer* JSON output:

   * Ask for:

     ```json
     {
       "program_code": "JS code here",
       "program_name": "mainFunc",
       "is_one_line_primitive": true/false
     }
     ```
   * You can still allow a `code` field with fenced JS for transition.

2. In `process_ai_message`:

   * First try to parse `message.content` as JSON using `LLMJsonParser.parse_json_or_fail`.
   * If successful:

     * Extract `program_code`, `program_name`, `is_one_line_primitive`.
   * If JSON parse fails:

     * Fallback to the existing Babel flow (regex + AST).

3. Replace `_is_one_line_primitive` with call to `PrimitiveDetector.is_one_line_primitive(ast, main_function_name)` from `agents_common`.

This implements:

* Change 3: **Structured LLM output**
* Change 6: **Primitive detection externalized**
* Change 8: **Regex-based extraction only as fallback, not primary**

---

# 5. Changes to `critic.py` (CriticAgent) 

### 5.1 Use `WorldState` + `ObservationFormatter`

**Today**: `render_human_message` re-parses events, similar to other agents.

**Change**:

1. Build `WorldState` via `WorldStateBuilder.from_events(events, chest_observation)`.
2. Get formatted text via `ObservationFormatter.format_for_critic(world, task=task, context=context, chest_observation=chest_observation)`.

This removes duplicated parsing and enforces a single world-view encoding across all agents.

---

### 5.2 Tighten JSON parsing and error handling in `ai_check_task_success`

You’re already using `fix_and_parse_json`, which is good.

**Change**:

1. Replace inline JSON parsing with `LLMJsonParser.parse_json_with_retry(...)`, passing `who="critic"`.
2. Ensure on failure you return `(False, "")` rather than recursing forever.
3. Avoid `return None` states; always return `(success, critique)`.

This strengthens:

* Change 3: **Structured JSON outputs**
* Change 7: **Unified ExecutionResult-style semantics (success + error)**

---

# 6. Unified ExecutionResult / Error Handling

The four agents don’t directly construct `ExecutionResult` today (that’s more Voyager/executor-level), but they **should produce enough structured data to fill it**.

Implementation:

* Voyager / Executor wraps outputs of ActionAgent, CriticAgent, and Env events into an `ExecutionResult` object defined in `agents_common.py`.
* CriticAgent returns `(success, critique)`; Executor populates `ExecutionResult.success` and adds `critique` into metadata.
* ActionAgent returns:

  * `program_code`, `program_name`, `is_one_line_primitive`
  * Executor then runs env.step, collects events, builds `WorldState`, and sets `ExecutionResult` fields.

This implements:

* Change 7: **Unified result wrapper**

No need to force the four files to own ExecutionResult; just ensure they *produce* structured pieces that feed into it.

---

# 7. Minimal New Files / Changes Recap

**New file:**

* `agents_common.py`

  * `WorldState`
  * `WorldStateBuilder`
  * `ObservationFormatter`
  * `ExecutionResult`
  * `LLMJsonParser`
  * `PrimitiveDetector`

**Existing files changes:**

* `curriculum.py`

  * Switch to WorldState + ObservationFormatter.
  * JSON output for tasks.
  * Extract inventory-full/chest logic into helper.

* `skill.py`

  * Transactional `add_new_skill`.
  * Optionally use `PrimitiveDetector` in future.

* `action.py`

  * Switch to WorldState + ObservationFormatter.
  * JSON-first `process_ai_message`, regex/Babel as fallback.
  * Use `PrimitiveDetector` from shared module.

* `critic.py`

  * Switch to WorldState + ObservationFormatter.
  * Use `LLMJsonParser` for critic JSON with proper retry handling.

---

# 8. Suggested Implementation Order

1. **Add `agents_common.py` with WorldState + Builder + Formatter (read-only, no behavior changes yet).**
2. **Refactor CurriculumAgent to consume WorldState + Formatter.**
3. **Refactor CriticAgent to consume WorldState + Formatter.**
4. **Refactor ActionAgent to consume WorldState + Formatter.**
5. **Introduce LLMJsonParser and migrate Curriculum and Critic to strict JSON outputs.**
6. **Add PrimitiveDetector, refactor ActionAgent, and wire SkillManager.**
7. **Make SkillManager.add_new_skill transactional.**
8. **Update Voyager/Executor to build and use ExecutionResult.**

You get modularity and stability without a rewrite, just by layering structure around the current behavior.
