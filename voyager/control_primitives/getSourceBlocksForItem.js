function getSourceBlocksForItem(itemName, mcData) {
    console.log(`[getSourceBlocksForItem] Looking up source blocks for item: '${itemName}'`);

    const targetItem = mcData.itemsByName[itemName];
    if (!targetItem) {
        console.log(`[getSourceBlocksForItem] Item '${itemName}' not found in mcData.itemsByName`);
        return [];
    }

    console.log(`[getSourceBlocksForItem] Found item '${itemName}' with ID: ${targetItem.id}`);

    const valid = [];
    for (const block of Object.values(mcData.blocks)) {
        if (block?.drops?.includes(targetItem.id)) {
            valid.push(block.name);
        }
    }

    console.log(`[getSourceBlocksForItem] Found ${valid.length} source blocks for '${itemName}': [${valid.join(', ')}]`);
    return valid;   // e.g., ["stone"] for "cobblestone"
}

module.exports = { getSourceBlocksForItem };
