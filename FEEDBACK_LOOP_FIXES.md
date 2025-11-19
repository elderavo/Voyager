# Feedback Loop Analysis & Fixes

## Problems Identified from latest_run.md

### Problem 1: Code Analyzer Bug - `bot.inventory.count()` Detected as Unknown Function
**Lines 15-16, 72-73, 129-130 in latest_run.md:**
```
[HTN] Validation failed: Unknown functions: ['count']
Available functions: ['craftItem', 'exploreUntil', 'killMob', 'mineBlock', 'mineWoodLog', ...]
```

**Root Cause:**
The code analyzer was extracting `count` from `bot.inventory.count()` and flagging it as an unknown function. The issue was in the MemberExpression handler - it checked if the immediate parent was `bot`, but didn't handle nested chains like `bot.inventory.count()` where the root is `bot` but the immediate parent is `bot.inventory`.

**Fix Applied:** ✅
Added `_is_builtin_api_call()` method that recursively walks up the member expression chain to find the root object:
```python
def _is_builtin_api_call(self, member_expr):
    """Walk up chain: bot.inventory.count() -> finds 'bot' -> returns True"""
    current = member_expr
    while self._safe_get(current, 'type') == 'MemberExpression':
        obj = self._safe_get(current, 'object', {})
        if self._safe_get(obj, 'type') == 'Identifier':
            root_name = self._safe_get(obj, 'name')
            return root_name in ('bot', 'mcData', 'Vec3', 'goals', 'pathfinder')
        current = obj
    return False
```

---

### Problem 2: Infinite Retry Loop - No Error Feedback to LLM
**Lines 24-27, 82-85, 140-143 in latest_run.md:**
```
****Action Agent human message****
Code from the last round: No code in the first round  # ← ALWAYS SAYS THIS!

Execution error: No error  # ← ERROR NOT PROPAGATED!
```

**Root Cause:**
In [voyager.py:373-377](voyager/voyager.py#L373-L377), when validation fails (string result), the error is printed but `self.messages` is NOT updated:

```python
else:
    assert isinstance(parsed_result, str)
    self.recorder.record([], self.task)
    print(f"\033[34m{parsed_result} Trying again!\033[0m")
    success = False  # String result means failure - need to retry
    # ← MISSING: self.messages should be updated here!
```

So the LLM never sees:
- What code it generated last time
- What error occurred
- That it should try a different approach

**Result:** LLM generates EXACT SAME CODE 4 times in a row.

**Fix Needed:** Update `self.messages` with error feedback before retry.

---

### Problem 3: Action Agent Writing Inventory Checks (Against Design Intent)
**Lines 5-7, 62-64, 119-121 in latest_run.md:**
```javascript
async function obtainOakLogs(bot) {
  const oakLogCount = bot.inventory.count(mcData.itemsByName.oak_log.id);  // ← UNWANTED
  if (oakLogCount < 3) {  // ← UNWANTED
    bot.chat('Need more oak logs');
    await mineBlock(bot, 'oak_log', 3 - oakLogCount);  // ← UNWANTED CALCULATION
  }
  bot.chat('Obtained 3 oak logs!');
}
```

**Design Intent (per user):**
- ✅ Action Agent: Write recipe execution code ONLY (no inventory checks, no conditionals)
- ✅ HTN Orchestrator: Handle inventory checks and runtime pruning
- ✅ Mineflayer primitives: Handle their own preconditions

**What Action Agent SHOULD Generate:**
```javascript
async function obtainOakLogs(bot) {
  await mineBlock(bot, 'oak_log', 3);
  bot.chat('Obtained 3 oak logs!');
}
```

**Fix Needed:** Update action agent prompt to forbid inventory checks.

---

### Problem 4: Creating New Functions Instead of Using Primitives
**Lines 5, 62, 119 in latest_run.md:**
```javascript
async function obtainOakLogs(bot) {  // ← NEW FUNCTION
  await mineBlock(bot, 'oak_log', 3);  // ← PRIMITIVE ALREADY EXISTS!
}
```

**Available Primitives:**
- `mineBlock(bot, blockType, count)` - exists!
- `mineWoodLog(bot)` - exists! (specialized for mining 1 wood log)

**What Action Agent SHOULD Have Done:**
For "Obtain 3 oak logs":
```json
{
  "program_code": "await mineBlock(bot, 'oak_log', 3);",
  "program_name": "obtainOakLogs",  // Name for skill library
  "reasoning": "Use mineBlock primitive to collect 3 oak logs directly"
}
```

Or even better - just execute the primitive directly without creating a new skill:
```json
{
  "program_code": "",  // No new code needed
  "program_name": "",  // Not saving this
  "exec_code": "await mineBlock(bot, 'oak_log', 3);",  // Direct execution
  "reasoning": "Task is simple - just call mineBlock primitive"
}
```

**Fix Needed:** Update action agent prompt to prefer primitives over creating new functions.

---

## Fixes Implementation Plan

### Fix 1: Code Analyzer ✅ DONE
- [x] Added `_is_builtin_api_call()` method
- [x] Updated `_visit_ast()` to use it
- [x] Now correctly ignores `bot.inventory.count()`, `bot.pathfinder.goto()`, etc.

### Fix 2: Error Feedback Loop (CRITICAL)
**File:** [voyager/voyager.py](voyager/voyager.py#L373-L377)

**Current Code:**
```python
else:
    assert isinstance(parsed_result, str)
    self.recorder.record([], self.task)
    print(f"\033[34m{parsed_result} Trying again!\033[0m")
    success = False
# ← Messages NOT updated! LLM doesn't see error!
```

**Fixed Code:**
```python
else:
    assert isinstance(parsed_result, str)
    self.recorder.record([], self.task)
    print(f"\033[34m{parsed_result} Trying again!\033[0m")
    success = False

    # CRITICAL FIX: Add error feedback to conversation
    # Get the last AI message (failed code generation)
    last_ai_message = self.conversations[-1][2] if self.conversations else ""

    # Create error feedback message
    error_human_message = self.action_agent.render_human_message(
        events=[],  # No events since validation failed
        code=last_ai_message,  # Show the code that failed
        task=self.task,
        context=self.context,
        critique=parsed_result  # The validation error becomes critique
    )

    # Update messages for next retry
    self.messages = [self.messages[0], error_human_message]  # Keep system msg, update human msg
```

### Fix 3: Remove Inventory Checks from Action Agent Prompts
**Files to Update:**
1. [voyager/prompts/action_template.txt](voyager/prompts/action_template.txt)
2. [voyager/prompts/action_response_format.txt](voyager/prompts/action_response_format.txt)

**Changes Needed:**

**In action_template.txt:**
```diff
Your job is to write a JavaScript function to accomplish the task by:
1. Analyzing the current state (inventory, resources, position, equipment)
2. Writing a complete async function that handles the task
-3. Using ONLY the primitives and known skills listed above
-4. Calling other skills or primitives to handle missing dependencies
-5. Calling the minimum number of skills necessary.
-6. Using bot.chat() to communicate progress and issues
+3. Writing PURE RECIPE CODE - no inventory checks, no conditionals for missing items
+4. Using ONLY the primitives and known skills listed above
+5. Calling the minimum number of skills/primitives necessary (prefer direct primitives!)
+6. Using bot.chat() to communicate progress ONLY

IMPORTANT RULES:
- You MUST write a complete async function
- You MUST name the function appropriately (e.g., craftStonePickaxe, mineIronOre)
- You MUST pass ALL required arguments to primitives (e.g., mineBlock(bot, 'stone', 3))
-- You MAY NOT skip crafting items, even if they are currently in inventory
-- You MAY call mineflayer primitives (mineBlock, craftItem, smeltItem, placeItem, killMob, etc.)
+- You MAY call mineflayer primitives (mineBlock, craftItem, etc.) - PREFER THESE!
- You MAY call known skills that are listed above
-- You MAY NOT call functions that don't exist in the available lists
-- You MAY NOT handle inventory checks and missing materials within your code
-- You MUST use bot.inventory.count(mcData.itemsByName.item_name.id) to check quantities
-- You SHOULD call other skills/primitives to gather missing materials
+- You MAY NOT call functions that don't exist
+- You MAY NOT write inventory checks (bot.inventory.count, if statements for items, etc.)
+- You MAY NOT write conditional logic for missing materials
+- Primitives handle their own preconditions - just call them with the required quantities!
- Arguments MUST be concrete values or expressions (bot, 'stone', 3, bot.inventory.count(...), etc.)
+- If the task is simple, prefer calling a primitive directly over creating a new function
- String literals MUST be quoted (e.g., 'stone', "oak_log")
```

**In action_response_format.txt:**
```diff
Rules:
- "program_code" must be a complete, valid JavaScript async function
- The function must be named according to "program_name"
- The function must take a single parameter: bot
-- You must use ONLY known skills from the available list, only use primitives if necessary.
+- You must PREFER primitives over skills when possible (primitives are more reliable)
+- For simple tasks, just call the primitive directly (no new function needed)
- ALL primitive calls must include their required arguments (e.g., mineBlock(bot, 'stone', 3))
- Arguments will be extracted and queued for sequential execution
-- Check inventory before using items: bot.inventory.count(mcData.itemsByName.item_name.id)
-- Handle missing materials by calling other skills/primitives
+- DO NOT check inventory - primitives handle this automatically
+- DO NOT write conditional logic for missing items
- Use bot.chat() to communicate what you're doing

Example output:
```json
{
-  "program_code": "async function craftStonePickaxe(bot) {\n  const cobblestoneCount = bot.inventory.count(mcData.itemsByName.cobblestone.id);\n  const sticksCount = bot.inventory.count(mcData.itemsByName.stick.id);\n  \n  if (cobblestoneCount < 3) {\n    bot.chat('Need more cobblestone');\n    await mineBlock(bot, 'stone', 3 - cobblestoneCount);\n  }\n  \n  if (sticksCount < 2) {\n    bot.chat('Need sticks');\n    await craftItem(bot, 'stick', 2 - sticksCount);\n  }\n  \n  await craftItem(bot, 'stone_pickaxe', 1);\n  bot.chat('Stone pickaxe crafted!');\n}",
+  "program_code": "async function craftStonePickaxe(bot) {\n  bot.chat('Crafting stone pickaxe');\n  await mineBlock(bot, 'stone', 3);\n  await craftItem(bot, 'stick', 2);\n  await craftItem(bot, 'stone_pickaxe', 1);\n  bot.chat('Stone pickaxe crafted!');\n}",
   "program_name": "craftStonePickaxe",
   "reasoning": "Mine cobblestone, craft sticks, then craft the pickaxe"
}
```
```

### Fix 4: Prefer Primitives Over New Functions
**Add decision tree to prompt:**

```
DECISION TREE: Should I create a new function or use existing primitives?

1. Is this task a SINGLE primitive call with simple arguments?
   → YES: Use exec_code with the primitive directly (no new function)
   → Example: "Obtain 3 oak logs" → `await mineBlock(bot, 'oak_log', 3);`

2. Is this task 2-3 sequential primitive calls?
   → Create a simple function that chains the primitives
   → Example: "Craft wooden pickaxe" → function that calls mineBlock + craftItem

3. Is there already a skill that does EXACTLY this?
   → Call the existing skill (don't reinvent it)
   → Example: "Mine 1 wood log" → use mineWoodLog skill

4. Is this task complex with multiple steps/branches?
   → Create a new function combining primitives and skills
   → Example: "Build a house" → complex multi-step function

EXAMPLES:

Task: "Obtain 3 oak logs"
Available: mineBlock(bot, blockType, count)
Decision: SINGLE primitive call
Output:
{
  "program_code": "await mineBlock(bot, 'oak_log', 3);",
  "program_name": "obtainOakLogs",
  "reasoning": "Simple task - just mine 3 oak logs using mineBlock primitive"
}

Task: "Craft 4 wooden planks"
Available: craftItem(bot, itemType, count)
Decision: SINGLE primitive call
Output:
{
  "program_code": "await craftItem(bot, 'oak_planks', 4);",
  "program_name": "craftWoodenPlanks",
  "reasoning": "Simple crafting task - use craftItem primitive directly"
}

Task: "Craft stone pickaxe"
Available: mineBlock, craftItem
Decision: 2-3 sequential primitives (create function)
Output:
{
  "program_code": "async function craftStonePickaxe(bot) {\n  await mineBlock(bot, 'stone', 3);\n  await craftItem(bot, 'stick', 2);\n  await craftItem(bot, 'stone_pickaxe', 1);\n  bot.chat('Stone pickaxe crafted!');\n}",
  "program_name": "craftStonePickaxe",
  "reasoning": "Multi-step recipe: mine cobblestone, craft sticks, craft pickaxe"
}
```

---

## Testing the Fixes

### Test Case 1: bot.inventory.count() Should Not Be Flagged ✅
```python
code = """
async function test(bot) {
  const count = bot.inventory.count(mcData.itemsByName.oak_log.id);
  await mineBlock(bot, 'oak_log', 3);
}
"""
analyzer = JavaScriptAnalyzer()
calls = analyzer.extract_function_calls(code)
# Expected: ['mineBlock']
# Should NOT include 'count'
```

### Test Case 2: Error Feedback Should Update Messages
```python
# After validation error:
assert self.messages[1].content.contains("Validation Error")
assert self.messages[1].content.contains("Unknown functions: ['count']")
assert "Code from the last round" in self.messages[1].content
# LLM should see the error and previous code on next retry
```

### Test Case 3: Simple Task Should Use Primitive Directly
```
Task: "Obtain 3 oak logs"
Expected Output:
{
  "program_code": "await mineBlock(bot, 'oak_log', 3);",
  "program_name": "obtainOakLogs",
  "reasoning": "Use mineBlock primitive directly"
}

Should NOT generate:
- Inventory checks: bot.inventory.count()
- Conditionals: if (oakLogCount < 3)
- New complex functions when primitive exists
```

---

## Summary of Design Intent

### Action Agent Responsibilities
✅ **SHOULD:**
- Generate pure recipe code (sequence of primitive/skill calls)
- Use primitives directly for simple tasks
- Create functions only when combining 3+ primitives
- Include ALL required arguments in primitive calls
- Use bot.chat() for progress updates

❌ **SHOULD NOT:**
- Check inventory (`bot.inventory.count()`)
- Write conditional logic for missing items
- Handle resource gathering preconditions
- Create new functions when primitives already exist
- Skip required steps

### HTN Orchestrator Responsibilities
✅ **SHOULD:**
- Validate function calls against known primitives/skills
- Decompose skills into primitive task queue
- Check inventory at runtime before executing primitives
- Prune tasks that are already satisfied
- Handle primitive failures and retries

### Mineflayer Primitives Responsibilities
✅ **SHOULD:**
- Handle their own preconditions (find blocks, check tools, etc.)
- Throw errors if preconditions can't be met
- Return success/failure to HTN orchestrator
- Emit progress events for monitoring

---

## Next Steps

1. ✅ **Code analyzer bug** - FIXED
2. ⏳ **Error feedback loop** - Needs implementation in voyager.py
3. ⏳ **Action agent prompts** - Needs updates to remove inventory checks
4. ⏳ **Primitive preference** - Needs decision tree in prompts

Would you like me to implement fixes 2-4?