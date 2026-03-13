const fs = require("fs");
const express = require("express");
const bodyParser = require("body-parser");
const mineflayer = require("mineflayer");
const { mineflayer: mineflayerViewer } = require("prismarine-viewer");

// ---------------------------------------------------------------------------
// Structured logger — stdout captured by Python SubprocessMonitor → mineflayer.log
// Format: ISO timestamp | LEVEL | [mineflayer] message
// ---------------------------------------------------------------------------
const log = {
    _write(level, msg, ...args) {
        const ts = new Date().toISOString();
        const extra = args.length
            ? " " + args.map(a => (typeof a === "object" ? JSON.stringify(a) : String(a))).join(" ")
            : "";
        process.stdout.write(`${ts} | ${level.padEnd(5)} | [mineflayer] ${msg}${extra}\n`);
    },
    debug: (msg, ...args) => log._write("DEBUG", msg, ...args),
    info:  (msg, ...args) => log._write("INFO",  msg, ...args),
    warn:  (msg, ...args) => log._write("WARN",  msg, ...args),
    error: (msg, ...args) => log._write("ERROR", msg, ...args),
};

const skills = require("./lib/skillLoader");
const { initCounter, getNextTime } = require("./lib/utils");
const obs = require("./lib/observation/base");
const OnChat = require("./lib/observation/onChat");
const OnError = require("./lib/observation/onError");
const { Voxels, BlockRecords } = require("./lib/observation/voxels");
const Status = require("./lib/observation/status");
const Inventory = require("./lib/observation/inventory");
const OnSave = require("./lib/observation/onSave");
const Chests = require("./lib/observation/chests");
const { plugin: tool } = require("mineflayer-tool");

let bot = null;

// Tracks the res object for any /start request that is still in-flight (i.e. the
// bot has been created but the spawn sequence hasn't finished yet and we haven't
// called res.json() on that request).  If a second /start arrives before the
// first one completes we use this to send an error reply to the stale request
// immediately so that the Python side doesn't hang for the full 120 s timeout.
let pendingStartRes = null;

// Prevent viewer/plugin errors from crashing the process between requests
process.on("uncaughtException", (err) => {
    log.error("Uncaught exception (non-fatal):", err.message || String(err));
});
process.on("unhandledRejection", (reason) => {
    log.error("Unhandled promise rejection (non-fatal):", reason instanceof Error ? reason.message : String(reason));
});

const app = express();

app.use(bodyParser.json({ limit: "50mb" }));
app.use(bodyParser.urlencoded({ limit: "50mb", extended: false }));

app.post("/start", (req, res) => {
    // If a previous /start is still in-flight (spawn sequence hasn't finished),
    // resolve it with an error immediately so the old Python request doesn't hang
    // for the full step_timeout before timing out.
    if (pendingStartRes) {
        log.warn("Second /start received while a previous /start is still in-flight — aborting the previous request");
        pendingStartRes.status(409).json({ error: "Superseded by a newer /start request" });
        pendingStartRes = null;
    }
    if (bot) onDisconnect("Restarting bot");
    bot = null;
    log.debug("POST /start", req.body);
    // Mark this request as pending until the spawn sequence sends its response.
    pendingStartRes = res;
    bot = mineflayer.createBot({
        host: req.body.host || "localhost", // minecraft server ip
        port: req.body.port, // minecraft server port
        username: req.body.username || "bot",
        auth: req.body.auth || "offline",
        disableChatSigning: true,
        checkTimeoutInterval: 60 * 60 * 1000,
    });
    bot.once("error", onConnectionFailed);

    // Event subscriptions
    bot.waitTicks = req.body.waitTicks;
    bot.globalTickCounter = 0;
    bot.stuckTickCounter = 0;
    bot.stuckPosList = [];
    bot.iron_pickaxe = false;

    bot.on("kicked", onDisconnect);

    // mounting will cause physicsTick to stop
    bot.on("mount", () => {
        bot.dismount();
    });

    bot.once("spawn", async () => {
        bot.removeListener("error", onConnectionFailed);
        let itemTicks = 1;
        if (req.body.reset === "hard") {
            // Suppress the kicked→onDisconnect handler during the kill/respawn
            // sequence so a brief death-screen disconnect doesn't tear the bot
            // down while we're waiting for respawn.
            bot.removeListener("kicked", onDisconnect);

            // Set keepInventory first so the kill doesn't drop items, then
            // wait a few ticks to let the server process the gamerule before
            // the kill fires.
            bot.chat("/gamerule keepInventory true");
            await bot.waitForTicks(5);
            bot.chat("/clear @s");
            bot.chat("/kill @s");

            // Wait for respawn with a hard timeout so a non-respawning server
            // doesn't block /start for the full 120 s step_timeout.
            await new Promise((resolve, reject) => {
                const timer = setTimeout(() => {
                    bot.removeListener("respawn", onRespawn);
                    reject(new Error("Bot did not respawn within 15 s after /kill @s"));
                }, 15000);
                function onRespawn() {
                    clearTimeout(timer);
                    resolve();
                }
                bot.once("respawn", onRespawn);
            });
            log.debug("Bot respawned after hard reset kill");

            // Re-register the kicked listener now that respawn is confirmed.
            bot.on("kicked", onDisconnect);

            const inventory = req.body.inventory ? req.body.inventory : {};
            const equipment = req.body.equipment
                ? req.body.equipment
                : [null, null, null, null, null, null];
            for (let key in inventory) {
                bot.chat(`/give @s minecraft:${key} ${inventory[key]}`);
                itemTicks += 1;
            }
            const equipmentNames = [
                "armor.head",
                "armor.chest",
                "armor.legs",
                "armor.feet",
                "weapon.mainhand",
                "weapon.offhand",
            ];
            for (let i = 0; i < 6; i++) {
                if (i === 4) continue;
                if (equipment[i]) {
                    bot.chat(
                        `/item replace entity @s ${equipmentNames[i]} with minecraft:${equipment[i]}`
                    );
                    itemTicks += 1;
                }
            }
        }

        if (req.body.position) {
            bot.chat(
                `/tp @s ${req.body.position.x} ${req.body.position.y} ${req.body.position.z}`
            );
        }

        // if iron_pickaxe is in bot's inventory
        if (
            bot.inventory.items().find((item) => item.name === "iron_pickaxe")
        ) {
            bot.iron_pickaxe = true;
        }

        const { pathfinder } = require("mineflayer-pathfinder");
        const tool = require("mineflayer-tool").plugin;
        const collectBlock = require("mineflayer-collectblock").plugin;
        const pvp = require("mineflayer-pvp").plugin;
        // minecrafthawkeye may not have a .plugin property, check if it's exported directly
        const minecraftHawkEyeModule = require("minecrafthawkeye");
        const minecraftHawkEye = minecraftHawkEyeModule.plugin || minecraftHawkEyeModule;

        bot.loadPlugin(pathfinder);
        bot.loadPlugin(tool);
        bot.loadPlugin(collectBlock);
        bot.loadPlugin(pvp);
        // Only load minecraftHawkEye if it's a valid function
        if (typeof minecraftHawkEye === 'function') {
            bot.loadPlugin(minecraftHawkEye);
        }

        // bot.collectBlock.movements.digCost = 0;
        // bot.collectBlock.movements.placeCost = 0;

        obs.inject(bot, [
            OnChat,
            OnError,
            Voxels,
            Status,
            Inventory,
            OnSave,
            Chests,
            BlockRecords,
        ]);
        skills.inject(bot);

        if (req.body.spread) {
            bot.chat(`/spreadplayers ~ ~ 0 300 under 80 false @s`);
            await bot.waitForTicks(bot.waitTicks);
        }

        await bot.waitForTicks(bot.waitTicks * itemTicks);
        // Spawn sequence complete — clear the pending tracker before sending the
        // response so that any concurrent /start that arrives after this point
        // doesn't try to abort an already-resolved request.
        pendingStartRes = null;
        res.json(bot.observe());

        initCounter(bot);
        bot.chat("/gamerule keepInventory true");
        bot.chat("/gamerule doDaylightCycle false");

        // Initialize prismarine-viewer so you can watch the bot in a browser
        // Access at http://localhost:3007 in your web browser
        try {
            bot.viewer = mineflayerViewer(bot, { port: 3007, firstPerson: true });
            log.info("Prismarine viewer started on http://localhost:3007");
        } catch (viewerErr) {
            log.warn("Prismarine viewer failed to start (port 3007 may still be in use):", viewerErr.message);
        }
    });

    function onConnectionFailed(e) {
        log.error("Bot connection failed:", e.message || String(e));
        bot = null;
        pendingStartRes = null;
        res.status(400).json({ error: e });
    }
    function onDisconnect(message) {
        if (bot.viewer) {
            bot.viewer.close();
        }
        bot.end();
        log.warn("Bot disconnected:", message);
        bot = null;
    }
});

app.post("/step", async (req, res) => {
    if (!bot) {
        return res.status(503).json({ error: "Bot not connected — call /start first" });
    }
    // import useful package
    let response_sent = false;
    function otherError(err) {
        log.error("Uncaught error in /step handler:", err.message || String(err));
        bot.emit("error", handleError(err));
        bot.waitForTicks(bot.waitTicks).then(() => {
            if (!response_sent) {
                response_sent = true;
                res.json(bot.observe());
            }
        });
    }

    process.on("uncaughtException", otherError);

    const mcData = require("minecraft-data")(bot.version);
    mcData.itemsByName["leather_cap"] = mcData.itemsByName["leather_helmet"];
    mcData.itemsByName["leather_tunic"] =
        mcData.itemsByName["leather_chestplate"];
    mcData.itemsByName["leather_pants"] =
        mcData.itemsByName["leather_leggings"];
    mcData.itemsByName["leather_boots"] = mcData.itemsByName["leather_boots"];
    mcData.itemsByName["lapis_lazuli_ore"] = mcData.itemsByName["lapis_ore"];
    mcData.blocksByName["lapis_lazuli_ore"] = mcData.blocksByName["lapis_ore"];
    const {
        Movements,
        goals: {
            Goal,
            GoalBlock,
            GoalNear,
            GoalXZ,
            GoalNearXZ,
            GoalY,
            GoalGetToBlock,
            GoalLookAtBlock,
            GoalBreakBlock,
            GoalCompositeAny,
            GoalCompositeAll,
            GoalInvert,
            GoalFollow,
            GoalPlaceBlock,
        },
        pathfinder,
        Move,
        ComputedPath,
        PartiallyComputedPath,
        XZCoordinates,
        XYZCoordinates,
        SafeBlock,
        GoalPlaceBlockOptions,
    } = require("mineflayer-pathfinder");
    const { Vec3 } = require("vec3");

    // Set up pathfinder
    const movements = new Movements(bot, mcData);
    bot.pathfinder.setMovements(movements);

    bot.globalTickCounter = 0;
    bot.stuckTickCounter = 0;
    bot.stuckPosList = [];

    function onTick() {
        bot.globalTickCounter++;
        if (bot.pathfinder && bot.pathfinder.isMoving()) {
            bot.stuckTickCounter++;
            if (bot.stuckTickCounter >= 100) {
                onStuck(1.5);
                bot.stuckTickCounter = 0;
            }
        }
    }

    bot.on("physicsTick", onTick);

    // initialize fail count
    let _craftItemFailCount = 0;
    let _killMobFailCount = 0;
    let _mineBlockFailCount = 0;
    let _placeItemFailCount = 0;
    let _smeltItemFailCount = 0;

    // Retrieve array form post bod
    const code = req.body.code;
    const programs = req.body.programs;
    bot.cumulativeObs = [];
    await bot.waitForTicks(bot.waitTicks);
    const r = await evaluateCode(code, programs);
    process.off("uncaughtException", otherError);
    if (r !== "success") {
        bot.emit("error", handleError(r));
    }
    await returnItems();
    // wait for last message
    await bot.waitForTicks(bot.waitTicks);
    if (!response_sent) {
        response_sent = true;
        res.json(bot.observe());
    }
    bot.removeListener("physicsTick", onTick);

    async function evaluateCode(code, programs) {
        // Echo the code produced for players to see it. Don't echo when the bot code is already producing dialog or it will double echo
        try {
            await eval("(async () => {" + programs + "\n" + code + "})()");
            return "success";
        } catch (err) {
            return err;
        }
    }

    function onStuck(posThreshold) {
        const currentPos = bot.entity.position;
        bot.stuckPosList.push(currentPos);

        // Check if the list is full
        if (bot.stuckPosList.length === 5) {
            const oldestPos = bot.stuckPosList[0];
            const posDifference = currentPos.distanceTo(oldestPos);

            if (posDifference < posThreshold) {
                teleportBot(); // execute the function
            }

            // Remove the oldest time from the list
            bot.stuckPosList.shift();
        }
    }

    function teleportBot() {
        const blocks = bot.findBlocks({
            matching: (block) => {
                return block.type === 0;
            },
            maxDistance: 1,
            count: 27,
        });

        if (blocks) {
            // console.log(blocks.length);
            const randomIndex = Math.floor(Math.random() * blocks.length);
            const block = blocks[randomIndex];
            bot.chat(`/tp @s ${block.x} ${block.y} ${block.z}`);
        } else {
            bot.chat("/tp @s ~ ~1.25 ~");
        }
    }

    function returnItems() {
        bot.chat("/gamerule doTileDrops false");
        const crafting_table = bot.findBlock({
            matching: mcData.blocksByName.crafting_table.id,
            maxDistance: 128,
        });
        if (crafting_table) {
            bot.chat(
                `/setblock ${crafting_table.position.x} ${crafting_table.position.y} ${crafting_table.position.z} air destroy`
            );
            bot.chat("/give @s crafting_table");
        }
        const furnace = bot.findBlock({
            matching: mcData.blocksByName.furnace.id,
            maxDistance: 128,
        });
        if (furnace) {
            bot.chat(
                `/setblock ${furnace.position.x} ${furnace.position.y} ${furnace.position.z} air destroy`
            );
            bot.chat("/give @s furnace");
        }
        if (bot.inventoryUsed() >= 32) {
            // if chest is not in bot's inventory
            if (!bot.inventory.items().find((item) => item.name === "chest")) {
                bot.chat("/give @s chest");
            }
        }
        // if iron_pickaxe not in bot's inventory and bot.iron_pickaxe
        if (
            bot.iron_pickaxe &&
            !bot.inventory.items().find((item) => item.name === "iron_pickaxe")
        ) {
            bot.chat("/give @s iron_pickaxe");
        }
        bot.chat("/gamerule doTileDrops true");
    }

    function handleError(err) {
        let stack = err.stack;
        if (!stack) {
            return err;
        }
        log.error("Execution error stack:", stack);
        const final_line = stack.split("\n")[1];
        const regex = /<anonymous>:(\d+):\d+\)/;

        const programs_length = programs.split("\n").length;
        let match_line = null;
        for (const line of stack.split("\n")) {
            const match = regex.exec(line);
            if (match) {
                const line_num = parseInt(match[1]);
                if (line_num >= programs_length) {
                    match_line = line_num - programs_length;
                    break;
                }
            }
        }
        if (!match_line) {
            return err.message;
        }
        let f_line = final_line.match(
            /\((?<file>.*):(?<line>\d+):(?<pos>\d+)\)/
        );
        if (f_line && f_line.groups && fs.existsSync(f_line.groups.file)) {
            const { file, line, pos } = f_line.groups;
            const f = fs.readFileSync(file, "utf8").split("\n");
            // let filename = file.match(/(?<=node_modules\\)(.*)/)[1];
            let source = file + `:${line}\n${f[line - 1].trim()}\n `;

            const code_source =
                "at " +
                code.split("\n")[match_line - 1].trim() +
                " in your code";
            return source + err.message + "\n" + code_source;
        } else if (
            f_line &&
            f_line.groups &&
            f_line.groups.file.includes("<anonymous>")
        ) {
            const { file, line, pos } = f_line.groups;
            let source =
                "Your code" +
                `:${match_line}\n${code.split("\n")[match_line - 1].trim()}\n `;
            let code_source = "";
            if (line < programs_length) {
                source =
                    "In your program code: " +
                    programs.split("\n")[line - 1].trim() +
                    "\n";
                code_source = `at line ${match_line}:${code
                    .split("\n")
                    [match_line - 1].trim()} in your code`;
            }
            return source + err.message + "\n" + code_source;
        }
        return err.message;
    }
});

app.post("/reset", async (req, res) => {
    // Soft reset: bot stays connected, just reset counters and optionally teleport.
    // Does NOT create a new bot connection. Used between tasks to avoid disconnect churn.
    if (!bot) {
        res.status(400).json({ error: "Bot not spawned" });
        return;
    }
    log.debug("POST /reset (soft)", req.body);
    try {
        bot.globalTickCounter = 0;
        bot.stuckTickCounter = 0;
        bot.stuckPosList = [];

        if (req.body.position) {
            bot.chat(`/tp @s ${req.body.position.x} ${req.body.position.y} ${req.body.position.z}`);
        }

        if (req.body.waitTicks) {
            await bot.waitForTicks(req.body.waitTicks);
        }

        res.json(bot.observe());
    } catch (err) {
        log.error("Error during soft /reset:", err.message || String(err));
        res.status(500).json({ error: err.message || String(err) });
    }
});

app.post("/stop", (req, res) => {
    bot.end();
    res.json({
        message: "Bot stopped",
    });
});

app.post("/pause", (req, res) => {
    if (!bot) {
        res.status(400).json({ error: "Bot not spawned" });
        return;
    }
    bot.chat("/pause");
    bot.waitForTicks(bot.waitTicks).then(() => {
        res.json({ message: "Success" });
    });
});

app.post("/registry", (req, res) => {
    if (!bot) {
        res.status(400).json({ error: "Bot not spawned" });
        return;
    }

    const mcData = require("minecraft-data")(bot.version);
    const type = req.body.type; // 'items', 'blocks', or 'recipes'
    const name = req.body.name; // optional: specific item/block name

    try {
        if (name) {
            // Return specific item/block
            if (type === "items") {
                const item = mcData.itemsByName[name];
                res.json(item || null);
            } else if (type === "blocks") {
                const block = mcData.blocksByName[name];
                res.json(block || null);
            } else if (type === "recipes") {
                const item = mcData.itemsByName[name];
                log.debug(`Registry recipe lookup: "${name}"`);
                log.debug(`Registry item in mcData:`, item ? `ID=${item.id}, name=${item.name}` : "null");
                if (!bot.recipesFor) {
                    log.error("bot.recipesFor is NOT available");
                }

                if (item) {
                    // Try to find crafting table in bot's inventory or nearby
                    const craftingTable = bot.findBlock({
                        matching: mcData.blocksByName.crafting_table?.id,
                        maxDistance: 32
                    });
                    log.debug(`Registry crafting table available:`, craftingTable ? "yes" : "no");

                    // Try without crafting table first (for 2x2 recipes)
                    let recipes = null;
                    try {
                        recipes = bot.recipesFor(item.id, null, 1, null);
                        log.debug(`Registry recipesFor (no table):`, recipes ? `${recipes.length} recipes` : "null");
                    } catch (err) {
                        log.error(`Registry error calling bot.recipesFor:`, err.message);
                    }

                    // If no recipes found and crafting table exists, try with crafting table
                    if ((!recipes || recipes.length === 0) && craftingTable) {
                        recipes = bot.recipesFor(item.id, null, 1, craftingTable);
                        log.debug(`Registry recipesFor (with table):`, recipes ? `${recipes.length} recipes` : "null");
                    }

                    if (recipes && recipes.length > 0) {
                        log.debug(`Registry first recipe:`, JSON.stringify(recipes[0]));
                    }
                    // Enhance recipes with ingredient names
                    if (recipes && recipes.length > 0) {
                        const enhancedRecipes = recipes.map(recipe => {
                            const ingredientNames = [];
                            if (recipe.delta) {
                                // Shaped/shapeless recipe with delta
                                recipe.delta.forEach(item => {
                                    if (item.count < 0) {  // Negative count means consumed ingredient
                                        const itemId = Math.abs(item.id);
                                        const itemData = mcData.items[itemId];
                                        if (itemData && itemData.name) {
                                            ingredientNames.push(itemData.name);
                                        }
                                    }
                                });
                            } else if (recipe.ingredients) {
                                // Direct ingredients list
                                recipe.ingredients.forEach(ingredient => {
                                    const itemData = mcData.items[ingredient.id];
                                    if (itemData && itemData.name) {
                                        ingredientNames.push(itemData.name);
                                    }
                                });
                            }
                            return {
                                ...recipe,
                                ingredientNames: ingredientNames
                            };
                        });
                        res.json(enhancedRecipes);
                    } else {
                        res.json(recipes || null);
                    }
                } else {
                    res.json(null);
                }
            } else {
                res.status(400).json({ error: "Invalid type. Must be 'items', 'blocks', or 'recipes'" });
            }
        } else {
            // Return all item/block names
            if (type === "items") {
                res.json(Object.keys(mcData.itemsByName));
            } else if (type === "blocks") {
                res.json(Object.keys(mcData.blocksByName));
            } else if (type === "recipes") {
                res.status(400).json({ error: "Name required for recipes" });
            } else {
                res.status(400).json({ error: "Invalid type. Must be 'items', 'blocks', or 'recipes'" });
            }
        }
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Server listening to PORT 3000

const DEFAULT_PORT = 3000;
const PORT = process.argv[2] || DEFAULT_PORT;
app.listen(PORT, () => {
    log.info(`Server started on port ${PORT}`);
});
