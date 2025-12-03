✔️ Patch 1 — Curriculum Prompt

Ensure Curriculum never emits mining verbs.

This is the only absolutely required patch.

Just add:

Never emit tasks beginning with mine, obtain, gather, collect, get, chop, harvest, dig, explore.
You must only emit Craft, Smelt, Cook, Kill, Equip tasks.


DONE.

✔️ Patch 2 — Old voyager.learn()

Remove the mining classification branch so mining tasks never route to Executor:

Change:
elif task.lower().startswith(("mine", "obtain", "gather", "collect")):
    task_type = "mine"


→ Remove entirely.

Delete the executor mining block as well:

elif use_executor and task_type == "mine":
    ...


Executor will still mine internally during craft.
Nothing breaks.

🟢 In the old system, this is essential.

✔️ Patch 3 — New learn_v2() (modular system)

For the modular system, you DO NOT need to adjust TaskClassifier.

Because:

Curriculum will never emit verbs that TaskClassifier maps to mining/gather

Those synonyms will never appear

TaskClassifier outputs:

CRAFT → primitive executor

Everything else → Action LLM executor

That is exactly correct behavior

🟢 No changes needed in the TaskClassifier.

✔️ Patch 4 — Action Agent

Do NOT restrict the Action Agent from generating mining skills.

It MUST remain the general fallback capable of generating:

exploration-based mining routines

navigational behavior

multi-step skills

corrective behavior when executor fails

The only minor protection worth keeping:

Do NOT save 1-line primitive routines as skills

Already implemented through is_one_line_primitive.

Otherwise, Action Agent should stay fully flexible.

🟢 Final Simplified Spec for Your Coder
1. Curriculum

Enforce:

Only Craft / Smelt / Cook / Kill / Equip tasks

No mining verbs, no obtain/gather/collect/get
(Requires only prompt editing)

2. voyager.learn() (old version)

Remove:

mining classification

mining executor path

So mining NEVER becomes a top-level routed action.

3. voyager.learn_v2() (modular)

Do nothing.
TaskClassifier is fine as-is, because it will never see mining verbs.

4. Executor

No changes.
It remains the only place where mining is supposed to happen.

5. Action Agent

No restrictions.
It remains the full-capability fallback planner.