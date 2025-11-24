-- Test 1 ---
****Executor Mode: Crafting wooden pickaxe****
[DEBUG] Normalizing item name: 'wooden pickaxe'
[DEBUG] After cleanup → 'wooden_pickaxe'
[DEBUG] Matched item: wooden_pickaxe
Discovering skill: craftWoodenPickaxe (depth: 0)
[DEBUG] Extracting item name from skill: craftWoodenPickaxe
[DEBUG] After removing 'craft' prefix: WoodenPickaxe
[DEBUG] Converted to snake_case: wooden_pickaxe
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: i cannot make wooden_pickaxe because i need: 3 more oak_planks, 2 more stick
[DEBUG] Chat indicates failure, returning False
[DEBUG] Parsing dependencies from 3 events
[DEBUG] Event type: onChat
[DEBUG] Chat message: I cannot make wooden_pickaxe because I need: 3 more oak_planks, 2 more stick
[DEBUG] Matched dependency string: 3 more oak_planks, 2 more stick
[DEBUG] Extracted dependency: oak_planks
[DEBUG] Extracted dependency: stick
[DEBUG] Event type: onError
[DEBUG] Error event: In your program code: throw new Error(`Missing ingredients for ${itemName}`);
Missing ingredients for wooden_pickaxe
at line 1:await craftItem(bot, 'wooden_pickaxe', 1); in your code
[DEBUG] Event type: observe
[DEBUG] Final dependencies list: ['oak_planks', 'stick']
Missing dependencies for wooden_pickaxe: ['oak_planks', 'stick']
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
Gathering primitive: oak_log
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: collect finish!
[DEBUG] Chat indicates success, returning True
[LOOP] Retrying craft for oak_planks after resolving deps...
[DEBUG] Checking execution success for 2 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: [craft:done] crafted 1 oak_planks
[DEBUG] Chat indicates success, returning True
✓ Craft succeeded for oak_planks
Synthesized skill craftOakPlanks:
async function craftOakPlanks(bot) {
  await mineBlock(bot, 'oak_log', 1);
  await craftItem(bot, 'oak_planks', 1);
}
Skill Manager generated description for craftOakPlanks:
async function craftOakPlanks(bot) {
    // The function crafts oak planks by first mining an oak log and then crafting it into oak planks.
}
C:\Users\Alex\Desktop\Projects\Coding\Minecraft_master\voyager\agents\skill.py:110: LangChainDeprecationWarning: Since Chroma 0.4.x the manual persistence method is no longer supported as docs are automatically persisted.
  self.vectordb.persist()
✓ Registered skill: craftOakPlanks
Recursively discovering skill for: stick
Discovering skill: craftStick (depth: 1)
[DEBUG] Extracting item name from skill: craftStick
[DEBUG] After removing 'craft' prefix: Stick
[DEBUG] Converted to snake_case: stick
[DEBUG] Checking execution success for 2 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: [craft:done] crafted 1 stick
[DEBUG] Chat indicates success, returning True
✓ Craft succeeded for stick
Synthesized skill craftStick:
async function craftStick(bot) {
  await craftItem(bot, 'stick', 1);
}
Skill Manager generated description for craftStick:
async function craftStick(bot) {
    // The function crafts a stick by calling a helper function to craft the item 'stick' once.
}
✓ Registered skill: craftStick
[LOOP] Retrying craft for wooden_pickaxe after resolving deps...
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: i cannot make wooden_pickaxe because i need: 1 more oak_planks
[DEBUG] Chat indicates failure, returning False
[DEBUG] Parsing dependencies from 3 events
[DEBUG] Event type: onChat
[DEBUG] Chat message: I cannot make wooden_pickaxe because I need: 1 more oak_planks
[DEBUG] Matched dependency string: 1 more oak_planks
[DEBUG] Extracted dependency: oak_planks
[DEBUG] Event type: onError
[DEBUG] Error event: In your program code: throw new Error(`Missing ingredients for ${itemName}`);
Missing ingredients for wooden_pickaxe
at line 1:await craftItem(bot, 'wooden_pickaxe', 1); in your code
[DEBUG] Event type: observe
[DEBUG] Final dependencies list: ['oak_planks']
Missing dependencies for wooden_pickaxe: ['oak_planks']
Executing known skill for dependency: craftOakPlanks
Executing skill: craftOakPlanks
[DEBUG] Checking execution success for 5 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: collect finish!
[DEBUG] Chat indicates success, returning True
[LOOP] Retrying craft for wooden_pickaxe after resolving deps...
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: i cannot make wooden_pickaxe because i need: 1 more oak_planks
[DEBUG] Chat indicates failure, returning False
[DEBUG] Parsing dependencies from 3 events
[DEBUG] Event type: onChat
[DEBUG] Chat message: I cannot make wooden_pickaxe because I need: 1 more oak_planks
[DEBUG] Matched dependency string: 1 more oak_planks
[DEBUG] Extracted dependency: oak_planks
[DEBUG] Event type: onError
[DEBUG] Error event: In your program code: throw new Error(`Missing ingredients for ${itemName}`);
Missing ingredients for wooden_pickaxe
at line 1:await craftItem(bot, 'wooden_pickaxe', 1); in your code
[DEBUG] Event type: observe
[DEBUG] Final dependencies list: ['oak_planks']
Missing dependencies for wooden_pickaxe: ['oak_planks']
Executing known skill for dependency: craftOakPlanks
Executing skill: craftOakPlanks
[DEBUG] Checking execution success for 5 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: collect finish!
[DEBUG] Chat indicates success, returning True
[LOOP] Retrying craft for wooden_pickaxe after resolving deps...
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: i cannot make wooden_pickaxe because i need: 1 more oak_planks
[DEBUG] Chat indicates failure, returning False
[DEBUG] Parsing dependencies from 3 events
[DEBUG] Event type: onChat
[DEBUG] Chat message: I cannot make wooden_pickaxe because I need: 1 more oak_planks
[DEBUG] Matched dependency string: 1 more oak_planks
[DEBUG] Extracted dependency: oak_planks
[DEBUG] Event type: onError
[DEBUG] Error event: In your program code: throw new Error(`Missing ingredients for ${itemName}`);
Missing ingredients for wooden_pickaxe
at line 1:await craftItem(bot, 'wooden_pickaxe', 1); in your code
[DEBUG] Event type: observe
[DEBUG] Final dependencies list: ['oak_planks']
Missing dependencies for wooden_pickaxe: ['oak_planks']
Executing known skill for dependency: craftOakPlanks
Executing skill: craftOakPlanks
[DEBUG] Checking execution success for 5 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: collect finish!
[DEBUG] Chat indicates success, returning True
[LOOP] Retrying craft for wooden_pickaxe after resolving deps...
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: i cannot make wooden_pickaxe because i need: 1 more oak_planks
[DEBUG] Chat indicates failure, returning False
[DEBUG] Parsing dependencies from 3 events
[DEBUG] Event type: onChat
[DEBUG] Chat message: I cannot make wooden_pickaxe because I need: 1 more oak_planks
[DEBUG] Matched dependency string: 1 more oak_planks
[DEBUG] Extracted dependency: oak_planks
[DEBUG] Event type: onError
[DEBUG] Error event: In your program code: throw new Error(`Missing ingredients for ${itemName}`);
Missing ingredients for wooden_pickaxe
at line 1:await craftItem(bot, 'wooden_pickaxe', 1); in your code
[DEBUG] Event type: observe
[DEBUG] Final dependencies list: ['oak_planks']
Missing dependencies for wooden_pickaxe: ['oak_planks']
Executing known skill for dependency: craftOakPlanks
Executing skill: craftOakPlanks
[DEBUG] Checking execution success for 5 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: collect finish!
[DEBUG] Chat indicates success, returning True
[LOOP] Retrying craft for wooden_pickaxe after resolving deps...
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: i cannot make wooden_pickaxe because i need: 1 more oak_planks
[DEBUG] Chat indicates failure, returning False
[DEBUG] Parsing dependencies from 3 events
[DEBUG] Event type: onChat
[DEBUG] Chat message: I cannot make wooden_pickaxe because I need: 1 more oak_planks
[DEBUG] Matched dependency string: 1 more oak_planks
[DEBUG] Extracted dependency: oak_planks
[DEBUG] Event type: onError
[DEBUG] Error event: In your program code: throw new Error(`Missing ingredients for ${itemName}`);
Missing ingredients for wooden_pickaxe
at line 1:await craftItem(bot, 'wooden_pickaxe', 1); in your code
[DEBUG] Event type: observe
[DEBUG] Final dependencies list: ['oak_planks']
Missing dependencies for wooden_pickaxe: ['oak_planks']
Executing known skill for dependency: craftOakPlanks
Executing skill: craftOakPlanks
[DEBUG] Checking execution success for 5 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: collect finish!
[DEBUG] Chat indicates success, returning True
[LOOP] Retrying craft for wooden_pickaxe after resolving deps...
[DEBUG] Checking execution success for 2 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: [craft:done] crafted 1 wooden_pickaxe
[DEBUG] Chat indicates success, returning True
✓ Craft succeeded for wooden_pickaxe
Synthesized skill craftWoodenPickaxe:
async function craftWoodenPickaxe(bot) {
  await craftOakPlanks(bot);
  await craftStick(bot);
  await craftOakPlanks(bot);
  await craftOakPlanks(bot);
  await craftOakPlanks(bot);
  await craftOakPlanks(bot);
  await craftOakPlanks(bot);
  await craftItem(bot, 'wooden_pickaxe', 1);
}
Skill Manager generated description for craftWoodenPickaxe:
async function craftWoodenPickaxe(bot) {
    // The function crafts a wooden pickaxe by crafting oak planks and sticks, then combining them to create the wooden pickaxe.
}
✓ Registered skill: craftWoodenPickaxe
Executing skill: craftWoodenPickaxe
[DEBUG] Checking execution success for 5 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: collect finish!
[DEBUG] Chat indicates success, returning True
[DEBUG] Executor returned success=True, events count=5