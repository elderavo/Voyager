// Returns the first safe Vec3 position adjacent to the bot where a block can
// be placed: the target cell must be air and the cell below it must be solid.
// Falls back to offset(1,0,0) if nothing clean is found.
function findSafePlacementPos(bot) {
    const base = bot.entity.position.floored();
    const offsets = [
        new Vec3(1, 0, 0),
        new Vec3(-1, 0, 0),
        new Vec3(0, 0, 1),
        new Vec3(0, 0, -1),
    ];
    for (const off of offsets) {
        const pos = base.plus(off);
        const atPos = bot.blockAt(pos);
        const below = bot.blockAt(pos.offset(0, -1, 0));
        if (atPos && atPos.name === "air" && below && below.name !== "air") {
            return pos;
        }
    }
    return base.offset(1, 0, 0); // fallback
}

// Scan for a placed crafting table, retrying a few times to allow the
// server's block-update to propagate back to mineflayer's world state.
// On a LAN server one round-trip is ~10-50 ms; 2 ticks (100 ms) is not
// reliably enough, so we poll up to `attempts` times.
async function findNearbyCraftingTable(bot, maxDistance = 32, attempts = 3, ticksBetween = 3) {
    const craftingTableId = mcData.blocksByName.crafting_table.id;
    for (let i = 0; i < attempts; i++) {
        const table = bot.findBlock({ matching: craftingTableId, maxDistance });
        if (table) return table;
        await bot.waitForTicks(ticksBetween);
    }
    return null;
}

// Ensures a crafting table is placed in the world and the bot is adjacent
// to it.  Returns the crafting-table block on success, null on failure.
//
// Resolution order:
//   1. Already in the world nearby  → navigate close, return it
//   2. In inventory                 → place, wait, retry-scan, navigate
//   3. Neither                      → craft one from planks (2x2, no table
//                                     required), then place and navigate
async function ensureCraftingTable(bot) {
    // 1. Already placed nearby?
    let table = await findNearbyCraftingTable(bot, 32, 1, 0);
    if (table) {
        await bot.pathfinder.goto(
            new GoalNear(table.position.x, table.position.y, table.position.z, 1)
        );
        return table;
    }

    // 2. In inventory?
    if (!bot.inventory.findInventoryItem(mcData.itemsByName.crafting_table.id)) {
        // 3. Try to craft one from planks using the 2x2 grid (no table needed)
        const tableRecipe = bot.recipesFor(
            mcData.itemsByName.crafting_table.id,
            null,
            1,
            null  // explicitly no crafting table — must be a 2x2 recipe
        )[0];

        if (!tableRecipe) {
            bot.chat("Need a crafting table but have no recipe (need planks)");
            return null;
        }

        // Verify we actually have the ingredients before attempting
        const canCraft = tableRecipe.delta.every((d) => {
            if (d.count >= 0) return true; // output slot, not an input
            const inv = bot.inventory.findInventoryItem(
                mcData.items[d.id].name,
                null
            );
            return inv && inv.count >= -d.count;
        });

        if (!canCraft) {
            bot.chat("Need a crafting table but don't have enough planks to craft one");
            return null;
        }

        await bot.craft(tableRecipe, 1, null);
        bot.chat("Crafted a crafting table");
    }

    // 4. Place it at a safe nearby position
    const pos = findSafePlacementPos(bot);
    await placeItem(bot, "crafting_table", pos);

    // Wait longer than the minimum — LAN round-trip means the block update
    // arrives later than on localhost.  Then retry the scan several times
    // before giving up, mirroring what the proven action_branch does.
    await bot.waitForTicks(5);
    table = await findNearbyCraftingTable(bot, 6, 3, 3);

    if (!table) {
        bot.chat("Failed to locate crafting table after placement");
        return null;
    }

    await bot.pathfinder.goto(
        new GoalNear(table.position.x, table.position.y, table.position.z, 1)
    );
    return table;
}

async function craftItem(bot, name, count = 1) {
    if (typeof name !== "string") {
        throw new Error("name for craftItem must be a string");
    }
    if (typeof count !== "number") {
        throw new Error("count for craftItem must be a number");
    }
    const itemByName = mcData.itemsByName[name];
    if (!itemByName) {
        throw new Error(`No item named ${name}`);
    }

    // Prefer a 2x2 recipe (no table required) when one exists.
    // This handles planks, sticks, crafting_table itself, etc.
    const recipesNoTable = bot.recipesFor(itemByName.id, null, 1, null);
    if (recipesNoTable.length > 0) {
        bot.chat(`Crafting ${name} x${count} (2x2 grid)`);
        try {
            await bot.craft(recipesNoTable[0], count, null);
            bot.chat(`Crafted ${name} x${count}`);
            return;
        } catch (err) {
            bot.chat(`2x2 craft failed for ${name}: ${err.message}`);
        }
    }

    // Recipe requires a crafting table — obtain one and navigate to it.
    const craftingTable = await ensureCraftingTable(bot);
    if (!craftingTable) {
        throw new Error(
            `craftItem: need a crafting table for ${name} but could not obtain one`
        );
    }

    const recipe = bot.recipesFor(itemByName.id, null, 1, craftingTable)[0];
    if (!recipe) {
        failedCraftFeedback(bot, name, itemByName, craftingTable);
        _craftItemFailCount++;
        if (_craftItemFailCount > 10) {
            throw new Error(
                "craftItem failed too many times, check chat log to see what happened"
            );
        }
        return;
    }

    bot.chat(`Crafting ${name} x${count} (3x3 table)`);
    try {
        await bot.craft(recipe, count, craftingTable);
        bot.chat(`Crafted ${name} x${count}`);
    } catch (err) {
        bot.chat(`Failed to craft ${name}: ${err.message}`);
    }
}
