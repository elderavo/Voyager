(Minecraft) C:\Users\Alex\Desktop\Projects\Coding\Minecraft\Voyager>python run_voyager.py
C:\Users\Alex\Desktop\Projects\Coding\Minecraft\Voyager\voyager\prompts\__init__.py:1: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.
  import pkg_resources
C:\Users\Alex\Desktop\Projects\Coding\Minecraft\Voyager\voyager\agents\curriculum.py:69: LangChainDeprecationWarning: The class `Chroma` was deprecated in LangChain 0.2.9 and will be removed in 1.0. An updated version of the class exists in the `langchain-chroma package and should be used instead. To use it run `pip install -U `langchain-chroma` and import as `from `langchain_chroma import Chroma``.
  self.qa_cache_questions_vectordb = Chroma(
Failed to send telemetry event ClientStartEvent: capture() takes 1 positional argument but 3 were given
Failed to send telemetry event ClientCreateCollectionEvent: capture() takes 1 positional argument but 3 were given
Initialized TaskQueue in CurriculumAgent
Failed to send telemetry event ClientStartEvent: capture() takes 1 positional argument but 3 were given
Failed to send telemetry event ClientCreateCollectionEvent: capture() takes 1 positional argument but 3 were given
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 32740.
Server started on port 3000

****Curriculum Agent human message****
Nearby blocks: dirt, grass_block, oak_leaves, oak_log, grass, birch_leaves, birch_log

Position: x=9.5, y=64.0, z=6.5

Equipment: [None, None, None, None, 'oak_log', None]

Chests: None

Completed tasks so far: None

Failed tasks that are too hard: None


****Curriculum Agent ai message****
Reasoning: You are currently in a forest biome with both oak and birch trees nearby. You have already obtained an oak log, but you haven't obtained a birch log yet. Collecting different types of wood can help you craft diverse items in the future.
Task: Obtain a birch log.
Curriculum Agent Question: How to obtain a birch log in Minecraft?
Curriculum Agent Answer: To obtain a birch log in Minecraft, you need to find and chop down a birch tree using an axe. Birch trees have white bark and can be found in the forest biome.
C:\Users\Alex\Desktop\Projects\Coding\Minecraft\Voyager\voyager\agents\curriculum.py:452: LangChainDeprecationWarning: Since Chroma 0.4.x the manual persistence method is no longer supported as docs are automatically persisted.
  self.qa_cache_questions_vectordb.persist()
Starting task Obtain a birch log for at most 4 times
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 29376.
Server started on port 3000

Render Action Agent system message with 0 skills
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 2572.
Server started on port 3000

Your last round rollout terminated due to error:
'charmap' codec can't decode byte 0x9d in position 852: character maps to <undefined>
Failed to complete task Obtain a birch log. Skipping to next task.
Completed tasks:
Failed tasks: Obtain a birch log
****Curriculum Agent human message****
Nearby blocks: dirt, grass_block, oak_leaves, oak_log, grass, birch_leaves, birch_log

Position: x=9.5, y=64.0, z=6.5

Equipment: [None, None, None, None, 'oak_log', None]

Chests: None

Completed tasks so far: None

Failed tasks that are too hard: Obtain a birch log


****Curriculum Agent ai message****
Reasoning: Since you have an oak log in your equipment, you can use it to craft wooden planks. This will allow you to create basic tools and structures.
Task: Craft 4 oak planks.
Curriculum Agent Question: How to craft 4 oak planks in Minecraft?
Curriculum Agent Answer: To craft 4 oak planks in Minecraft, you need to place one oak log in any crafting grid (such as the 2x2 grid in your inventory) and it will yield 4 oak planks.
Starting task Craft 4 oak planks for at most 4 times
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 2580.
Server started on port 3000

Render Action Agent system message with 0 skills
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 2716.
Server started on port 3000

Your last round rollout terminated due to error:
'charmap' codec can't decode byte 0x9d in position 852: character maps to <undefined>
Failed to complete task Craft 4 oak planks. Skipping to next task.
Completed tasks:
Failed tasks: Obtain a birch log, Craft 4 oak planks
****Curriculum Agent human message****
Nearby blocks: dirt, grass_block, oak_leaves, oak_log, grass, birch_leaves, birch_log

Position: x=9.5, y=64.0, z=6.5

Equipment: [None, None, None, None, 'oak_log', None]

Chests: None

Completed tasks so far: None

Failed tasks that are too hard: Obtain a birch log, Craft 4 oak planks
