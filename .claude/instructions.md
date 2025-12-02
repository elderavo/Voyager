✅ PATCH INSTRUCTIONS (EXPLICIT, STEP-BY-STEP)

Your goal:
Stop mining primitives from returning “success by default,” and correctly detect when a block requires a tool.

You must patch three locations:

PATCH 1 — Add explicit “tool required” detection in mineBlock.js
File: minecraft/action_primitives/mineBlock.js (or your equivalent)
Before your actual digging code, insert this block:
// --- TOOL REQUIREMENT CHECK ---
const mcData = require('minecraft-data')(bot.version);
const targetName = itemName; // you likely have this variable already

const blockToMine = bot.findBlock({
    matching: mcData.blocksByName[targetName]?.id,
    maxDistance: 6
});

if (!blockToMine) {
    bot.chat(`no_block_found:${targetName}`);
    return;
}

if (!bot.canDigBlock(blockToMine)) {
    bot.chat(`need_tool:${targetName}`);
    return;
}
// --- END TOOL CHECK ---

Why this matters

bot.canDigBlock(block) already knows all hardness, tool tier, material rules.

This fires BEFORE digging.

It emits a clear machine-readable message your Python executor can detect.

DO NOT try to dig the block if this returns early.
PATCH 2 — Teach Python executor to detect tool failures explicitly
File: executor_utils.py (or wherever you classify success/failure)

Modify your event parser so that:

Add detection:
if "need_tool:" in chat_message:
    return False, {"failure_type": "TOOL_REQUIRED"}

Also add:
if "no_block_found:" in chat_message:
    return False, {"failure_type": "NO_BLOCK_NEARBY"}

Critically: REMOVE the fallback “defaulting to True.”

Your current behavior:

# [BAD] if nothing matched → return True


Replace with:

# If no success keywords AND no inventory increase, treat as failure
return False

PATCH 3 — Replace default success with inventory delta success detection
File: executor_skills.py — inside your primitive mining success check

Replace the entire “no explicit success/failure → default to True” region with the following logic:

# BEFORE executing mineBlock: snapshot inventory
inv_before = self.env.get_inventory_counts()

# AFTER execution: determine outcome
inv_after = self.env.get_inventory_counts()
delta = inv_after.get(target_item, 0) - inv_before.get(target_item, 0)

# SUCCESS = inventory increased
if delta > 0:
    return True, events

# FAILURE = no delta + no explicit success message
return False, {"failure_type": "NO_YIELD"}


This is the ground truth used in MineRL, Voyager, and decision-transformer-style agents.

PATCH 4 — Emit needed-tool dependency for HTN
Where: In executor’s missing-dependency extraction logic

Add:

if failure_type == "TOOL_REQUIRED":
    missing.append(f"tool_for_{item}")   # or just append the item itself


This tells the HTN:

"To mine cobblestone, you need 'wooden_pickaxe'"


You can map required tools by mcData:

required_tool = mcdata.blocks[block_id].harvestTools

PATCH 5 — Fix stone/dripstone item normalization
File: item normalization utility

Before falling back to fuzzy match, insert:

if token.startswith("stone"):
    return "stone"


Then remove fuzzy matching against block names entirely.

This prevents:

stone_block → dripstone_block


which caused the nonsense request for “mine dripstone_block nearby.”