Below is **exactly how experienced software engineers would merge two diverging branches** (task-queue branch and HTN-branch), preserve Voyager compatibility, and layer the new “interruptible-step orchestrator” architecture on top *without* breaking either system.

This is a **realistic engineering plan**, not theory.

---

# ⭐ CORE GUIDING PRINCIPLES

1. **Don’t merge branches directly.**
   Merge both into a **new feature branch** that introduces the interruptible architecture.

2. **Treat existing branches as “providers” of capabilities:**

   * **HTN branch:** gives you `expand(...) → subtasks → primitives`
   * **Task queue branch:** gives you the queueing/execution model
   * **Base Voyager branch:** gives you `direct_execute_*()` primitive actions & skill library

3. **Build a *new Orchestrator layer* above all three**
   without rewriting their internals.

This keeps everything **backwards compatible** and minimizes breakage.

---

# ⭐ OVERALL MERGE STRATEGY (WHAT REAL ENGINEERS DO)

## **Step 1 — Freeze the current HTN and task-queue APIs**

Define *stable interfaces* so the orchestrator can talk to both:

**HTN API**

```python
htn.expand(task) -> List[Primitive]
```

**Task Queue API**

```python
task_queue.push(primitive)
primitive = task_queue.pop()
```

**Direct executor API:**

```python
direct_execute_primitive(primitive) -> result
```

Everything else remains untouched.

This is crucial: *agree on API boundaries before merging anything.*

---

## **Step 2 — Create a NEW orchestrator wrapper (“StepOrchestrator”)**

This is the new component that will *wrap and coordinate* all existing modules.

Example skeleton:

```python
class StepOrchestrator:
    def __init__(self, htn, queue, curriculum, safety, scorer, critic):
        self.htn = htn
        self.queue = queue
        self.curriculum = curriculum
        self.safety = safety
        self.scorer = scorer
        self.critic = critic

        self.current_phase = None
        self.current_task = None
        self.paused_context = None
```

This is the **new “brains”** of the system.
Everything else stays in its own branch-level file.

---

## **Step 3 — Keep old Voyager “direct_execute” methods untouched**

These remain *exactly as-is*:

```python
direct_execute_mine(...)
direct_execute_craft(...)
direct_execute_place(...)
```

The new orchestrator simply calls the old system.

This guarantees **full backward compatibility** with any old code that relied on direct execution.

---

## **Step 4 — Implement the “step” function ON TOP of both branches**

The `step()` method is brand new, and it uses **both** HTN and task queue branches:

```python
def step(self):
    self.update_facts()

    danger = self.safety.evaluate(self.facts)
    phase = self.scorer.evaluate(self.goal_graph, self.facts, danger)

    if phase != self.current_phase:
        self.interrupt_and_replan(phase)

    if self.queue.empty():
        self.current_task = self.curriculum.next_task(phase)
        primitives = self.htn.expand(self.current_task)
        self.queue.extend(primitives)

    # execute ONE primitive
    primitive = self.queue.pop()
    result = direct_execute_primitive(primitive)

    self.critic.observe(primitive, result)
```

Notice:

* **HTN branch only gives primitive lists**
* **Task queue branch manages queues**
* **Direct execute is unchanged**

All branches remain compatible and reusable.

---

## **Step 5 — Merge both feature branches INTO the orchestrator feature branch**

Not into main, not into each other.
Do this:

```
main (base Voyager)
│
├─ branch/task-queue-working
│
├─ branch/htn-decomp-working
│
└─ ❗ branch/interruptible-orchestrator  (your new branch)
```

Then:

```
git merge task-queue-working into interruptible-orchestrator
git merge htn-decomp-working into interruptible-orchestrator
```

Resolve conflicts **ONLY inside StepOrchestrator**, not in core logic.

This prevents either branch from overwriting the other.

---

## **Step 6 — Add a compatibility shim for older Voyager logic**

Inside StepOrchestrator.step():

If HTN expansion fails or returns empty:

```python
if not primitives:
    # fallback to old voyager style executor
    return curriculum.generate_primitive_task()
```

If task-queue logic fails:

```python
if direct_execute_primitive fails:
    regenerate primitives from HTN
```

This preserves behavior from all older branches.

---

# ⭐ WHAT STAYS THE SAME (NO BREAKAGE)

* Direct executor
* Primitive skills
* HTN method files
* Task queue underlying datastructure
* ActionBot integration
* Mineflayer connection
* Critic
* Curriculum bot logic

The only new thing is the **step orchestrator** that ties them together.

---

# ⭐ WHAT CHANGES (NEW LAYER ONLY)

* New StepOrchestrator class
* New interrupt/resume logic
* New safety-phase scoring before each primitive
* HTN only called once per task, not per execution
* Discord queue instead of batch primitive execution

Everything else remains untouched → backwards compatible.

---

# ⭐ FINAL BLOCK DIAGRAM (Updated for Backwards Compatibility)

```
           ┌───────── existing Voyager ─────────┐
           │                                     │
           │           DIRECT EXECUTOR           │
           │   (direct_execute_* unchanged)      │
           └───────────────────┬─────────────────┘
                               │
                               ▼
       ┌────────────────────────────────────────┐
       │         NEW STEP ORCHESTRATOR          │
       │   integrates HTN + task-queue + safety │
       └──────────┬──────────────┬──────────────┘
                  │              │
                  │              │
                  ▼              ▼
     ┌─────────────────┐     ┌───────────────┐
     │     HTN BRANCH  │     │ TASK-QUEUE    │
     │ expand(task)->[]│     │ pop/push impl │
     └─────────────────┘     └───────────────┘
                  │              │
                  └─────── primitives ───────┘
                               │
                               ▼
       ┌────────────────────────────────────────┐
       │     SAFETY + PHASE SCORER (new)        │
       │   (CV danger, hp, hunger, milestones)  │
       └────────────────────────────────────────┘
                               │
                               ▼
       ┌────────────────────────────────────────┐
       │     CURRICULUM BOT (unchanged)         │
       └────────────────────────────────────────┘
                               │
                               ▼
       ┌────────────────────────────────────────┐
       │          ACTION BOT (unchanged)        │
       └────────────────────────────────────────┘
                               │
                               ▼
       ┌────────────────────────────────────────┐
       │           CRITIC (unchanged)           │
       └────────────────────────────────────────┘
```

Everything is layered so each old branch still works independently.

---

# ⭐ FINAL EXPLANATION (CRUCIAL)

You are **not merging HTN branch into task-queue branch**.
You are merging both branches into a **wrapper orchestrator** that uses both through stable APIs.

This is how professional engineers maintain backwards compatibility:

* Don’t rewrite old modules
* Don’t merge them destructively
* Wrap them in a common orchestrator
* Introduce new logic above them

This minimizes risk and dramatically speeds integration.

---

If you want, I can:

* Write the entire `StepOrchestrator` class in Python
* Create a compatibility shim layer for Voyager modules
* Generate a migration plan from your two branches
* Produce a Git merging strategy document

Just say which you want next.
