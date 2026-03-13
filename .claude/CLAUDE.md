Here’s the **minimal clean architecture** I’d use, in the context of original Voyager.

It keeps the spirit of Voyager:

* curriculum proposes task
* system decides whether task is structured or open-ended
* structured tasks go through HTN/production planning
* weird tasks fall back to ActionAgent
* critic evaluates outcome
* successful reusable behaviors become skills

But it cuts the runtime down to a small set of concepts.

---

# Original Voyager, conceptually

Original Voyager is basically:

1. **Curriculum Agent**
   proposes next task

2. **Action Agent**
   writes JS code for the task

3. **Environment / Executor**
   runs code

4. **Critic**
   checks if task succeeded

5. **Skill Manager**
   stores useful code snippets

That works, but its weakness is this:

* every task is treated like an open-ended coding problem
* even simple production tasks like crafting a pickaxe get routed through LLM code generation
* missing dependencies are discovered late and awkwardly

So your upgrade is really about **splitting the world into two execution paths**.

---

# The clean upgraded Voyager workflow

## Path A: structured production tasks

For things like:

* craft
* smelt
* mine/gather
* kill
* maybe trade later

These should **not** go straight to ActionAgent.

They should go:

```text
Curriculum
  -> Task Classifier
  -> Production Planner
  -> Executor
  -> Critic
  -> Skill Saver
```

## 1. `Task Parser`

You still need a tiny component that does:

parse "Craft 1 iron pickaxe" into HaveItem("iron_pickaxe",1)

reject malformed or unsupported tasks

maybe normalize item names and quantities

## 2. `Goal`

This is the planning currency.

Two main kinds:

* `HaveItem(item, qty)`
* `WorldStateGoal(...)`

In your near-term system, structured production can mostly use:

* `HaveItem(...)`
* `WorkspaceAvailable(...)`
* `CanHarvest(...)`
* `FuelAvailable(...)`
* `EntityAccessible(...)`

So the planner reasons in **goals/predicates**, not code.

---

## 3. `Resolver`

This is the HTN-ish planner.

Input:

* target goal
* current inventory/world snapshot

Output:

* ordered list of `PlanNode`s

Its job is only:

* check whether goal is already satisfied
* choose a method that can satisfy it
* recursively resolve prerequisites
* produce an execution order

It should **not** emit JS.

It should **not** call Mineflayer.

It should just produce a plan.

Example:

```text
HaveItem(iron_pickaxe,1)
  -> HaveItem(iron_ingot,3)
  -> HaveItem(stick,2)
  -> WorkspaceAvailable(crafting_table)
```

---

## 4. `MethodRegistry`

This maps goals to methods.

Examples:

* `HaveItem(oak_log)` → `MiningMethod`
* `HaveItem(stick)` → `CraftingMethod`
* `HaveItem(iron_ingot)` → `SmeltingMethod`
* `HaveItem(leather)` → `KillingMethod` or later `TradingMethod`

The registry decides **what kind of operation** satisfies a goal.

This replaces a lot of ad hoc logic.

---

## 5. `Executor`

Input: ordered `PlanNode`s
Output:

* success/failure
* events
* structured failure info

Executor is the only layer that:

* calls Mineflayer JS helpers
* updates world/inventory state
* sees actual runtime failures

This is where:

* `craftItem`
* `mineBlock`
* `smeltItem`
* `killMob`
* `placeItem`

actually happen.

And this is where runtime failure feedback is generated, like:

* `MissingWorkspace(crafting_table)`
* `MissingTool(CanHarvest(iron_ore))`
* `MissingResource(HaveItem(coal,1))`

---

## 6. `SkillStore`

This is the upgraded SkillManager/SkillGraph.

Responsibilities:

* store reusable learned skills
* retrieve skill by output/effect
* mark stale if dependencies change
* avoid saving junk one-liners

This unifies two skill sources:

1. **production-derived skills**

   * `craftOakPlanks`
   * `craftStick`
   * `craftWoodenPickaxe`

2. **ActionAgent-generated skills**

   * custom open-ended behavior code

So one store, two origins.

---

# The actual end-to-end Voyager workflow

Here is the full pipeline.
Curriculum proposes structured task
    ↓
TaskParser/Validator
    ↓
existing skill?
    ├─ yes → execute
    └─ no  → resolve plan
                ↓
             execute
                ↓
      repairable failure?
        ├─ yes, under limit → repair + retry
        └─ no / over limit  → ActionAgent gets original task
                ↓
              critic
                ↓
            maybe save skill

New Voyager can **repair structured plans structurally**.

---

## Step 7: Fallback to ActionAgent when structure breaks

You still need the ActionAgent.

Use it like this:
On execution failure, attempt repair

- re-resolve missing predicates

- splice new subplan

- retry

- Track repair count

After 3–4 failed repair cycles, abandon structured execution and hand the entire original task to ActionAgent

Not just the failed node, The whole task.

---

## Step 8: Critic evaluates outcome

Regardless of whether the task came from production planning or ActionAgent, Critic checks:

* was the requested task satisfied?
* did inventory/world actually change correctly?
* was the result partial?

This part should stay close to Voyager’s original idea.

Critic remains the gate for:

* task success
* reward/progress
* whether to store skill

---

## Step 9: Skill saving

After success:

### For structured production path

Save only meaningful multi-step subplans, such as:

* `craftOakPlanks`
* `craftStick`
* `craftCraftingTable`
* `craftWoodenPickaxe`

Do **not** save things like:

* one-line `mine oak_log`
* raw `place furnace`

unless you later decide some enabler patterns are worth storing.

### For ActionAgent path

Save successful reusable code the same way Voyager already does.

So the skill system becomes shared infrastructure.

---

# Minimal internal data model

You do not need many objects.

## `Goal`

Examples:

* `HaveItem("iron_pickaxe",1)`
* `WorkspaceAvailable("furnace")`
* `CanHarvest("iron_ore")`

## `PlanNode`

Fields should be minimal:

* `goal`
* `method_name`
* `role` = `produce | enable`
* `save_as_skill`
* maybe `metadata`

That’s enough.

You do **not** need complex graph objects floating around everywhere at runtime.

The Resolver can internally build a DAG/tree, but the Executor mostly just needs an ordered list.

---

# How HTN fits here

You asked about handoff to HTN.

This is basically a **light HTN / GOAP hybrid**.

The decomposition logic is HTN-like:

* “to achieve X, do A, B, C”

The predicate checking is GOAP-like:

* “is this condition already satisfied?”
* “what action satisfies it?”

So your “HTN” layer can simply be the Resolver.

You do not need a separate giant HTN subsystem if Resolver already:

* recursively decomposes goals
* handles prerequisites
* returns executable order

That’s the cleanest version.

---

# The simplest possible control loop

Here’s the whole thing in one flow:

```text
Curriculum proposes task
    ↓
TaskClassifier
    ↓
Is task structured?
    ├─ No → ActionAgent → Executor → Critic → maybe save skill
    └─ Yes
          ↓
      SkillStore lookup
          ↓
      Existing skill?
          ├─ Yes → Executor → Critic
          └─ No
                ↓
             Resolver
                ↓
             PlanNodes
                ↓
             Executor
                ↓
      runtime missing predicate?
          ├─ Yes → Resolver repair → continue
          └─ No
                ↓
             Critic
                ↓
       success? maybe save reusable structured skills
```

That is the architecture I’d actually build.

---

# Why this is better than the current sprawling version

Because it avoids three bad patterns:

## 1. Planning emits JS

Bad because it mixes reasoning with implementation.

## 2. Every task goes through ActionAgent

Bad because the LLM is doing deterministic recipe expansion work.

## 3. Tool/workspace logic is encoded as item hacks

Bad because `stone_pickaxe required` is not really true if you already have iron.

This 6-class design fixes all three.

---

# What stays from original Voyager

You are not throwing Voyager away. You are narrowing each agent’s role.

## Keep:

* Curriculum Agent
* ActionAgent
* Critic
* Skill persistence
* environment execution model

## Replace / refactor:

* ad hoc missing dependency handling
* “everything is LLM-generated JS”
* flat skills with no dependency awareness

So it’s still Voyager, but with a structured production runtime in front of the ActionAgent.

---

# My recommended near-term implementation order

1. `TaskClassifier`
2. `Goal` predicates
3. `MethodRegistry`
4. `Resolver`
5. `Executor` for structured plan nodes
6. `SkillStore` integration
7. then fallback plumbing back into ActionAgent/Critic loop

That gets you the value fastest.

---

# One sentence summary

The clean version is:

**Voyager becomes a two-path system where structured resource-production goals are resolved by a predicate-based planner and only genuinely open-ended tasks fall through to the ActionAgent.**

If you want, next I can turn this into a single **authoritative markdown spec** your sub-agents can code against.
