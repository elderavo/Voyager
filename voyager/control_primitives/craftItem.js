// ==========================
//  craftItem.js (final)
// ==========================
//
// - Handles crafting table detection (and placement if in inventory)
// - Uses Mineflayer recipesFor / recipesAll correctly
// - Emits Voyager-style dependency messages from recipe.delta
// - Designed to run inside index.js /step scope where mcData, placeItem, etc. exist
//

/**
 * Compute missing ingredients for a given recipe using recipe.delta.
 * Negative counts are consumed; positive are produced.
 */
function computeMissingIngredients(bot, recipe) {
    const missing = [];

    for (const deltaItem of recipe.delta) {
        if (deltaItem.count < 0) {
            const itemName = mcData.items[deltaItem.id].name;
            const invItem = bot.inventory.findInventoryItem(itemName, null);
            const have = invItem ? invItem.count : 0;
            const need = -deltaItem.count;
            if (have < need) {
                missing.push({
                    name: itemName,
                    needed: need - have,
                });
            }
        }
    }

    return missing;
}

/**
 * Pick the recipe that is "closest" to craftable:
 * the one with the smallest total missing ingredient count.
 */
function pickBestRecipe(bot, recipes) {
    if (!recipes || recipes.length === 0) return null;

    let best = null;
    let bestScore = Infinity;

    for (const r of recipes) {
        const missing = computeMissingIngredients(bot, r);
        const score = missing.reduce((acc, m) => acc + m.needed, 0);
        if (score < bestScore) {
            bestScore = score;
            best = r;
        }
    }

    return best;
}

/**
 * Emit Voyager-style dependency feedback:
 * "I cannot make <name> because I need: 3 more oak_planks, 2 more stick"
 */
function emitDependencyFeedback(bot, itemName, missingList) {
    if (!missingList || missingList.length === 0) return;

    const parts = missingList.map((m) => `${m.needed} more ${m.name}`);
    const msg = `I cannot make ${itemName} because I need: ${parts.join(", ")}`;
    bot.chat(msg);
}

/**
 * Find an existing crafting table near the bot, with retries to allow
 * world state to update after placement.
 */
async function findNearbyCraftingTable(bot, maxDistance = 32, attempts = 3, ticksBetween = 3) {
    const craftingTableId = mcData.blocksByName.crafting_table.id;
    
    for (let i = 0; i < attempts; i++) {
        const table = bot.findBlock({
            matching: craftingTableId,
            maxDistance,
        });
        if (table) return table;
        await bot.waitForTicks(ticksBetween);
    }
    return null;
}

/**
 * Ensure there is a crafting table block near the bot.
 * If none is found but the bot has a crafting_table item in inventory,
 * place one adjacent using placeItem, wait, then re-scan.
 *
 * If still none is found, throws "No crafting table nearby".
 */
async function ensureCraftingTable(bot, itemName) {
    // First, try to find an existing table
    let table = await findNearbyCraftingTable(bot, 32, 3, 3);

    if (table) {
        try {
            await bot.pathfinder.goto(new (require('mineflayer-pathfinder').goals.GoalNear)(table.position.x, table.position.y, table.position.z, 1));
            return table;
        } catch (err) {
            // If pathfinding times out, the table might be floating/unreachable - delete it and place a new one
            if (err.message && err.message.includes("Took to long to decide path to goal")) {
                bot.chat(`[CT:UNREACHABLE] Table at ${table.position} unreachable, removing...`);
                bot.chat(`/setblock ${table.position.x} ${table.position.y} ${table.position.z} air`);
                await bot.waitForTicks(3);
                // Fall through to placement logic below
                table = null;
            } else {
                throw err;
            }
        }
    }

    // No table found or table was removed; see if we can place one from inventory
    const ctItemDef = mcData.itemsByName["crafting_table"];
    if (!ctItemDef) {
        bot.chat(`craftItem: crafting_table item definition missing in mcData`);
        throw new Error("No crafting table nearby");
    }

    const invCt = bot.inventory.findInventoryItem(ctItemDef.id);
    if (!invCt) {
        // No crafting table block and no item to place one
        bot.chat(`craftItem: No crafting table nearby for '${itemName}'`);
        throw new Error("No crafting table nearby");
    }

    // We have a crafting_table item → place it beside the bot
    const placePos = bot.entity.position.offset(1, 0, 0).floored();
    bot.chat(`[CT] Placing crafting table at ${placePos}`);
    await placeItem(bot, "crafting_table", placePos);
    await bot.waitForTicks(5);

    // Re-scan for the table now that it should be placed
    table = await findNearbyCraftingTable(bot, 6, 3, 3);
    if (!table) {
        bot.chat(`[CT:FAIL] Could not locate crafting table after placement for '${itemName}'`);
        throw new Error("No crafting table nearby (after placement)");
    }

    bot.chat("[CT] Crafting table ready");
    return table;
}

/**
 * Main crafting primitive.
 *
 * - Validates item name and count
 * - Ensures a crafting table block is near the bot (placing one if necessary)
 * - Uses recipesFor to find actually craftable recipes
 * - Uses recipesAll + recipe.delta to compute missing dependencies
 * - Emits Voyager-style dependency chat and throws on failure
 */
async function craftItem(bot, itemName, count = 1) {
    // Argument checks
    if (typeof itemName !== "string") {
        throw new Error("name for craftItem must be a string");
    }
    if (typeof count !== "number") {
        throw new Error("count for craftItem must be a number");
    }

    const itemDef = mcData.itemsByName[itemName];
    if (!itemDef) {
        bot.chat(`craftItem: Unknown item '${itemName}'`);
        throw new Error(`No item named ${itemName}`);
    }
    const itemId = itemDef.id;

    // Ensure we have a crafting table block (or place one from inventory)
    const craftingTable = await ensureCraftingTable(bot, itemName);

    // First try: recipes that are actually craftable with current inventory
    let recipes = bot.recipesFor(itemId, null, count, craftingTable);

    if (recipes.length > 0) {
        const recipe = recipes[0];
        try {
            await bot.craft(recipe, count, craftingTable);
            bot.chat(`[craft:done] crafted ${count} ${itemName}`);
            return;
        } catch (err) {
            bot.chat(`[craft:fail] Could not craft ${itemName}: ${err.message}`);
            throw err;
        }
    }

    // No craftable recipe with current inventory.
    // Now ask for ALL recipes and compute which ingredients are missing.
    const allRecipes = bot.recipesAll(itemId, null, craftingTable);

    if (!allRecipes || allRecipes.length === 0) {
        // There truly is no crafting-table recipe for this item
        bot.chat(`craftItem: No crafting-table recipe for '${itemName}'`);
        throw new Error(`Recipe not found for ${itemName}`);
    }

    const bestRecipe = pickBestRecipe(bot, allRecipes);
    if (!bestRecipe) {
        bot.chat(`craftItem: No usable recipe candidate for '${itemName}'`);
        throw new Error(`Recipe not found for ${itemName}`);
    }

    const missing = computeMissingIngredients(bot, bestRecipe);

    if (missing.length > 0) {
        // Emit dependency line that Python parses into dependencies
        emitDependencyFeedback(bot, itemName, missing);
        throw new Error(`Missing ingredients for ${itemName}`);
    }

    // Edge case: recipesFor was empty but delta says we're not missing anything.
    // Try to craft anyway just in case Mineflayer had a minCount quirk.
    try {
        await bot.craft(bestRecipe, count, craftingTable);
        bot.chat(`[craft:done] crafted ${count} ${itemName}`);
    } catch (err) {
        bot.chat(`[craft:fail] Could not craft ${itemName}: ${err.message}`);
        throw err;
    }
}

// Optional CommonJS export for environments that require it.
module.exports = { craftItem };
