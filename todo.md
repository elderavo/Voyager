Issues: 

# TODO: Integrate Executor module with HTN Scheduler 
  1. Curriculum Bot suggests a skill
  2. Executor learns a skill
  3. When executor sucesfully calls a known skill, scheduler decomposes it into primitives and places on the task queue. 
    Exp: this will allow for dynamic actions - a queue of primitives can be paused, re-prioritized, and interrupted without derailing the entire task
    new, priority actions can be put on top of the queue without affecting others behind it. 
# TODO: Integrate Executor module with Voyager
  1. Curriculum bot suggests a skill
  2. Executor tries to decompose it and learn the skill. 
  3. If Executor can't, then pass to Action bot for resolution. 
    Exp: this is a fallback option to ensure the bot never gets stuck, it's always at least trying to do an action. 
  4. The Action Bot is only invoked for things that aren't crafting, like exploreUntil, killMob, etc. 

# TODO: Integrate Mining and Smelting
  1. How is the bot supposed to know something needs to be mined? With what level pickaxe? Can Mineflayer do that or is that always going to be Action LLM?  
  2. Can we treat smelting the same as crafting (just give it a furnace and fuel)?

# TODO: step method
  1. Orchestrator and HTN need to be interruptible, but are recursive in nature. 
  2. Instead of calling primitives directly, implement a step method that has the primitive call, but also stubs for:
    - safety check 
    - phase check 
    - option to save state and "bug out" to be returned to later. 
  3. This is critical to allow events that happen in the middle of a cycle to be dealt with by out of cycle agents (curriculum, safety)
      without cancelling and clearing existing tasks. (ie, you need to be able to intrrupt and fight a skeleton shooting you, but you do want to continue mining what you came down there for when you're done.)
      ┌──────────────────────────────────────────────────────────────┐
      │                      ORCHESTRATOR.STEP()                     │
      │                                                              │
      │  1. Update facts                                             │
      │  2. danger = safety_model(obs)                               │
      │  3. phase = phase_scorer(...)                                │
      │  4. IF phase changed → INTERRUPT                             │
      │  5. IF primitive_queue empty → request new task + expand HTN │
      │  6. primitive = primitive_queue.pop_front()                  │
      │  7. direct_execute_primitive(primitive)                      │
      │  8. critic.observe(result)                                   │
      │                                                              │
      └───────────────┬──────────────────────────────────────────────┘

# THOUGHT: Can the HTN unlearn unused calls in skills?
  1. Would have to be through inventory checking after the fact.

# THOUGHT: Is overcrafting an issue? How do we currently handle quantity? 
  1. craftItem uses mineflayer provided recipes, and that returns the output num transparently to the bot. The output num should
  get handled in the dependency layer, if we only needed to do it once to satisfy the dep, then we got at least that many from the proceeding craft
  2. We don't handle that one oak log is enough to make sticks twice. What we will do is selectively cull the primitive task queue based on inventory.

# THOUGHT: Integrate a safety CV Model
  1. Take screencaps from prismarine viewer and embed them
  2. Classify the embeddings for safety. (dangerous/safe/unknown, mob in frame, lava, drowning)
  3. soft-max classifying for activity type (gathering, exploring, caving, fighting, stuck, etc)
  4. Feed safety classification as context for an interrupt, pause scheduled tasks if risk assesment goes past threshold. 
  5. Health and hunger need to be monitored along with visual frames. 

# THOUGHT: Other uses for CV
  1. How can we build structures? 
  2. How do we teach it what good structures are? 
  3. Integrate with other metrics in a "safety" JFS? 



# Dev Roadmap: 
0. Furnace placement and smelting dependencies.
1. Iron out Action Bot and HTN interplay - how do you cover everything that needs to be done in one or the other? 
2. Integrate HTN and Orchestrator 
3. 

