Executor initialized with max recursion depth: 5
=== Using Refactored Learn V2 Architecture ===
[ResetManager] Initial reset: HARD (clearing inventory)
Mineflayer process not running → starting
Subprocess mineflayer started with PID 21240.
Server started on port 3000

[ResetManager] Soft refresh (no restart)
[V2] Initial inventory: {'crafting_table': 1}
****Curriculum Agent human message****
Position: (91.5, 63.0, -860.5)

Equipment: [None, None, None, None, None, None]

Chests: None

Completed tasks so far: None

Failed tasks that are too hard: None


****Curriculum Agent ai message****
Reasoning: As you have no equipment, it's important to start crafting basic tools to help you survive and explore.
Task: Craft 1 wooden pickaxe.
Curriculum Agent Question: How to craft 1 wooden pickaxe in Minecraft?
Curriculum Agent Answer: To craft 1 wooden pickaxe in Minecraft, you will need 3 wooden planks and 2 sticks. Arrange them in a crafting table in the following pattern: place 3 wooden planks across the top row, and then place 2 sticks in the middle and bottom center slots. This will create a wooden pickaxe for you to use in the game.        
C:\Users\Alex\Desktop\Projects\Coding\MinecraftDev\0.3.0\Voyager\voyager\agents\curriculum.py:427: LangChainDeprecationWarning: Since Chroma 0.4.x the manual persistence method is no longer supported as docs are automatically persisted.
  self.qa_cache_questions_vectordb.persist()
[V2] Starting task: Craft 1 wooden pickaxe
[V2] Classified as: TaskSpec(type=craft, params={'item': 'wooden_pickaxe', 'count': 1}, origin=curriculum)
[V2] Execution plan: ExecutionPlan(mode=executor_primitive)
[V2] Using primitive executor
[DEBUG] Normalizing item name: 'wooden_pickaxe'
[DEBUG] After cleanup → 'wooden_pickaxe'
[DEBUG] Matched item: wooden_pickaxe
Discovering skill: craftWoodenPickaxe (depth: 0)
[DEBUG] Extracting item name from skill: craftWoodenPickaxe
[DEBUG] After removing 'craft' prefix: WoodenPickaxe
[DEBUG] Converted to snake_case: wooden_pickaxe
[DEBUG] Checking execution success for 2 events
[DEBUG] Checking event type: onError
[DEBUG] Found error event, returning False: Took to long to decide path to goal!
[DEBUG] Parsing dependencies from 2 events
[DEBUG] Event type: onError
[DEBUG] Error event: Took to long to decide path to goal!
[DEBUG] Event type: observe
[DEBUG] Final dependencies list: []
✗ Failed to craft wooden_pickaxe: no further dependencies
Failed to ensure skill for crafting wooden_pickaxe
Failed to complete task Craft 1 wooden pickaxe. Skipping to next task.
[ResetManager] Soft refresh (no restart)
[V2] Completed:
[V2] Failed: Craft 1 wooden pickaxe
****Curriculum Agent human message****
Position: (85.5, 66.0, -854.7)

Equipment: [None, None, None, None, None, None]

Chests: None

Completed tasks so far: None

Failed tasks that are too hard: Craft 1 wooden pickaxe


****Curriculum Agent ai message****
Reasoning: Since you failed to craft a wooden pickaxe, it seems you need to start with something simpler to understand the crafting process.
Task: Craft 4 wooden planks.
Curriculum Agent Question: How to craft 4 wooden planks in Minecraft?
Curriculum Agent Answer: To craft 4 wooden planks in Minecraft, you need to place one block of wood in any crafting grid. When you do this, you will receive 4 wooden planks.
[V2] Starting task: Craft 4 wooden planks
[V2] Classified as: TaskSpec(type=craft, params={'item': 'wooden_planks', 'count': 4}, origin=curriculum)
[V2] Execution plan: ExecutionPlan(mode=executor_primitive)
[V2] Using primitive executor
[DEBUG] Normalizing item name: '4 wooden_planks'
[DEBUG] After cleanup → 'wooden_planks'
[DEBUG] Trying singular form: 'wooden_plank'
[DEBUG] Normalizing '4 wooden_planks' → 'oak_planks' (auto-correct)
Discovering skill: craftOakPlanks (depth: 0)
[DEBUG] Extracting item name from skill: craftOakPlanks
[DEBUG] After removing 'craft' prefix: OakPlanks
[DEBUG] Converted to snake_case: oak_planks
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: i cannot make oak_planks because i need: 1 more oak_log
[DEBUG] Chat indicates failure, returning False
[DEBUG] Parsing dependencies from 3 events
[DEBUG] Event type: onChat
[DEBUG] Chat message: I cannot make oak_planks because I need: 1 more oak_log
[DEBUG] Matched dependency string: 1 more oak_log
[DEBUG] Extracted dependency: oak_log
[DEBUG] Event type: onError
[DEBUG] Error event: In your program code: throw new Error(`Missing ingredients for ${itemName}`);
Missing ingredients for oak_planks
at line 1:await craftItem(bot, 'oak_planks', 1); in your code
[DEBUG] Event type: observe
[DEBUG] Final dependencies list: ['oak_log']
Missing dependencies for oak_planks: ['oak_log']
Gathering primitive: oak_log
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: collect finish!
[DEBUG] Checking event type: onSave
[DEBUG] Checking event type: observe
[DEBUG] No explicit success/failure indicators, defaulting to True
[LOOP] Retrying craft for oak_planks (attempt 2/5)...
[DEBUG] Checking execution success for 2 events
[DEBUG] Checking event type: onError
[DEBUG] Found error event, returning False: Took to long to decide path to goal!
[DEBUG] Parsing dependencies from 2 events
[DEBUG] Event type: onError
[DEBUG] Error event: Took to long to decide path to goal!
[DEBUG] Event type: observe
[DEBUG] Final dependencies list: []
✗ Failed to craft oak_planks: no further dependencies
Failed to ensure skill for crafting oak_planks
Failed to complete task Craft 4 wooden planks. Skipping to next task.
[ResetManager] Soft refresh (no restart)