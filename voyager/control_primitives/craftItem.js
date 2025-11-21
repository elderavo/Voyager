// ==========================
//  craftItem.js (rewritten)
// ==========================
//
// This version strictly follows the Mineflayer API defined in api.md
// and properly distinguishes between 2x2 and 3x3 (crafting table) recipes.
// It avoids all the mis-detection issues and ghost crafting behavior
// caused by using incorrect recipeFor signatures or incorrect craftingTable
// block resolution.
//

const Item = require('prismarine-item');

/**
 * Craft an item using the correct 2x2 or 3x3 recipe logic.
 *
 * @param {Bot} bot - Mineflayer bot instance
 * @param {string} itemName - mcData item name (e.g., "oak_planks")
 * @param {number} count - number of items to craft
 */
async function craftItem(bot, itemName, count = 1) {
  const mcData = bot.registry;

  // --- Lookup item ---
  const itemByName = mcData.itemsByName[itemName];
  if (!itemByName) {
    bot.chat(`craftItem: Unknown item '${itemName}'`);
    throw new Error(`Unknown item: ${itemName}`);
  }

  const itemId = itemByName.id;

  // ====================================================================
  // 1. Try 2x2 inventory recipes first (craftingTable = null).
  //    Mineflayer semantics:
  //
  //      bot.recipesFor(itemType, metadata=null, minCount, craftingTable=null)
  //
  //    → Searches ONLY inventory (2×2) crafts.
  //
  // ====================================================================

  let recipes = bot.recipesFor(itemId, null, count, null);

  if (recipes.length > 0) {
    // Found an inventory recipe.
    try {
      await bot.craft(recipes[0], count, null);
      bot.chat(`crafted ${count} ${itemName} (2x2)`);
      return;
    } catch (err) {
      bot.chat(`craftItem: 2x2 craft failed for ${itemName}: ${err.message}`);
      throw err;
    }
  }

  // ====================================================================
  // 2. No 2x2 recipes found → Look for a nearby crafting table block.
  // ====================================================================

  const craftingTableId = mcData.blocksByName.crafting_table.id;

  // Find a table within 4 blocks of the bot.
  let craftingTable = bot.findBlock({
    matching: craftingTableId,
    maxDistance: 4
  });

  // If not found, fail meaningfully. The caller (executor) should decide
  // whether to place a table, craft one, or handle missing dependency.
  if (!craftingTable) {
    bot.chat(`craftItem: No crafting table nearby for '${itemName}'`);
    throw new Error("No crafting table nearby");
  }

  // ====================================================================
  // 3. Try crafting table (3×3) recipes.
  // ====================================================================

  recipes = bot.recipesFor(itemId, null, count, craftingTable);

  if (recipes.length === 0) {
    bot.chat(`craftItem: No crafting-table recipe for '${itemName}'`);
    throw new Error(`Recipe not found for ${itemName}`);
  }

  try {
    await bot.craft(recipes[0], count, craftingTable);
    bot.chat(`crafted ${count} ${itemName} (3x3)`);
    return;
  } catch (err) {
    bot.chat(`craftItem: 3x3 craft failed for ${itemName}: ${err.message}`);
    throw err;
  }
}

module.exports = { craftItem };
