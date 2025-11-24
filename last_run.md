Issues: 

Integration of the executor module within the voyager framework. [IGNORE FOR NOW]

# TODO: Integrate Executor module with HTN Scheduler 
  1. Curriculum Bot suggests a skill
  2. Executor learns a skill
  3. When executor sucesfully calls a known skill, scheduler decomposes it into primitives and places on the task queue. 

# TODO: Integrate Executor module with Voyager
  1. Curriculum bot suggests a skill
  2. Executor tries to decompose it and learn the skill. 
  3. If Executor can't, then pass to Action bot for resolution. 

# TODO: Integrate Mining and Smelting
  1. How is the bot supposed to know something needs to be mined? With what level pickaxe? Can Mineflayer do that or is that always going to be Action LLM?  
  2. Can we treat smelting the same as crafting (just give it a furnace and fuel)?

# TODO: Can the HTN unlearn unused calls in skills? 