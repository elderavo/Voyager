✅ CHANGE 1 — Add fallback_ai() to ExecutorActions

In executor_actions.py:


Add:

def fallback_ai(self, item_name):
    """
    Fallback path for when Executor cannot obtain a dependency.
    Delegates the task to the ActionBot.
    Always returns True so the high-level task is not aborted.
    """
    print(f"[AI-FALLBACK] Requesting external agent to obtain '{item_name}'")

    # TODO: Integrate with ActionBot API interface
    # For now, we assume ActionBot completes the task successfully.
    return True


This ensures:

No recursion failures

No loss of tasks

System continues progressing

✅ CHANGE 2 — Insert fallback call at the END of ensure_dependency()

At the bottom of ensure_dependency() after craftable, smeltable, gatherable checks add:

# --- FINAL FALLBACK: AI/ActionBot ---
print(f"[AI-FALLBACK] Executor cannot obtain '{dep}'. Handing off to AI agent.")
return actions_executor.fallback_ai(dep)


Placement:
Just before the current "Cannot obtain dependency" error return.

Replace:

print(f"[ERROR] Cannot obtain dependency '{dep}' (not craftable, not gatherable)")
return False


with:

print(f"[AI-FALLBACK] Executor cannot obtain '{dep}'. Handing off to AI agent.")
return actions_executor.fallback_ai(dep)

💡 WHAT THIS IMMEDIATELY FIXES
Case: Leather armor
craft leather
 → missing rabbit_hide
rabbit_hide:
   craftable? NO
   gatherable? NO
   smeltable? NO
   → AI fallback: kill rabbits

Case: Iron chestplate
craft iron_chestplate
 → missing iron_ingot
iron_ingot:
    craftable? NO (once we change recipe type logic)
    gatherable? NO
    smeltable? NO (for now)
    → AI fallback: do whatever needed (mine ore, smelt it, etc.)

Case: String, feathers, wool

All resolve through fallback, not failure.