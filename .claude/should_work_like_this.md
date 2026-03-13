Flow should look like this:

### 1. Curriculum emits task

Something like:

```text
Craft 1 wooden pickaxe
```

Because you’re constraining curriculum, this is assumed to be a valid structured task.

### 2. Parser normalizes it

It gets turned into a goal like:

```text
HaveItem(wooden_pickaxe, 1)
```

Not “run craft JS,” not “ask action bot,” just a goal.

### 3. Skill store checked first

Before planning, ask:

```text
Do we already have a reusable non-stale skill for wooden_pickaxe?
```

If yes:

* executor runs that skill directly
* critic checks success
* done

If no:

* continue to resolver

### 4. Resolver asks MethodRegistry how to satisfy goal

For:

```text
HaveItem(wooden_pickaxe, 1)
```

registry says the main satisfying method is:

```text
craft
```

Then resolver asks that method for static prereqs.

That should come back roughly as:

```text
HaveItem(oak_planks, 3)
HaveItem(stick, 2)
WorkspaceAvailable(crafting_table)
```

### 5. Resolver recursively resolves each prereq

#### `HaveItem(oak_planks, 3)`

Craft method says:

* need `HaveItem(oak_log, 1)`

Then for `HaveItem(oak_log, 1)`:

* registry chooses gather/mine
* if logs are hand-minable, no tool prereq
* emit node: gather oak_log

#### `HaveItem(stick, 2)`

Craft method says:

* need `HaveItem(oak_planks, 2)`

Resolver sees planks are already part of the graph, so ideally it reuses that requirement rather than planning a second redundant branch.

#### `WorkspaceAvailable(crafting_table)`

Realizer/workspace logic says:

* if table already nearby, satisfied
* else if table in inventory, add place node
* else resolve `HaveItem(crafting_table, 1)` plus place node

For `HaveItem(crafting_table, 1)`:

* need `HaveItem(oak_planks, 4)`

So total wood requirement becomes something like:

* enough logs/planks for table, sticks, and pickaxe

### 6. Resolver outputs ordered plan

Something like:

1. gather oak_log(s)
2. craft oak_planks
3. craft crafting_table
4. place crafting_table
5. craft stick
6. craft wooden_pickaxe

Exact log count depends on how quantity aggregation is handled.

### 7. Executor runs nodes in order

Executor is dumb. It just runs each node’s method:

* `mineBlock(bot, 'oak_log', n)`
* `craftItem(bot, 'oak_planks', n)`
* `craftItem(bot, 'crafting_table', 1)`
* `placeItem(bot, 'crafting_table', ...)`
* `craftItem(bot, 'stick', 2)`
* `craftItem(bot, 'wooden_pickaxe', 1)`

After each step it updates observed state and checks result.

### 8. If something fails, repair loop kicks in

Example failures:

* no tree nearby
* no placeable crafting table location
* crafting helper reports missing planks
* pathing fails

If failure is structured and repairable, executor/resolver do bounded repair:

* add missing subgoal
* splice repaired nodes in
* retry

Example:

* craft step says missing `oak_planks`
* repair adds more log/plank gathering
* retry craft

### 9. If repair budget exceeded, full fallback to ActionAgent

After 3–4 failed repair cycles:

* abandon HTN path
* give original task **“Craft 1 wooden pickaxe”** plus context/failures to ActionAgent
* let it try end-to-end

That fallback is for world weirdness, not default execution.

### 10. Critic checks final outcome

Critic verifies:

```text
inventory has wooden_pickaxe >= 1
```

If yes:

* task succeeds
* curriculum progresses

### 11. Skill saving

If this was produced through structured execution and the plan is worth keeping, save useful multi-step skills like:

* `craftOakPlanks`
* `craftStick`
* `craftCraftingTable`
* `craftWoodenPickaxe`

Do not save trivial one-liners like “mine one oak log.”

The important idea is: **the task starts as a goal, gets decomposed into prerequisites, gets realized into executable nodes, gets repaired if needed, and only falls to ActionAgent if structured repair fails repeatedly.**
