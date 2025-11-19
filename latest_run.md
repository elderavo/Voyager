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
Subprocess mineflayer started with PID 27032.
Server started on port 3000

****Curriculum Agent human message****
Nearby blocks: dirt, grass_block, oak_leaves, oak_log, grass, birch_leaves, birch_log

Position: x=9.5, y=64.0, z=6.5

Equipment: [None, None, None, None, 'oak_log', None]

Chests: None

Completed tasks so far: None

Failed tasks that are too hard: None


****Curriculum Agent ai message****
Reasoning: You are currently in a forest biome with oak and birch trees nearby. You have an oak log in your equipment but no other tools or items. The first step in Minecraft is usually to gather more wood to craft basic tools.
Task: Obtain 4 oak logs.
Curriculum Agent Question: How to obtain 4 oak logs in Minecraft?
Curriculum Agent Answer: To obtain 4 oak logs in Minecraft, you can start by finding oak trees in the game. Use a tool such as an axe to chop down the oak trees, which will drop oak logs. Each oak tree typically drops multiple oak logs, so you may only need to chop down one or two trees to obtain 4 oak logs.
C:\Users\Alex\Desktop\Projects\Coding\Minecraft\Voyager\voyager\agents\curriculum.py:452: LangChainDeprecationWarning: Since Chroma 0.4.x the manual persistence method is no longer supported as docs are automatically persisted.
  self.qa_cache_questions_vectordb.persist()
Starting task Obtain 4 oak logs for at most 4 times
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 6296.
Server started on port 3000

Render Action Agent system message with 0 skills
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 13372.
Server started on port 3000

Your last round rollout terminated due to error:
'charmap' codec can't decode byte 0x9d in position 852: character maps to <undefined>
Failed to complete task Obtain 4 oak logs. Skipping to next task.
Completed tasks:
Failed tasks: Obtain 4 oak logs
****Curriculum Agent human message****
Nearby blocks: dirt, grass_block, oak_leaves, oak_log, grass, birch_leaves, birch_log

Position: x=9.5, y=64.0, z=6.5

Equipment: [None, None, None, None, 'oak_log', None]

Chests: None

Completed tasks so far: None

Failed tasks that are too hard: Obtain 4 oak logs


****Curriculum Agent ai message****
Reasoning: Since the player failed to obtain 4 oak logs previously, it might be a good idea to start with a smaller task to build up their skills. There are both oak and birch trees nearby, so the player can try to obtain logs from these trees.
Task: Obtain 1 birch log.
Curriculum Agent Question: How to obtain 1 birch log in Minecraft?
Curriculum Agent Answer: To obtain 1 birch log in Minecraft, you need to find a birch tree and use an axe to chop it down. Birch trees have white bark and can be found in various biomes such as forests and plains.
Starting task Obtain 1 birch log for at most 4 times
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 27892.
Server started on port 3000

Render Action Agent system message with 0 skills
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 26508.
Server started on port 3000

Your last round rollout terminated due to error:
'charmap' codec can't decode byte 0x9d in position 852: character maps to <undefined>
Failed to complete task Obtain 1 birch log. Skipping to next task.
Mineflayer process has exited, restarting
Subprocess mineflayer started with PID 26508.
Server started on port 3000

Your last round rollout terminated due to error:
'charmap' codec can't decode byte 0x9d in position 852: character maps to <undefined>
Failed to complete task Obtain 1 birch log. Skipping to next task.
Completed tasks:

Your last round rollout terminated due to error:
'charmap' codec can't decode byte 0x9d in position 852: character maps to <undefined>
Failed to complete task Obtain 1 birch log. Skipping to next task.
Completed tasks:
Your last round rollout terminated due to error:
'charmap' codec can't decode byte 0x9d in position 852: character maps to <undefined>
Failed to complete task Obtain 1 birch log. Skipping to next task.
Completed tasks:
'charmap' codec can't decode byte 0x9d in position 852: character maps to <undefined>
Failed to complete task Obtain 1 birch log. Skipping to next task.
Completed tasks:
Completed tasks:
Failed tasks: Obtain 4 oak logs, Obtain 1 birch log
****Curriculum Agent human message****
Nearby blocks: dirt, grass_block, oak_leaves, oak_log, grass, birch_leaves, birch_log
Failed tasks: Obtain 4 oak logs, Obtain 1 birch log
****Curriculum Agent human message****
Nearby blocks: dirt, grass_block, oak_leaves, oak_log, grass, birch_leaves, birch_log
****Curriculum Agent human message****
Nearby blocks: dirt, grass_block, oak_leaves, oak_log, grass, birch_leaves, birch_log
Nearby blocks: dirt, grass_block, oak_leaves, oak_log, grass, birch_leaves, birch_log

Position: x=9.5, y=64.0, z=6.5

Position: x=9.5, y=64.0, z=6.5
Position: x=9.5, y=64.0, z=6.5

Equipment: [None, None, None, None, 'oak_log', None]

Chests: None

Completed tasks so far: None

Failed tasks that are too hard: Obtain 4 oak logs, Obtain 1 birch log
