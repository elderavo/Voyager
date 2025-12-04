function getSourceBlocksForItem(itemName, mcData) {
    const targetItem = mcData.itemsByName[itemName];
    if (!targetItem) return [];

    const valid = [];
    for (const block of Object.values(mcData.blocks)) {
        if (block?.drops?.includes(targetItem.id)) {
            valid.push(block.name);
        }
    }

    return valid;   // e.g., ["stone"] for "cobblestone"
}

module.exports = { getSourceBlocksForItem };
