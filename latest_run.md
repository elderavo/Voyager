PS C:\Users\Alex\Desktop\Projects\Coding\Minecraft\voyager\env\mineflayer> & C:/Users/Alex/miniconda3/envs/Minecraft/python.exe c:/Users/Alex/Desktop/Projects/Coding/Minecraft/run_voyager.py
c:\Users\Alex\Desktop\Projects\Coding\Minecraft\voyager\prompts\__init__.py:1: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.
  import pkg_resources
c:\Users\Alex\Desktop\Projects\Coding\Minecraft\voyager\agents\curriculum.py:69: LangChainDeprecationWarning: The class `Chroma` was deprecated in LangChain 0.2.9 and will be removed in 1.0. An updated version of the class exists in the `langchain-chroma package and should be used instead. To use it run `pip install -U `langchain-chroma` and import as `from `langchain_chroma import Chroma``.
  self.qa_cache_questions_vectordb = Chroma(
Failed to send telemetry event ClientStartEvent: capture() takes 1 positional argument but 3 were given
Failed to send telemetry event ClientCreateCollectionEvent: capture() takes 1 positional argument but 3 were given
Initialized TaskQueue in CurriculumAgent
Failed to send telemetry event ClientStartEvent: capture() takes 1 positional argument but 3 were given
Failed to send telemetry event ClientCreateCollectionEvent: capture() takes 1 positional argument but 3 were given
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 29732.
Server started on port 3000

****Curriculum Agent human message****
Nearby blocks: grass_block, dirt, grass, stone, azure_bluet, dandelion, oxeye_daisy

Position: x=4.5, y=86.0, z=-5.5

Equipment: [None, None, None, None, None, None]

Chests: None

Completed tasks so far: None

Failed tasks that are too hard: None


****Curriculum Agent ai message****
Reasoning: As you have no equipment and haven't completed any tasks yet, the first step should be to gather some basic resources. Wood is a fundamental resource in Minecraft, used for crafting many basic tools and items.
Task: Obtain a wood log.
Curriculum Agent Question: How to obtain a wood log in Minecraft?
Curriculum Agent Answer: To obtain a wood log in Minecraft, you can start by punching a tree. This will cause wood blocks to drop, which you can then collect and craft into wood logs.
c:\Users\Alex\Desktop\Projects\Coding\Minecraft\voyager\agents\curriculum.py:452: LangChainDeprecationWarning: Since Chroma 0.4.x the manual persistence method is no longer supported as docs are automatically persisted.
  self.qa_cache_questions_vectordb.persist()
Starting task Obtain a wood log for at most 4 times
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 34616.
Server started on port 3000

Render Action Agent system message with 0 skills
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 30992.
Server started on port 3000

Your last round rollout terminated due to error:
'charmap' codec can't decode byte 0x9d in position 852: character maps to <undefined>
Failed to complete task Obtain a wood log. Skipping to next task.
Completed tasks:
Failed tasks: Obtain a wood log
****Curriculum Agent human message****
Nearby blocks: grass_block, dirt, grass, stone, azure_bluet, dandelion, oxeye_daisy

Position: x=4.5, y=86.0, z=-5.5

Equipment: [None, None, None, None, None, None]

Chests: None

Completed tasks so far: None

Failed tasks that are too hard: Obtain a wood log


****Curriculum Agent ai message****
Reasoning: Since the task to obtain a wood log was too hard and failed, it's likely that there are no trees nearby. However, there are stones nearby which can be used to craft basic tools.
Task: Mine 3 stones.
Curriculum Agent Question: How to mine 3 stones in Minecraft?
Curriculum Agent Answer: To mine 3 stones in Minecraft, you will need a pickaxe made of wood, stone, iron, diamond, or netherite. Approach the stone block and use the pickaxe to break it. Each time you break a stone block, you will collect one stone. Repeat this process three times to mine 3 stones.
Starting task Mine 3 stones for at most 4 times
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 1384.
Server started on port 3000

Render Action Agent system message with 0 skills
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 5160.
Server started on port 3000

Your last round rollout terminated due to error:
'charmap' codec can't decode byte 0x9d in position 852: character maps to <undefined>
Failed to complete task Mine 3 stones. Skipping to next task.
Completed tasks:
Failed tasks: Obtain a wood log, Mine 3 stones
****Curriculum Agent human message****
Nearby blocks: grass_block, dirt, grass, stone, azure_bluet, dandelion, oxeye_daisy

Position: x=4.5, y=86.0, z=-5.5

Equipment: [None, None, None, None, None, None]

Chests: None

Completed tasks so far: None

Failed tasks that are too hard: Obtain a wood log, Mine 3 stones


****Curriculum Agent ai message****
Reasoning: Since you failed to obtain a wood log and mine stones, it seems you don't have the necessary tools yet. You can start by collecting some flowers around you, which can be used for crafting dyes later.
Task: Collect 1 dandelion.
Curriculum Agent Question: How to collect 1 dandelion in Minecraft?
Curriculum Agent Answer: To collect a dandelion in Minecraft, you can find them growing naturally in grassy areas. Simply walk around until you spot one and then use any tool (such as your hand) to break the block it's on and collect the dandelion.
Starting task Collect 1 dandelion for at most 4 times
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 38712.
Server started on port 3000

Render Action Agent system message with 0 skills
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 32796.
Server started on port 3000

Your last round rollout terminated due to error:
'charmap' codec can't decode byte 0x9d in position 852: character maps to <undefined>
Failed to complete task Collect 1 dandelion. Skipping to next task.
Completed tasks:
Failed tasks: Obtain a wood log, Mine 3 stones, Collect 1 dandelion
****Curriculum Agent human message****
Nearby blocks: grass_block, dirt, grass, stone, azure_bluet, dandelion, oxeye_daisy

Position: x=4.5, y=86.0, z=-5.5

Equipment: [None, None, None, None, None, None]

Chests: None

Completed tasks so far: None

Failed tasks that are too hard: Obtain a wood log, Mine 3 stones, Collect 1 dandelion


****Curriculum Agent ai message****
Reasoning: Since the player has failed to obtain a wood log and mine stones, it seems that the player does not have the necessary tools yet. The player is also in an area with flowers, which can be collected without any tools.        
Task: Collect 1 azure_bluet.
Curriculum Agent Question: How to collect 1 azure bluet in Minecraft?
Curriculum Agent Answer: To collect an azure bluet in Minecraft, you can find this flower growing naturally in flower forests, plains, and sunflower plains biomes. Simply use shears to collect the azure bluet without destroying it.   
Starting task Collect 1 azure_bluet for at most 4 times
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 37940.
Server started on port 3000