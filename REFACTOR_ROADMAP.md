# HTN System Refactor Roadmap

## Executive Summary

**Goal**: Transform the HTN system from a primitive task executor into a skill-based orchestrator that checks known skills, decomposes intentions into primitive calls, and lets the LLM write dependency resolution logic in JavaScript.

**Core Principle**: The LLM writes JavaScript code that handles dependencies internally (like OG Voyager). The HTN system validates that the LLM's proposed code only uses known skills + primitives, then executes it.

---

## Current State Analysis

### What We Have:
1. **SkillManager** ([skill.py](voyager/agents/skill.py)) - Works correctly
   - Stores skills in `skills.json` as `{name: {code, description}}`
   - Vector DB for semantic skill retrieval
   - `programs` property concatenates all skills + primitives

2. **HTNOrchestrator** ([htn/orchestrator.py](voyager/htn/orchestrator.py)) - Wrong architecture
   - Parses JSON from LLM (intention, primitive_actions, missing)
   - Tries to execute primitives by generating templated JS
   - Should instead validate & decompose skills

3. **SkillExecutor** ([skill_executor.py](voyager/agents/skill_executor.py)) - Wrong architecture
   - Has `_execute_craft()`, `_execute_gather()`, etc.
   - Reimplements game logic in Python
   - Should be deleted or minimized to validation only

4. **Prompts** ([prompts/action_template.txt](voyager/prompts/action_template.txt))
   - Currently tells LLM to output JSON with dependencies
   - Should tell LLM to write JavaScript using known skills + primitives

5. **RecipeFacts** ([facts/recipes.py](voyager/facts/recipes.py)) - Keep as-is
   - Provides validation data from mineflayer registry
   - Used for hints to LLM, not execution


---

## Target Architecture

### New Flow:

```
Curriculum Agent: Ask LLM what to do next, get reply "craft stone pickaxe"
    ↓
[ActionAgent] Ask LLM: "Write code for 'craft stone pickaxe' using known skills + primitives"
    ↓
[LLM] Returns structured response:
{
  "intention": "craft_stone_pickaxe",
  "skill_code": "async function craftStonePickaxe(bot) { ... }",
  "dependencies_used": ["mine_stone", "craft_sticks", "craftItem"],
  "reasoning": "Need cobblestone and sticks, handle missing materials"
}
    ↓
[HTNOrchestrator] Validate response:

Crafting Algo/Pseudocode: 
Craft(X):
Get Recipe
Check for immediate satisfiability from inventory (if so, craft and finish) (because if it's in inv, assume it's already known or primitive)
Check if covered by known skill (if so, push primitives of known skill onto stack and finish)
If not, print missing items (as list) 
for item in list 
Craft(item)

On success, record all primitives of X and put X into known skills
  - Parse skill_code to extract function calls
  - Check all called functions exist in: known_skills OR primitives
  - If validation fails → ask LLM to fix with error details
  - If validation passes → proceed to execution
    ↓
[HTNOrchestrator] Decompose skill into execution plan:
  - Extract all function calls from skill_code
  - Build dependency graph
  - Create execution stack (primitives only, in correct order)
    ↓
[VoyagerEnv] Execute the full skill JavaScript in mineflayer
  - Skill code runs with access to all known skills + primitives
  - Mineflayer handles actual game interactions
    ↓
[CriticAgent] Verify success
    ↓
[SkillManager] If successful, save new skill:
  - Add to skills.json
  - Add to vector DB
  - Now available for future tasks!
```

### Key Changes:

1. **LLM writes full JavaScript functions** with dependency handling ///NOTE: THIS ALREADY HAPPENS! Don't change! 
2. **HTN validates** that code only uses known functions 
3. **HTN decomposes** skill into primitives for stack execution /// NOTE: The primitives are any skill defined in mineflayer (eg, mine, goto)
4. **No Python execution logic** - just validation and orchestration
5. **Skills are reusable** - future tasks can call saved skills /// NOTE: The HTN should decompose them into 

---

## Detailed Refactor Steps

### Phase 1: Update Prompts (No code changes yet)

**Files to modify:**
- `voyager/prompts/action_template.txt`
- `voyager/prompts/action_response_format.txt`

**Changes:**

#### action_template.txt:
```
You are a helpful assistant that writes Minecraft bot code using Mineflayer primitives and known skills.

Available primitives:
{primitives}

Available known skills:
{known_skills}

Your job:
1. Analyze the current state (inventory, resources, position)
2. Write a JavaScript function to accomplish the task
3. Use ONLY the primitives and known skills listed above
4. Handle missing dependencies by calling other skills or primitives
5. Check inventory before crafting/using items

IMPORTANT RULES:
- You MUST write a complete async function
- You MAY call minefalyer primitives
- You MAY call known skills (listed above)
- You MAY NOT call functions that don't exist in the lists above
- You MUST handle inventory checks and missing materials
- You MUST use bot.inventory.count() to check quantities

Output Format:
{response_format}
```

#### action_response_format.txt:
```json
{
  "intention": "<task_name_in_snake_case>",
  "skill_code": "<complete JavaScript async function>",
  "dependencies_used": ["<skill1>", "<skill2>", "<primitive1>"],
  "reasoning": "<why you wrote the code this way>"
}
```

**Test Plan:**
- Manually test prompt with GPT-4 API
- Verify it outputs valid JSON with executable JavaScript

---

### Phase 2: Add Skill Validation to HTNOrchestrator

**Files to modify:**
- `voyager/htn/orchestrator.py`

**New methods to add:**

```python
def validate_skill_code(self, skill_code, available_functions):
    """
    Parse JavaScript code and verify all function calls exist.

    Args:
        skill_code (str): JavaScript function code
        available_functions (set): Set of valid function names

    Returns:
        tuple: (is_valid, errors, function_calls)
    """
    try:
        # Use JavaScript AST parser (Babel via pyexecjs)
        # Extract all function calls: await foo(), foo(), bot.something()
        # Check each against available_functions

        function_calls = self._extract_function_calls(skill_code)
        invalid_calls = [f for f in function_calls if f not in available_functions]

        if invalid_calls:
            return False, f"Unknown functions: {invalid_calls}", function_calls

        return True, None, function_calls

    except Exception as e:
        return False, f"Parse error: {e}", []

def _extract_function_calls(self, skill_code):
    """
    Parse JavaScript and extract all function calls.
    Uses Babel parser (same as current code parsing).
    """
    # Similar to action.py process_ai_message() logic
    # Extract: await foo(...), foo(...), bot.method(...)
    # Return list of function names
    pass

def decompose_skill_to_primitives(self, skill_code, known_skills):
    """
    Analyze skill code and build execution plan.

    Args:
        skill_code (str): Validated JavaScript function
        known_skills (dict): All known skills with their code

    Returns:
        list: Execution plan with primitives only
    """
    # For each function call in skill_code:
    #   - If it's a primitive → add to plan
    #   - If it's a skill → recursively decompose
    # Build topologically sorted list of primitives
    pass
```

**Test Plan:**
- Unit test with sample skill code
- Verify detection of unknown functions
- Verify extraction of all function calls

---

### Phase 3: Refactor HTNOrchestrator Main Flow

**Files to modify:**
- `voyager/htn/orchestrator.py`

**Replace current methods:**

```python
def parse_llm_response(self, ai_message_content):
    """
    Parse JSON response from LLM containing skill code.

    Returns:
        dict: {intention, skill_code, dependencies_used, reasoning}
    """
    # Extract JSON from markdown
    # Parse and validate required fields
    # Return structured data
    pass

def validate_and_prepare_skill(self, response, skill_manager):
    """
    Validate LLM's skill code and prepare for execution.

    Args:
        response (dict): Parsed LLM response
        skill_manager (SkillManager): For available skills/primitives

    Returns:
        tuple: (is_valid, error_message, execution_plan)
    """
    skill_code = response['skill_code']
    dependencies = response['dependencies_used']

    # Get all available functions
    available = set(skill_manager.skills.keys())
    available.update(['mineBlock', 'craftItem', 'smeltItem', 'placeItem',
                      'killMob', 'exploreUntil', 'useChest'])

    # Validate
    is_valid, error, calls = self.validate_skill_code(skill_code, available)

    if not is_valid:
        return False, error, None

    # Verify declared dependencies match actual calls
    actual_deps = set(calls)
    declared_deps = set(dependencies)
    if actual_deps != declared_deps:
        return False, f"Dependency mismatch: {actual_deps} vs {declared_deps}", None

    # Build execution plan
    plan = self.decompose_skill_to_primitives(skill_code, skill_manager.skills)

    return True, None, plan

def execute_skill(self, skill_code, skill_manager, env):
    """
    Execute validated skill code in mineflayer.

    Args:
        skill_code (str): Validated JavaScript function
        skill_manager (SkillManager): For programs context
        env (VoyagerEnv): For execution

    Returns:
        tuple: (success, events, error)
    """
    # Execute full skill code with all skills + primitives available
    all_programs = skill_manager.programs
    events = env.step(code=skill_code, programs=all_programs)

    # Check for errors in events
    success = self._check_execution_success(events)

    return success, events, None
```

**Remove/deprecate:**
- `queue_tasks()` - Not needed anymore
- `execute_queue()` - Not needed anymore
- `_generate_code_for_task()` - LLM generates code now
- Most of the task queue logic

**Keep:**
- `last_intention`, `last_primitives` for debugging
- Event and inventory tracking
- Error handling and retry logic

**Test Plan:**
- Integration test with mock LLM response
- Verify validation catches invalid functions
- Verify execution passes correct programs to env

---

### Phase 4: Simplify or Remove SkillExecutor

**Files to modify:**
- `voyager/agents/skill_executor.py` (major simplification)

**Option A: Minimize to validation helper**

```python
class SkillValidator:
    """Provides validation hints to LLM, doesn't execute."""

    def __init__(self, facts):
        self.facts = facts

    def get_item_validation(self, item_name):
        """Check if item exists and get metadata."""
        normalized = self._normalize_item_name(item_name)
        if not normalized:
            return {"valid": False, "error": f"Unknown item: {item_name}"}

        recipe = self.facts.get_recipe(normalized)
        return {
            "valid": True,
            "normalized_name": normalized,
            "craftable": recipe is not None,
            "ingredients": self.facts.get_ingredient_names(recipe[0]) if recipe else []
        }

    def get_execution_hints(self, intention):
        """Return hints to include in LLM prompt."""
        # e.g., for "craft stone pickaxe" return:
        # "Requires: 3 cobblestone, 2 sticks"
        pass
```

**Option B: Remove entirely**
- Move `_normalize_item_name()` to RecipeFacts
- Use RecipeFacts directly for validation hints

**Test Plan:**
- Verify hints are useful in prompts
- Verify validation catches errors early

---

### Phase 5: Update ActionAgent Integration

**Files to modify:**
- `voyager/agents/action.py`
- `voyager/voyager.py`

**ActionAgent changes:**

```python
def request_skill_from_llm(self, task, events, known_skills, primitives):
    """
    Ask LLM to write skill code for task.

    Args:
        task (str): The task to accomplish
        events (list): Recent game events
        known_skills (list): Available skill descriptions
        primitives (list): Available primitive descriptions

    Returns:
        str: Raw LLM response (JSON)
    """
    system_msg = self.render_system_message(skills=known_skills)
    human_msg = self.render_human_message(events=events, task=task)

    messages = [system_msg, human_msg]
    response = self.llm.invoke(messages)

    return response.content
```

**Voyager.py changes:**

```python
def step(self, task):
    # ... existing setup ...

    # Get known skills for context
    relevant_skills = self.skill_manager.retrieve_skills(task)

    # Ask LLM for skill code
    llm_response = self.action_agent.request_skill_from_llm(
        task=task,
        events=self.last_events,
        known_skills=relevant_skills,
        primitives=self.skill_manager.control_primitives
    )

    # Parse and validate
    parsed = self.htn_orchestrator.parse_llm_response(llm_response)
    is_valid, error, plan = self.htn_orchestrator.validate_and_prepare_skill(
        parsed, self.skill_manager
    )

    # Retry loop if validation fails
    max_retries = 3
    retry_count = 0
    while not is_valid and retry_count < max_retries:
        # Tell LLM about the error
        llm_response = self.action_agent.retry_with_error(
            previous_response=llm_response,
            error=error
        )
        parsed = self.htn_orchestrator.parse_llm_response(llm_response)
        is_valid, error, plan = self.htn_orchestrator.validate_and_prepare_skill(
            parsed, self.skill_manager
        )
        retry_count += 1

    if not is_valid:
        raise RuntimeError(f"LLM failed to generate valid skill after {max_retries} retries: {error}")

    # Execute skill
    success, events, exec_error = self.htn_orchestrator.execute_skill(
        skill_code=parsed['skill_code'],
        skill_manager=self.skill_manager,
        env=self.env
    )

    # Update state
    self.last_events = events

    # Critic verification
    critique = self.critic_agent.check_task_success(
        task=task,
        events=events,
        max_retries=5
    )

    # Save successful skill
    if success and critique['success']:
        self.skill_manager.add_new_skill({
            "task": task,
            "program_name": parsed['intention'],
            "program_code": parsed['skill_code']
        })

    return success, events, critique
```

**Test Plan:**
- Integration test with full flow
- Verify retry logic works
- Verify skills are saved correctly

---

### Phase 6: Update Response Format and Parsing

**Files to modify:**
- `voyager/htn/orchestrator.py`
- `voyager/agents/action.py`

**Add robust JSON parsing:**

```python
def parse_llm_response(self, ai_message_content):
    """
    Parse structured JSON response from LLM.

    Expected format:
    {
      "intention": "task_name",
      "skill_code": "async function ...",
      "dependencies_used": ["func1", "func2"],
      "reasoning": "explanation"
    }
    """
    # Try to extract JSON from markdown code blocks
    json_pattern = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
    matches = json_pattern.findall(ai_message_content)

    json_str = matches[0] if matches else ai_message_content

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}\nResponse: {ai_message_content}")

    # Validate required fields
    required = ["intention", "skill_code", "dependencies_used"]
    missing = [f for f in required if f not in data]
    if missing:
        raise ValueError(f"Missing fields: {missing}")

    # Validate types
    if not isinstance(data['skill_code'], str):
        raise ValueError("skill_code must be string")
    if not isinstance(data['dependencies_used'], list):
        raise ValueError("dependencies_used must be list")

    return data
```

**Test Plan:**
- Unit test with various JSON formats
- Test with markdown code blocks
- Test error handling

---

### Phase 7: Function Call Extraction (JavaScript AST)

**Files to modify:**
- `voyager/htn/orchestrator.py` (or new file `voyager/htn/code_analyzer.py`)

**Implementation:**

```python
from javascript import require

class JavaScriptAnalyzer:
    """Analyze JavaScript code using Babel AST parser."""

    def __init__(self):
        # Use same Babel setup as action.py
        self.babel = require("@babel/core")
        self.babel_generator = require("@babel/generator").default

    def extract_function_calls(self, code):
        """
        Parse JavaScript and extract all function calls.

        Returns:
            list: Function names called in the code
        """
        try:
            # Parse to AST
            ast = self.babel.parse(code, {
                "sourceType": "module",
                "plugins": ["jsx"]
            })

            # Walk AST and find CallExpression nodes
            calls = []
            self._visit_ast(ast, calls)

            return list(set(calls))  # Deduplicate

        except Exception as e:
            raise ValueError(f"JavaScript parse error: {e}")

    def _visit_ast(self, node, calls):
        """Recursively visit AST nodes to find function calls."""
        if isinstance(node, dict):
            node_type = node.get('type')

            # Check for function calls
            if node_type == 'CallExpression':
                callee = node.get('callee', {})
                if callee.get('type') == 'Identifier':
                    calls.append(callee.get('name'))
                elif callee.get('type') == 'MemberExpression':
                    # Handle bot.method() or obj.method()
                    obj = callee.get('object', {})
                    prop = callee.get('property', {})
                    if obj.get('name') == 'bot':
                        # Skip bot.* methods (built-in mineflayer)
                        pass
                    elif prop.get('type') == 'Identifier':
                        calls.append(prop.get('name'))

            # Recursively visit child nodes
            for value in node.values():
                if isinstance(value, (dict, list)):
                    self._visit_ast(value, calls)

        elif isinstance(node, list):
            for item in node:
                self._visit_ast(item, calls)
```

**Test Plan:**
- Unit test with sample JavaScript functions
- Test complex nesting and await calls
- Test member expressions (bot.chat, etc.)

---

### Phase 8: Skill Decomposition Logic

**Files to modify:**
- `voyager/htn/orchestrator.py`

**Implementation:**

```python
def decompose_skill_to_primitives(self, skill_code, known_skills):
    """
    Recursively decompose skill into primitives.

    Args:
        skill_code (str): Top-level skill JavaScript
        known_skills (dict): All known skills {name: {code, description}}

    Returns:
        list: Ordered list of primitive operations
    """
    analyzer = JavaScriptAnalyzer()
    function_calls = analyzer.extract_function_calls(skill_code)

    primitives = {'mineBlock', 'craftItem', 'smeltItem', 'placeItem',
                  'killMob', 'exploreUntil', 'useChest'}

    execution_plan = []

    for call in function_calls:
        if call in primitives:
            # It's a primitive - add directly
            execution_plan.append({
                'type': 'primitive',
                'function': call,
                'source': 'top_level'
            })
        elif call in known_skills:
            # It's a skill - recursively decompose
            skill_primitives = self.decompose_skill_to_primitives(
                known_skills[call]['code'],
                known_skills
            )
            execution_plan.extend(skill_primitives)
        else:
            # Unknown function (should have been caught in validation)
            raise ValueError(f"Unknown function in decomposition: {call}")

    return execution_plan
```

**Note**: This decomposition is primarily for **visualization and debugging**. The actual execution runs the full skill code, not individual primitives.

**Test Plan:**
- Test with nested skills (skill calls skill calls primitive)
- Verify topological ordering
- Test cycle detection

---

### Phase 9: Error Handling and Retry Logic

**Files to modify:**
- `voyager/voyager.py`
- `voyager/agents/action.py`

**Add retry method to ActionAgent:**

```python
def retry_with_error(self, previous_response, error, task, events):
    """
    Ask LLM to fix skill code based on error.

    Args:
        previous_response (str): Previous LLM response
        error (str): Validation or execution error
        task (str): Original task
        events (list): Game events

    Returns:
        str: New LLM response (hopefully fixed)
    """
    retry_prompt = f"""
Your previous response had an error:
{error}

Previous response:
{previous_response}

Please fix the issue and provide a corrected response.
Remember:
- Only use functions from the known skills and primitives lists
- All function names must be exact matches
- Check bot.inventory before crafting/using items
"""

    human_msg = HumanMessage(content=retry_prompt)
    response = self.llm.invoke([self.last_system_message, human_msg])

    return response.content
```

**Add to Voyager.py:**

```python
def step_with_retries(self, task, max_retries=3):
    """Execute task with automatic retry on validation failures."""

    for attempt in range(max_retries):
        try:
            # Get LLM response
            llm_response = self.action_agent.request_skill_from_llm(...)

            # Validate
            parsed = self.htn_orchestrator.parse_llm_response(llm_response)
            is_valid, error, plan = self.htn_orchestrator.validate_and_prepare_skill(...)

            if not is_valid:
                print(f"Validation failed (attempt {attempt+1}/{max_retries}): {error}")
                if attempt < max_retries - 1:
                    # Retry with error feedback
                    llm_response = self.action_agent.retry_with_error(
                        previous_response=llm_response,
                        error=error,
                        task=task,
                        events=self.last_events
                    )
                    continue
                else:
                    raise RuntimeError(f"Validation failed after {max_retries} attempts")

            # Execute
            success, events, exec_error = self.htn_orchestrator.execute_skill(...)

            return success, events

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Error (attempt {attempt+1}/{max_retries}): {e}")
                continue
            else:
                raise
```

**Test Plan:**
- Test with intentionally invalid responses
- Verify retry improves output
- Test max_retries limit

---

### Phase 10: Integration Testing and Cleanup

**Tasks:**

1. **Remove deprecated code:**
   - Delete or comment out old HTN task queue logic
   - Remove `skill_executor.py` methods
   - Clean up unused imports

2. **Add comprehensive tests:**
   - Unit tests for all new methods
   - Integration tests for full flow
   - Test with real Minecraft environment

3. **Update documentation:**
   - Update README with new architecture
   - Document new JSON response format
   - Add examples of skill code

4. **Performance optimization:**
   - Cache parsed ASTs
   - Optimize skill retrieval
   - Add timeout handling

5. **Edge case handling:**
   - Empty inventory scenarios
   - Missing resources
   - Invalid item names
   - Circular skill dependencies

---

## Migration Strategy

### Week 1: Foundation
- [ ] Update prompts (Phase 1)
- [ ] Add skill validation (Phase 2)
- [ ] Test with manual JSON responses

### Week 2: Core Refactor
- [ ] Refactor HTNOrchestrator (Phase 3)
- [ ] Simplify SkillExecutor (Phase 4)
- [ ] Add function call extraction (Phase 7)

### Week 3: Integration
- [ ] Update ActionAgent (Phase 5)
- [ ] Update Voyager.py (Phase 5)
- [ ] Add retry logic (Phase 9)

### Week 4: Testing & Polish
- [ ] Integration testing (Phase 10)
- [ ] Remove deprecated code
- [ ] Documentation
- [ ] Performance optimization

---

## Success Metrics

### Functional:
- [ ] LLM generates valid JavaScript skills
- [ ] Validation catches all invalid function calls
- [ ] Skills execute successfully in mineflayer
- [ ] Successful skills are saved and reused
- [ ] Retry logic fixes validation errors

### Architectural:
- [ ] No Python game logic execution
- [ ] Clean separation: LLM writes, HTN validates, Env executes
- [ ] Skills can call other skills
- [ ] Skill library grows over time

### Performance:
- [ ] < 5 seconds for validation
- [ ] < 3 retries average for LLM corrections
- [ ] 90%+ skill reuse rate after 100 tasks

---

## Rollback Plan

If refactor fails or causes regressions:

1. **Git branches**: Keep old system in `old-htn-system` branch
2. **Feature flag**: Add `use_new_htn` flag to toggle systems
3. **Fallback**: Keep old code paths commented but functional
4. **Data migration**: skills.json format should remain compatible

---

## Dependencies and Blockers

### External Dependencies:
- Babel parser (already used in action.py)
- LangChain (already installed)
- ChromaDB (already used)

### Internal Dependencies:
- RecipeFacts must remain functional
- VoyagerEnv execution must remain stable
- SkillManager vector DB must remain synced

### Potential Blockers:
- LLM may struggle with complex skill writing → **Mitigation**: Add examples in prompt
- JavaScript AST parsing may be fragile → **Mitigation**: Extensive testing
- Skill reuse may be low initially → **Mitigation**: Seed with good examples

---

## Open Questions

1. **Skill versioning**: How to handle updated skills? (craftStonePickaxe v1, v2, ...)
2. **Skill parameters**: Should skills take parameters? `await mineBlock(bot, "oak_log", 5)`
3. **Partial success**: What if skill partially completes? Save or discard?
4. **Skill naming**: Snake_case or camelCase? Enforce conventions?
5. **Dependency cycles**: How to detect and handle? (skill A calls B calls A)

**Resolution approach**: Document decisions in ADR (Architecture Decision Records)

---

## Testing Checklist

### Unit Tests:
- [ ] parse_llm_response() with valid/invalid JSON
- [ ] validate_skill_code() with valid/invalid functions
- [ ] extract_function_calls() with various JavaScript patterns
- [ ] decompose_skill_to_primitives() with nested skills

### Integration Tests:
- [ ] Full flow: task → LLM → validate → execute → save
- [ ] Retry logic with validation failures
- [ ] Skill reuse in subsequent tasks
- [ ] Error handling at each stage

### End-to-End Tests:
- [ ] Craft wooden pickaxe (simple)
- [ ] Craft stone pickaxe (medium, needs dependencies)
- [ ] Craft iron pickaxe (complex, needs smelting, mining, crafting)
- [ ] Build shelter (very complex, multiple skills)

### Regression Tests:
- [ ] All existing skills still work
- [ ] Skill manager functions unchanged
- [ ] Environment execution unchanged
- [ ] Critic agent still works

---

## Notes

- Keep this document updated as refactor progresses
- Add lessons learned and gotchas
- Document any deviations from plan
- Track actual time vs estimated time

**Last Updated**: 2025-11-17
