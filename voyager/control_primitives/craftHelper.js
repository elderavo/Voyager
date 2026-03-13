function failedCraftFeedback(bot, name, item, craftingTable) {
    const recipes = bot.recipesAll(item.id, null, craftingTable);
    if (!recipes.length) {
        // No recipe exists at all for this item with the given table context
        throw new Error(
            `No recipe found for ${name} — ensure you have the required materials and a crafting table`
        );
    }
    // Find the recipe with the fewest missing ingredients so the feedback
    // message is as specific as possible.  Reuse the recipes already fetched
    // above rather than calling recipesAll again (the original second call
    // incorrectly passed a block-ID integer instead of a block object).
    let min = 999;
    let min_recipe = null;
    for (const recipe of recipes) {
        const delta = recipe.delta;
        let missing = 0;
        for (const delta_item of delta) {
            if (delta_item.count < 0) {
                const inventory_item = bot.inventory.findInventoryItem(
                    mcData.items[delta_item.id].name,
                    null
                );
                if (!inventory_item) {
                    missing += -delta_item.count;
                } else {
                    missing += Math.max(
                        -delta_item.count - inventory_item.count,
                        0
                    );
                }
            }
        }
        if (missing < min) {
            min = missing;
            min_recipe = recipe;
        }
    }
    const delta = min_recipe.delta;
    let message = "";
    for (const delta_item of delta) {
        if (delta_item.count < 0) {
            const inventory_item = bot.inventory.findInventoryItem(
                mcData.items[delta_item.id].name,
                null
            );
            if (!inventory_item) {
                message += ` ${-delta_item.count} more ${
                    mcData.items[delta_item.id].name
                }, `;
            } else if (inventory_item.count < -delta_item.count) {
                message += `${
                    -delta_item.count - inventory_item.count
                } more ${mcData.items[delta_item.id].name}, `;
            }
        }
    }
    bot.chat(`I cannot make ${name} because I need: ${message}`);
}
