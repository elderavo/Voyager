# TODO: Mineflayer still start/stop/starting on run_voyager.py start. 
# TODO: Find the hard-coded list of "immediate gather" blocks somehwere. 

# NOTE: Now, gathering primitives call the action bot. This seems correct - let executor module decompose craft tasks, let action bot do what executor cant. 
# NOTE: bot got stuck in water last run. 

# NEXT: See how bot handles being tasked to do something like "craft stone pick" that decomposes to something executor can't do itself (mine cobblestone)

Executor initialized with max recursion depth: 5
[DEBUG] Starting fresh with HARD reset (clearing inventory)
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 11456.
Server started on port 3000

[DEBUG] Initial inventory after reset: {'crafting_table': 1}
****Curriculum Agent human message****
Nearby blocks: dirt, stone, grass_block, grass, tall_grass

Position: x=-172.5, y=65.0, z=-580.5

Equipment: [None, None, None, None, 'crafting_table', None]

Inventory (1/36): {'crafting_table': 1}

Chests: None

Completed tasks so far: None

Failed tasks that are too hard: None


****Curriculum Agent ai message****
Reasoning: You are just starting out in the game and you don't have any tools or equipment. The first thing you need to do is to gather some basic resources. Wood is a versatile resource that can be used to craft a variety of items, including tools and weapons.
Task: Obtain a wood log.
Curriculum Agent Question: How to obtain a wood log in Minecraft?
Curriculum Agent Answer: To obtain a wood log in Minecraft, you can start by punching a tree. When you punch a tree, you will see wood blocks breaking off. Collect these wood blocks by walking over them, and they will turn into wood logs in your inventory.
C:\Users\Alex\Desktop\Projects\Coding\Minecraft_master\voyager\agents\curriculum.py:442: LangChainDeprecationWarning: Since Chroma 0.4.x the manual persistence method is no longer supported as docs are automatically persisted.
  self.qa_cache_questions_vectordb.persist()
Starting task Obtain a wood log for at most 4 times
Render Action Agent system message with 0 skills
****Action Agent human message****
Code from the last round: No code in the first round

Execution error: No error

Chat log: None

Biome:

Time: midnight

Nearby blocks: dirt, stone, grass_block, grass, tall_grass

Nearby entities (nearest to farthest): bat

Health: 20.0/20

Hunger: 20.0/20

Position: x=-172.5, y=65.0, z=-580.5

Equipment: [None, None, None, None, 'crafting_table', None]

Inventory (1/36): {'crafting_table': 1}

Chests: None

Task: Obtain a wood log

Context: Question: How to obtain a wood log in Minecraft?
Answer: To obtain a wood log in Minecraft, you can start by punching a tree. When you punch a tree, you will see wood blocks breaking off. Collect these wood blocks by walking over them, and they will turn into wood logs in your inventory.

Critique: None


****Action Agent ai message****
Explain: There is no error or chat log to explain as this is the first task.

Plan:
1) Use the `exploreUntil` function to find a tree (wood log).
2) Use the `mineBlock` function to mine the wood log.

Code:
```javascript
async function obtainWoodLog(bot) {
    // Find a tree
    const tree = await exploreUntil(bot, new Vec3(1, 0, 1), 60, () => {
        const tree = bot.findBlock({
            matching: mcData.blocksByName["oak_log"].id,
            maxDistance: 32,
        });
        return tree;
    });

    // Mine the tree
    if (tree) {
        await mineBlock(bot, "oak_log", 1);
        bot.chat("Wood log obtained.");
    } else {
        bot.chat("No tree found.");
    }
}
```
****Recorder message: 226 ticks have elapsed****
****Recorder message: 1 iteration passed****
****Critic Agent human message****
Biome:

Time: midnight

Nearby blocks: dirt, grass_block, grass, oxeye_daisy, azure_bluet, dandelion, cornflower, water, tall_grass, pumpkin, oak_log, crafting_table

Health: 20.0/20

Hunger: 20.0/20

Position: x=-166.5, y=64.0, z=-565.5

Equipment: [None, None, None, None, 'crafting_table', None]

Inventory (2/36): {'crafting_table': 1, 'oak_log': 1}

Chests: None

Task: Obtain a wood log

Context: Question: How to obtain a wood log in Minecraft?
Answer: To obtain a wood log in Minecraft, you can start by punching a tree. When you punch a tree, you will see wood blocks breaking off. Collect these wood blocks by walking over them, and they will turn into wood logs in your inventory.


****Critic Agent ai message****
{
    "reasoning": "You have 1 oak_log in your inventory, which means you successfully obtained a wood log.",
    "success": true,
    "critique": ""
}
[DEBUG] Getting fresh state after task (soft refresh, no restart)
[DEBUG] Inventory after task: {'crafting_table': 1, 'oak_log': 2}
Skill Manager generated description for obtainWoodLog:
async function obtainWoodLog(bot) {
    // The function is about obtaining a wood log by finding a tree in the environment. It explores the area until locating an oak tree. Once the tree is found, it mines a single oak log block. If successful, it sends a message indicating that a wood log has been obtained; otherwise, it notifies that no tree was found.
}
Completed task Obtain a wood log.
Completed tasks: Obtain a wood log
Failed tasks:
****Curriculum Agent human message****
Nearby blocks: dirt, grass_block, grass, oxeye_daisy, azure_bluet, dandelion, cornflower, tall_grass, pumpkin, oak_log, crafting_table

Position: x=-166.5, y=65.0, z=-564.5

Equipment: [None, None, None, None, 'crafting_table', None]

Inventory (2/36): {'crafting_table': 1, 'oak_log': 2}

Chests: None

Completed tasks so far: Obtain a wood log

Failed tasks that are too hard: None


****Curriculum Agent ai message****
Reasoning: You have some oak logs in your inventory. You can use these to craft wooden planks, which are a basic building material and can be used to craft a variety of items.
Task: Craft 4 wooden planks.
Curriculum Agent Question: How to craft 4 wooden planks in Minecraft?
Curriculum Agent Answer: To craft 4 wooden planks in Minecraft, you need to place one block of wood in any crafting grid. When you do this, it will turn into 4 wooden planks.
Starting task Craft 4 wooden planks for at most 4 times
[Executor Mode] Crafting: 4 wooden planks
[DEBUG] Current inventory before crafting: {'crafting_table': 1, 'oak_log': 2}
****Executor Mode: Crafting 4 wooden planks****
[DEBUG] Normalizing item name: '4 wooden planks'
[DEBUG] After cleanup → 'wooden_planks'
[DEBUG] Trying singular form: 'wooden_plank'
[DEBUG] Normalizing '4 wooden planks' → 'oak_planks' (auto-correct)
Discovering skill: craftOakPlanks (depth: 0)
[DEBUG] Extracting item name from skill: craftOakPlanks
[DEBUG] After removing 'craft' prefix: OakPlanks
[DEBUG] Converted to snake_case: oak_planks
[DEBUG] Checking execution success for 2 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: [craft:done] crafted 1 oak_planks
[DEBUG] Chat indicates success, returning True
✓ Craft succeeded for oak_planks
Synthesized skill craftOakPlanks:
async function craftOakPlanks(bot) {
  await craftItem(bot, 'oak_planks', 1);
}
Skill Manager generated description for craftOakPlanks:
async function craftOakPlanks(bot) {
    // The function crafts 1 oak plank using the crafting table.
}
✓ Registered skill: craftOakPlanks
[QUANTITY] Crafting additional copy 2/4
Executing skill: craftOakPlanks
[DEBUG] Checking execution success for 2 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: [craft:done] crafted 1 oak_planks
[DEBUG] Chat indicates success, returning True
[QUANTITY] Crafting additional copy 3/4
Executing skill: craftOakPlanks
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: i cannot make oak_planks because i need: 1 more oak_log
[DEBUG] Chat indicates failure, returning False
[QUANTITY] Failed at copy 3/4
[DEBUG] Executor returned success=False, events count=5
[DEBUG] Getting fresh state after task (soft refresh, no restart)
[DEBUG] Inventory after task: {'oak_planks': 8, 'crafting_table': 1}
Failed to complete task Craft 4 wooden planks. Skipping to next task.
Completed tasks: Obtain a wood log
Failed tasks: Craft 4 wooden planks
****Curriculum Agent human message****
Nearby blocks: dirt, grass_block, grass, cornflower, water, tall_grass, oxeye_daisy, dandelion, pumpkin, azure_bluet, crafting_table

Position: x=-164.5, y=64.0, z=-566.5

Equipment: [None, None, None, None, 'crafting_table', None]

Inventory (2/36): {'oak_planks': 8, 'crafting_table': 1}

Chests: None

Completed tasks so far: Obtain a wood log

Failed tasks that are too hard: Craft 4 wooden planks


****Curriculum Agent ai message****
Reasoning: You have oak planks in your inventory and a crafting table nearby. You can use these to craft a wooden pickaxe, which will allow you to mine stone and other harder blocks.
Task: Craft a wooden pickaxe.
Curriculum Agent Question: How to craft a wooden pickaxe in Minecraft?
Curriculum Agent Answer: To craft a wooden pickaxe in Minecraft, you will need three wooden planks and two sticks. Place the wooden planks in the top row of the crafting table, with one in the middle slot and one in the right slot. Then, place the sticks in the middle slot and bottom slot of the crafting table. This will create a wooden pickaxe for you to use in the game.
Starting task Craft a wooden pickaxe for at most 4 times
[Executor Mode] Crafting: a wooden pickaxe
[DEBUG] Current inventory before crafting: {'oak_planks': 8, 'crafting_table': 1}
****Executor Mode: Crafting a wooden pickaxe****
[DEBUG] Normalizing item name: 'a wooden pickaxe'
[DEBUG] After cleanup → 'wooden_pickaxe'
[DEBUG] Matched item: wooden_pickaxe
Discovering skill: craftWoodenPickaxe (depth: 0)
[DEBUG] Extracting item name from skill: craftWoodenPickaxe
[DEBUG] After removing 'craft' prefix: WoodenPickaxe
[DEBUG] Converted to snake_case: wooden_pickaxe
[DEBUG] Checking execution success for 3 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: i cannot make wooden_pickaxe because i need: 2 more stick
[DEBUG] Chat indicates failure, returning False
[DEBUG] Parsing dependencies from 3 events
[DEBUG] Event type: onChat
[DEBUG] Chat message: I cannot make wooden_pickaxe because I need: 2 more stick
[DEBUG] Matched dependency string: 2 more stick
[DEBUG] Extracted dependency: stick
[DEBUG] Event type: onError
[DEBUG] Error event: In your program code: throw new Error(`Missing ingredients for ${itemName}`);
Missing ingredients for wooden_pickaxe
at line 1:await craftItem(bot, 'wooden_pickaxe', 1); in your code
[DEBUG] Event type: observe
[DEBUG] Final dependencies list: ['stick']
Missing dependencies for wooden_pickaxe: ['stick']
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
    // The function crafts a stick by calling a helper function to craft an item named 'stick' once.
}
✓ Registered skill: craftStick
[LOOP] Retrying craft for wooden_pickaxe (attempt 2/5)...
[DEBUG] Checking execution success for 2 events
[DEBUG] Checking event type: onChat
[DEBUG] Chat message for success check: [craft:done] crafted 1 wooden_pickaxe
[DEBUG] Chat indicates success, returning True
✓ Craft succeeded for wooden_pickaxe
Synthesized skill craftWoodenPickaxe:
async function craftWoodenPickaxe(bot) {
  await craftStick(bot);
  await craftItem(bot, 'wooden_pickaxe', 1);
}
Skill Manager generated description for craftWoodenPickaxe:
async function craftWoodenPickaxe(bot) {
    // The function crafts a wooden pickaxe by first crafting a stick and then crafting the wooden pickaxe item.
}
✓ Registered skill: craftWoodenPickaxe
[DEBUG] Executor returned success=True, events count=0
[DEBUG] Getting fresh state after task (soft refresh, no restart)
[DEBUG] Inventory after task: {'stick': 2, 'oak_planks': 3, 'wooden_pickaxe': 1, 'crafting_table': 1}
[DEBUG] Skipping primitive skill: craftWoodenPickaxe
Completed task Craft a wooden pickaxe.
Completed tasks: Obtain a wood log, Craft a wooden pickaxe
Failed tasks: Craft 4 wooden planks
****Curriculum Agent human message****
Nearby blocks: dirt, grass_block, grass, cornflower, water, tall_grass, oxeye_daisy, dandelion, pumpkin, azure_bluet, crafting_table

Position: x=-164.5, y=64.0, z=-566.5

Equipment: [None, None, None, None, 'crafting_table', None]

Inventory (4/36): {'stick': 2, 'oak_planks': 3, 'wooden_pickaxe': 1, 'crafting_table': 1}

Chests: None

Completed tasks so far: Obtain a wood log, Craft a wooden pickaxe

Failed tasks that are too hard: Craft 4 wooden planks


****Curriculum Agent ai message****
Reasoning: You have a wooden pickaxe and some sticks in your inventory. You can use these to craft a better tool, such as a stone pickaxe, which will allow you to mine faster and gather more diverse resources. However, you need cobblestone to craft a stone pickaxe. You can obtain cobblestone by mining stone blocks with your wooden pickaxe.
Task: Obtain 3 cobblestones.
Curriculum Agent Question: How to obtain 3 cobblestones in Minecraft?
Curriculum Agent Answer: To obtain 3 cobblestones in Minecraft, you can mine regular stone blocks with a pickaxe. When you mine a regular stone block, it will drop cobblestone. You can then collect the cobblestone to obtain 3 pieces.
Starting task Obtain 3 cobblestones for at most 4 times
Skill Manager retrieving for 4 skills
Failed to send telemetry event CollectionQueryEvent: capture() takes 1 positional argument but 3 were given
Skill Manager retrieved skills: obtainWoodLog, craftWoodenPickaxe, craftOakPlanks, craftStick
Render Action Agent system message with 4 skills
****Action Agent human message****
Code from the last round: No code in the first round

Execution error: No error

Chat log: None

Biome:

Time: midnight

Nearby blocks: dirt, grass_block, grass, cornflower, water, tall_grass, oxeye_daisy, dandelion, pumpkin, azure_bluet, crafting_table

Nearby entities (nearest to farthest): salmon, bat

Health: 20.0/20

Hunger: 20.0/20

Position: x=-164.5, y=64.0, z=-566.5

Equipment: [None, None, None, None, 'crafting_table', None]

Inventory (4/36): {'stick': 2, 'oak_planks': 3, 'wooden_pickaxe': 1, 'crafting_table': 1}

Chests: None

Task: Obtain 3 cobblestones

Context: Question: How to obtain 3 cobblestones in Minecraft?
Answer: To obtain 3 cobblestones in Minecraft, you can mine regular stone blocks with a pickaxe. When you mine a regular stone block, it will drop cobblestone. You can then collect the cobblestone to obtain 3 pieces.

Critique: None


****Action Agent ai message****
Explain: There is no execution error or chat log to explain as this is the first round.

Plan:
1) Use the `exploreUntil` function to find a stone block.
2) Use the `mineBlock` function to mine 3 cobblestones.

Code:
```javascript
async function obtainCobblestone(bot) {
  // Find a stone block
  const stone = await exploreUntil(bot, new Vec3(1, 0, 1), 60, () => {
    const stone = bot.findBlock({
      matching: mcData.blocksByName["stone"].id,
      maxDistance: 32
    });
    return stone;
  });

  // Mine the stone
  if (stone) {
    await mineBlock(bot, "stone", 3);
    bot.chat("Cobblestone obtained.");
  } else {
    bot.chat("No stone found.");
  }
}
```
****Recorder message: 2087 ticks have elapsed****
****Recorder message: 2 iteration passed****
Critic Agent: Error occurs Cannot read properties of undefined (reading 'emit')
Skill Manager retrieving for 4 skills
Skill Manager retrieved skills: obtainWoodLog, craftWoodenPickaxe, craftOakPlanks, craftStick