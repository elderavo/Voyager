[V2] Starting task: Craft 1 crafting table
[V2] Classified as: TaskSpec(type=craft, params={'item': 'crafting_table', 'count': 1}, origin=curriculum)
[V2] Execution plan: ExecutionPlan(mode=executor_primitive)
[V2] Using primitive executor
[DEBUG] Normalizing item name: 'crafting_table'
[DEBUG] After cleanup → 'crafting_table'
[DEBUG] Matched item: crafting_table
Discovering skill: craftCraftingTable (depth: 0)
[DEBUG] Extracting item name from skill: craftCraftingTable
[DEBUG] After removing 'craft' prefix: CraftingTable
[DEBUG] Converted to snake_case: crafting_table
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: i cannot make crafting_table because i need: 4 more oak_planks
[DEBUG] Chat indicates failure, returning False
[DEBUG] Parsing dependencies from 3 events
[DEBUG] Event type: onChat
[DEBUG] Chat message: I cannot make crafting_table because I need: 4 more oak_planks
[DEBUG] Matched dependency string: 4 more oak_planks
[DEBUG] Extracted dependency: oak_planks
[DEBUG] Event type: onError
[DEBUG] Error event: In your program code: throw new Error(`Missing ingredients for ${itemName}`);
Missing ingredients for crafting_table
at line 1:await craftItem(bot, 'crafting_table', 1); in your code
[DEBUG] Event type: observe
[DEBUG] Final dependencies list: ['oak_planks']
Missing dependencies for crafting_table: ['oak_planks']
Attempting to craft dependency: oak_planks
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: i cannot make oak_planks because i need: 1 more oak_log
[DEBUG] Chat indicates failure, returning False
Crafting oak_planks failed, checking if it's gatherable...
Recursively discovering skill for: oak_planks
Discovering skill: craftOakPlanks (depth: 1)
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
Attempting to craft dependency: oak_log
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: craftitem: no crafting-table recipe for 'oak_log'
[DEBUG] Checking event type: onError
[DEBUG] Found error event, returning False: In your program code: throw new Error(`Recipe not found for ${itemName}`);
Recipe not found for oak_log
at line 1:await craftItem(bot, 'oak_log', 1); in your code
Crafting oak_log failed, checking if it's gatherable...
Recursively discovering skill for: oak_log
Discovering skill: craftOakLog (depth: 2)
[DEBUG] Extracting item name from skill: craftOakLog
[DEBUG] After removing 'craft' prefix: OakLog
[DEBUG] Converted to snake_case: oak_log
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: craftitem: no crafting-table recipe for 'oak_log'
[DEBUG] Checking event type: onError
[DEBUG] Found error event, returning False: In your program code: throw new Error(`Recipe not found for ${itemName}`);
Recipe not found for oak_log
at line 1:await craftItem(bot, 'oak_log', 1); in your code
[DEBUG] Parsing dependencies from 3 events
[DEBUG] Event type: onChat
[DEBUG] Chat message: craftItem: No crafting-table recipe for 'oak_log'
[DEBUG] Event type: onError
[DEBUG] Error event: In your program code: throw new Error(`Recipe not found for ${itemName}`);
Recipe not found for oak_log
at line 1:await craftItem(bot, 'oak_log', 1); in your code
[DEBUG] Event type: observe
[DEBUG] Final dependencies list: []
✗ Failed to craft oak_log: no further dependencies
✗ Failed to obtain dependency: oak_log
✗ Failed to obtain dependency: oak_planks
Failed to ensure skill for crafting crafting_table
Failed to complete task Craft 1 crafting table. Skipping to next task.
[ResetManager] Soft refresh (no restart)