from __future__ import annotations

import os
import random
import re
import shutil

# Disable ChromaDB telemetry before importing
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import voyager.utils as U
from voyager.prompts import load_prompt
from voyager.utils.json_utils import fix_and_parse_json
from voyager.utils import get_logger
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.vectorstores import Chroma
from voyager.agents.task_queue import TaskQueue, Task

logger = get_logger(__name__)


class CurriculumAgent:
    def __init__(
        self,
        model="gpt-3.5-turbo",
        temperature=0,
        qa_model="gpt-3.5-turbo",
        qa_temperature=0,
        http_timeout=120,
        ckpt_dir="ckpt",
        resume=False,
        mode="auto",
        warm_up=None,
        core_inventory_items: str | None = None,
    ):
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_retries=3,
            request_timeout=http_timeout,
        )
        self.qa_llm = ChatOpenAI(
            model=qa_model,
            temperature=qa_temperature,
            max_retries=3,
            request_timeout=http_timeout,
        )
        assert mode in [
            "auto",
            "manual",
        ], f"mode {mode} not supported"
        self.mode = mode
        self.ckpt_dir = ckpt_dir
        self._qa_cache_vectordb_dir = f"{ckpt_dir}/curriculum/vectordb"
        if not resume and os.path.exists(self._qa_cache_vectordb_dir):
            shutil.rmtree(self._qa_cache_vectordb_dir)
        U.f_mkdir(self._qa_cache_vectordb_dir)
        if resume:
            logger.info(f"Loading Curriculum Agent from {ckpt_dir}/curriculum")
            self.completed_tasks = U.load_json(
                f"{ckpt_dir}/curriculum/completed_tasks.json"
            )
            self.failed_tasks = U.load_json(f"{ckpt_dir}/curriculum/failed_tasks.json")
            self.qa_cache = U.load_json(f"{ckpt_dir}/curriculum/qa_cache.json")
        else:
            self.completed_tasks = []
            self.failed_tasks = []
            self.qa_cache = {}
        self.qa_cache_questions_vectordb = Chroma(
            collection_name="qa_cache_questions_vectordb",
            embedding_function=OpenAIEmbeddings(),
            persist_directory=self._qa_cache_vectordb_dir,
        )
        assert self.qa_cache_questions_vectordb._collection.count() == len(
            self.qa_cache
        ), (
            f"Curriculum Agent's qa cache question vectordb is not synced with qa_cache.json.\n"
            f"There are {self.qa_cache_questions_vectordb._collection.count()} questions in vectordb "
            f"but {len(self.qa_cache)} questions in qa_cache.json.\n"
            f"Did you set resume=False when initializing the agent?\n"
            f"You may need to manually delete the qa cache question vectordb directory for running from scratch.\n"
        )
        if not warm_up:
            warm_up = self.default_warmup
        self.warm_up = {}
        if "optional_inventory_items" in warm_up:
            assert core_inventory_items is not None
            self._core_inv_items_regex = re.compile(core_inventory_items)
            self.warm_up["optional_inventory_items"] = warm_up[
                "optional_inventory_items"
            ]
        else:
            self.warm_up["optional_inventory_items"] = 0
        for key in self.curriculum_observations:
            self.warm_up[key] = warm_up.get(key, self.default_warmup[key])
        self.warm_up["nearby_blocks"] = 0
        self.warm_up["inventory"] = 0
        self.warm_up["completed_tasks"] = 0
        self.warm_up["failed_tasks"] = 0

        self.task_queue = TaskQueue()
        logger.info("Initialized TaskQueue in CurriculumAgent")

    @property
    def default_warmup(self):
        return {
            "context": 15,
            "biome": 10,
            "time": 15,
            "nearby_blocks": 0,
            "other_blocks": 10,
            "nearby_entities": 5,
            "health": 15,
            "hunger": 15,
            "position": 0,
            "equipment": 0,
            "optional_inventory_items": 7,
            "chests": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
        }

    @property
    def curriculum_observations(self):
        return [
            "context",
            "biome",
            "time",
            "nearby_blocks",
            "other_blocks",
            "nearby_entities",
            "health",
            "hunger",
            "position",
            "equipment",
            "chests",
            "completed_tasks",
            "failed_tasks",
        ]

    @property
    def progress(self):
        return len(self.completed_tasks)

    def render_system_message(self):
        system_message = SystemMessage(content=load_prompt("curriculum"))
        assert isinstance(system_message, SystemMessage)
        return system_message

    def render_observation(self, *, events, chest_observation):
        assert events[-1][0] == "observe", "Last event must be observe"
        event = events[-1][1]
        biome = event["status"]["biome"]
        time_of_day = event["status"]["timeOfDay"]
        voxels = event["voxels"]
        block_records = event["blockRecords"]
        entities = event["status"]["entities"]
        health = event["status"]["health"]
        hunger = event["status"]["food"]
        position = event["status"]["position"]
        equipment = event["status"]["equipment"]
        inventory_used = event["status"]["inventoryUsed"]
        inventory = event["inventory"]

        if not any(
            "dirt" in block
            or "log" in block
            or "grass" in block
            or "sand" in block
            or "snow" in block
            for block in voxels
        ):
            biome = "underground"

        other_blocks = ", ".join(
            list(
                set(block_records).difference(set(voxels).union(set(inventory.keys())))
            )
        )
        other_blocks = other_blocks if other_blocks else "None"

        nearby_entities = (
            ", ".join([k for k, v in sorted(entities.items(), key=lambda x: x[1])])
            if entities
            else "None"
        )

        completed_tasks = (
            ", ".join(self.completed_tasks) if self.completed_tasks else "None"
        )
        failed_tasks = ", ".join(self.failed_tasks) if self.failed_tasks else "None"

        if self.progress < self.warm_up["optional_inventory_items"]:
            inventory = {
                k: v
                for k, v in inventory.items()
                if self._core_inv_items_regex.search(k) is not None
            }

        observation = {
            "context": "",
            "biome": f"Biome: {biome}\n\n",
            "time": f"Time: {time_of_day}\n\n",
            "nearby_blocks": f"Nearby blocks: {', '.join(voxels) if voxels else 'None'}\n\n",
            "other_blocks": f"Other blocks that are recently seen: {other_blocks}\n\n",
            "nearby_entities": f"Nearby entities: {nearby_entities}\n\n",
            "health": f"Health: {health:.1f}/20\n\n",
            "hunger": f"Hunger: {hunger:.1f}/20\n\n",
            "position": f"Position: x={position['x']:.1f}, y={position['y']:.1f}, z={position['z']:.1f}\n\n",
            "equipment": f"Equipment: {equipment}\n\n",
            "chests": chest_observation,
            "completed_tasks": f"Completed tasks so far: {completed_tasks}\n\n",
            "failed_tasks": f"Failed tasks that are too hard: {failed_tasks}\n\n",
        }
        return observation

    def render_human_message(self, *, events, chest_observation):
        content = ""
        observation = self.render_observation(
            events=events, chest_observation=chest_observation
        )
        if self.progress >= self.warm_up["context"]:
            questions, answers = self.run_qa(
                events=events, chest_observation=chest_observation
            )
            i = 1
            for question, answer in zip(questions, answers):
                if "Answer: Unknown" in answer or "language model" in answer:
                    continue
                observation["context"] += f"Question {i}: {question}\n"
                observation["context"] += f"{answer}\n\n"
                i += 1
                if i > 5:
                    break

        for key in self.curriculum_observations:
            if self.progress >= self.warm_up[key]:
                if self.warm_up[key] != 0:
                    should_include = random.random() < 0.8
                else:
                    should_include = True
                if should_include:
                    content += observation[key]

        logger.debug("Curriculum human message:\n%s", content, extra={"llm": True})
        return HumanMessage(content=content)

    def propose_next_task(self, *, events, chest_observation, max_retries=5):
        if events:
            inventoryUsed = events[-1][1]["status"].get("inventoryUsed", 0)
        else:
            inventoryUsed = 0

        if inventoryUsed >= 33:
            if chest_observation != "Chests: None\n\n":
                chests = chest_observation[8:-2].split("\n")
                for chest in chests:
                    content = chest.split(":")[1]
                    if content == " Unknown items inside" or content == " Empty":
                        position = chest.split(":")[0]
                        task = f"Deposit useless items into the chest at {position}"
                        context = (
                            f"Your inventory have {inventoryUsed} occupied slots before depositing. "
                            "After depositing, your inventory should only have 20 occupied slots. "
                            "You should deposit useless items such as andesite, dirt, cobblestone, etc. "
                            "Also, you can deposit low-level tools, "
                            "For example, if you have a stone pickaxe, you can deposit a wooden pickaxe. "
                            "Make sure the list of useless items are in your inventory "
                            "(do not list items already in the chest), "
                            "You can use bot.inventoryUsed() to check how many inventory slots are used."
                        )
                        return task, context

            if events and "chest" in events[-1][1]["inventory"]:
                task = "Place a chest"
                context = (
                    "You have a chest in inventory, place it around you. "
                    "If chests is not None, or nearby blocks contains chest, this task is success."
                )
            else:
                task = "Craft 1 chest"
                context = "Craft 1 chest with 8 planks of any kind of wood."
            return task, context

        messages = [
            self.render_system_message(),
            self.render_human_message(
                events=events, chest_observation=chest_observation
            ),
        ]

        if self.mode == "auto":
            return self.propose_next_ai_task(messages=messages, max_retries=max_retries)
        elif self.mode == "manual":
            return self.propose_next_manual_task()
        else:
            raise ValueError(f"Invalid curriculum agent mode: {self.mode}")

    def propose_next_ai_task(self, *, messages, max_retries=5):
        if max_retries == 0:
            raise RuntimeError("Max retries reached, failed to propose ai task.")
        curriculum = self.llm.invoke(messages).content
        logger.debug("Curriculum LLM response:\n%s", curriculum, extra={"llm": True})
        try:
            response = self.parse_ai_message(curriculum)
            assert "next_task" in response
            context = self.get_task_context(response["next_task"])
            return response["next_task"], context
        except Exception as e:
            logger.warning(f"Error parsing curriculum response: {e} — retrying")
            return self.propose_next_ai_task(
                messages=messages,
                max_retries=max_retries - 1,
            )

    def parse_ai_message(self, message):
        task = ""
        for line in message.split("\n"):
            if line.startswith("Task:"):
                task = line[5:].replace(".", "").strip()
        assert task, "Task not found in Curriculum Agent response"
        return {"next_task": task}

    def propose_next_manual_task(self):
        confirmed = False
        task, context = "", ""
        while not confirmed:
            task = input("Enter task: ")
            context = input("Enter context: ")
            print(f"Task: {task}\nContext: {context}")
            confirmed = input("Confirm? (y/n)").lower() in ["y", ""]
        return task, context

    def update_exploration_progress(self, info):
        task = info["task"]
        if task.startswith("Deposit useless items into the chest at"):
            return
        if info["success"]:
            logger.info(f"Completed task: {task}")
            self.completed_tasks.append(task)
        else:
            logger.info(f"Failed task: {task} — skipping to next")
            self.failed_tasks.append(task)
        self.clean_up_tasks()

    def clean_up_tasks(self):
        updated_completed_tasks = []
        updated_failed_tasks = self.failed_tasks
        for task in self.completed_tasks:
            if task not in updated_completed_tasks:
                updated_completed_tasks.append(task)
        for task in updated_completed_tasks:
            while task in updated_failed_tasks:
                updated_failed_tasks.remove(task)
        self.completed_tasks = updated_completed_tasks
        self.failed_tasks = updated_failed_tasks
        U.dump_json(
            self.completed_tasks, f"{self.ckpt_dir}/curriculum/completed_tasks.json"
        )
        U.dump_json(self.failed_tasks, f"{self.ckpt_dir}/curriculum/failed_tasks.json")

    def decompose_task(self, task, events):
        messages = [
            SystemMessage(content=load_prompt("curriculum_task_decomposition")),
            self.render_human_message(events=events, chest_observation=""),
            HumanMessage(content=f"Final task: {task}"),
        ]
        logger.debug("Curriculum task decomposition for: %s", task, extra={"llm": True})
        response = self.llm.invoke(messages).content
        logger.debug("Curriculum decomposition response:\n%s", response, extra={"llm": True})
        return fix_and_parse_json(response)

    def run_qa(self, *, events, chest_observation):
        questions_new, _ = self.run_qa_step1_ask_questions(
            events=events, chest_observation=chest_observation
        )
        questions = []
        answers = []
        for question in questions_new:
            if self.qa_cache_questions_vectordb._collection.count() > 0:
                docs_and_scores = (
                    self.qa_cache_questions_vectordb.similarity_search_with_score(
                        question, k=1
                    )
                )
                if docs_and_scores and docs_and_scores[0][1] < 0.05:
                    question_cached = docs_and_scores[0][0].page_content
                    assert question_cached in self.qa_cache
                    answer_cached = self.qa_cache[question_cached]
                    questions.append(question_cached)
                    answers.append(answer_cached)
                    continue
            answer = self.run_qa_step2_answer_questions(question=question)
            assert question not in self.qa_cache
            self.qa_cache[question] = answer
            self.qa_cache_questions_vectordb.add_texts(texts=[question])
            U.dump_json(self.qa_cache, f"{self.ckpt_dir}/curriculum/qa_cache.json")
            self.qa_cache_questions_vectordb.persist()
            questions.append(question)
            answers.append(answer)
        assert len(questions_new) == len(questions) == len(answers)
        return questions, answers

    def get_task_context(self, task):
        question = (
            f"How to {task.replace('_', ' ').replace(' ore', '').replace(' ores', '').replace('.', '').strip().lower()}"
            f" in Minecraft?"
        )
        if question in self.qa_cache:
            answer = self.qa_cache[question]
        else:
            answer = self.run_qa_step2_answer_questions(question=question)
            self.qa_cache[question] = answer
            self.qa_cache_questions_vectordb.add_texts(texts=[question])
            U.dump_json(self.qa_cache, f"{self.ckpt_dir}/curriculum/qa_cache.json")
            self.qa_cache_questions_vectordb.persist()
        context = f"Question: {question}\n{answer}"
        return context

    def render_system_message_qa_step1_ask_questions(self):
        return SystemMessage(content=load_prompt("curriculum_qa_step1_ask_questions"))

    def render_human_message_qa_step1_ask_questions(self, *, events, chest_observation):
        observation = self.render_observation(
            events=events, chest_observation=chest_observation
        )
        content = ""
        for key in self.curriculum_observations:
            content += observation[key]
        return HumanMessage(content=content)

    def run_qa_step1_ask_questions(self, *, events, chest_observation):
        biome = events[-1][1]["status"]["biome"].replace("_", " ")
        questions = [
            f"What are the blocks that I can find in the {biome} in Minecraft?",
            f"What are the items that I can find in the {biome} in Minecraft?",
            f"What are the mobs that I can find in the {biome} in Minecraft?",
        ]
        concepts = [biome, biome, biome]
        messages = [
            self.render_system_message_qa_step1_ask_questions(),
            self.render_human_message_qa_step1_ask_questions(
                events=events, chest_observation=chest_observation
            ),
        ]
        qa_response = self.qa_llm.invoke(messages).content
        try:
            pattern = r"Question \d+: (.+)\nConcept \d+: (.+)"
            pairs = re.findall(pattern, qa_response)
            questions_new = [pair[0] for pair in pairs]
            concepts_new = [pair[1] for pair in pairs]
            assert len(questions_new) == len(concepts_new)
            questions.extend(questions_new)
            concepts.extend(concepts_new)
        except Exception as e:
            logger.warning(f"Error parsing QA step 1 response: {e}")
        return questions, concepts

    def render_system_message_qa_step2_answer_questions(self):
        return SystemMessage(
            content=load_prompt("curriculum_qa_step2_answer_questions")
        )

    def render_human_message_qa_step2_answer_questions(self, question):
        content = f"Question: {question}"
        return HumanMessage(content=content)

    def run_qa_step2_answer_questions(self, question):
        messages = [
            self.render_system_message_qa_step2_answer_questions(),
            self.render_human_message_qa_step2_answer_questions(question=question),
        ]
        logger.debug("QA question: %s", question, extra={"llm": True})
        qa_answer = self.qa_llm.invoke(messages).content
        logger.debug("QA answer:\n%s", qa_answer, extra={"llm": True})
        return qa_answer

    def get_next_task_from_queue(self):
        if not self.task_queue.empty():
            next_task = self.task_queue.pop()
            logger.debug(f"Popped task from queue: {next_task} (remaining: {self.task_queue.size()})")
            return next_task
        return None

    def process_action_response(self, intention, primitive_actions, missing_dependencies):
        logger.info(
            f"Processing action response — intention: {intention} | "
            f"primitives: {primitive_actions} | missing: {missing_dependencies}"
        )

        for dep in missing_dependencies:
            self.task_queue.push(Task("dependency", dep, parent=intention))

        for pa in primitive_actions:
            if isinstance(pa, dict):
                action_type = pa.get("type", "unknown")
                payload = pa.get("payload", None)
                self.task_queue.push(Task(action_type, payload, parent=intention))
            else:
                self.task_queue.push(Task(pa, None, parent=intention))

        return self.task_queue.pop()
