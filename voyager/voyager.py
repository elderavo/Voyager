import copy
import json
import os
import shutil
import time
import traceback
from typing import Dict

import voyager.utils as U
from .env import VoyagerEnv
from voyager.utils import get_logger

from .agents import ActionAgent
from .agents import CriticAgent
from .agents import CurriculumAgent
from .agents import SkillManager
from .htn import HTNOrchestrator

logger = get_logger(__name__)


# TODO: remove event memory
class Voyager:
    def __init__(
        self,
        mc_port: int = None,
        mc_host: str = "localhost",
        azure_login: Dict[str, str] = None,
        server_port: int = 3000,
        openai_api_key: str = None,
        env_wait_ticks: int = 40,
        env_step_timeout: int = 600,
        max_iterations: int = 160,
        reset_placed_if_failed: bool = False,
        action_agent_model: str = "gpt-4",
        action_agent_temperature: float = 0,
        action_agent_task_max_retries: int = 4,
        action_agent_show_chat_log: bool = True,
        action_agent_show_execution_error: bool = True,
        curriculum_agent_model: str = "gpt-4",
        curriculum_agent_temperature: float = 0,
        curriculum_agent_qa_model: str = "gpt-3.5-turbo",
        curriculum_agent_qa_temperature: float = 0,
        curriculum_agent_warm_up: Dict[str, int] = None,
        curriculum_agent_core_inventory_items: str = r".*_log|.*_planks|stick|crafting_table|furnace"
        r"|cobblestone|dirt|coal|.*_pickaxe|.*_sword|.*_axe",
        curriculum_agent_mode: str = "auto",
        critic_agent_model: str = "gpt-4",
        critic_agent_temperature: float = 0,
        critic_agent_mode: str = "auto",
        skill_manager_model: str = "gpt-3.5-turbo",
        skill_manager_temperature: float = 0,
        skill_manager_retrieval_top_k: int = 5,
        openai_api_timeout: int = 240,
        ckpt_dir: str = "ckpt",
        skill_library_dir: str = None,
        resume: bool = False,
    ):
        """
        The main class for Voyager.
        Action agent is the iterative prompting mechanism in paper.
        Curriculum agent is the automatic curriculum in paper.
        Critic agent is the self-verification in paper.
        """
        # Wipe the checkpoint directory at the start of every fresh run so stale
        # skills, curriculum state, and events from previous sessions don't bleed
        # in.  Agents create their own subdirs during __init__, so this must run
        # before any agent is constructed.
        if not resume and os.path.exists(ckpt_dir):
            logger.info(f"Fresh run — wiping checkpoint directory: {ckpt_dir}")
            shutil.rmtree(ckpt_dir)

        # init env
        self.env = VoyagerEnv(
            mc_port=mc_port,
            mc_host=mc_host,
            azure_login=azure_login,
            server_port=server_port,
            step_timeout=env_step_timeout,
        )
        self.env_wait_ticks = env_wait_ticks
        self.reset_placed_if_failed = reset_placed_if_failed
        self.max_iterations = max_iterations

        # set openai api key
        os.environ["OPENAI_API_KEY"] = openai_api_key

        # init agents
        self.action_agent = ActionAgent(
            model=action_agent_model,
            temperature=action_agent_temperature,
            http_timeout=openai_api_timeout,
            ckpt_dir=ckpt_dir,
            resume=resume,
            chat_log=action_agent_show_chat_log,
            execution_error=action_agent_show_execution_error,
        )
        self.action_agent_task_max_retries = action_agent_task_max_retries
        self.curriculum_agent = CurriculumAgent(
            model=curriculum_agent_model,
            temperature=curriculum_agent_temperature,
            qa_model=curriculum_agent_qa_model,
            qa_temperature=curriculum_agent_qa_temperature,
            http_timeout=openai_api_timeout,
            ckpt_dir=ckpt_dir,
            resume=resume,
            mode=curriculum_agent_mode,
            warm_up=curriculum_agent_warm_up,
            core_inventory_items=curriculum_agent_core_inventory_items,
        )
        self.critic_agent = CriticAgent(
            model=critic_agent_model,
            temperature=critic_agent_temperature,
            http_timeout=openai_api_timeout,
            mode=critic_agent_mode,
        )
        self.skill_manager = SkillManager(
            model=skill_manager_model,
            temperature=skill_manager_temperature,
            retrieval_top_k=skill_manager_retrieval_top_k,
            http_timeout=openai_api_timeout,
            ckpt_dir=skill_library_dir if skill_library_dir else ckpt_dir,
            resume=True if resume or skill_library_dir else False,
        )
        self.recorder = U.EventRecorder(ckpt_dir=ckpt_dir, resume=resume)
        self.resume = resume

        # Initialize HTN execution system lazily after the env is ready
        self.htn_orchestrator = None
        self._htn_initialized = False

        # init variables for rollout
        self.action_agent_rollout_num_iter = -1
        self.task = None
        self.context = ""
        self.messages = None
        self.conversations = []
        self.last_events = None

        # Execution tracking for skill tree building
        self.execution_chain = []
        self.top_level_task = None
        self.top_level_skill_name = None

    def reset(self, task, context="", reset_env=True):
        self.action_agent_rollout_num_iter = 0
        self.task = task
        self.context = context
        self.top_level_task = task
        self.execution_chain = []

        if reset_env:
            self.env.reset(
                options={
                    "mode": "soft",
                    "wait_ticks": self.env_wait_ticks,
                }
            )
        difficulty = (
            "easy" if len(self.curriculum_agent.completed_tasks) > 15 else "peaceful"
        )
        events = self.env.step(
            "bot.chat(`/time set ${getNextTime()}`);\n"
            + f"bot.chat('/difficulty {difficulty}');"
        )
        skills = self.skill_manager.retrieve_skills(query=self.context)
        logger.info(f"Render Action Agent system message with {len(skills)} skills")
        system_message = self.action_agent.render_system_message(skills=skills)
        human_message = self.action_agent.render_human_message(
            events=events, code="", task=self.task, context=context, critique=""
        )
        self.messages = [system_message, human_message]
        logger.debug("Action Agent human message:\n%s", human_message.content, extra={"llm": True})
        assert len(self.messages) == 2
        self.conversations = []
        return self.messages

    def close(self):
        self.env.close()

    def _request_skill_for_prereq(self, item_name):
        """
        Request Action LLM to generate a new skill for a missing prerequisite.
        Resets conversation context without resetting Mineflayer environment state.
        """
        logger.info(f"Requesting skill generation for prerequisite: {item_name}")

        prereq_task = f"Obtain {item_name}"
        prereq_context = (
            f"Generate a skill to obtain {item_name}. "
            f"Use only primitive functions (mineBlock, craftItem, smeltItem, etc.) or known skills. "
            f"This is a prerequisite for a larger task."
        )

        self.task = prereq_task
        self.context = prereq_context
        self.action_agent_rollout_num_iter = 0

        events = self.env.step("bot.chat('Preparing to obtain prerequisite');")

        skills = self.skill_manager.retrieve_skills(query=prereq_context)
        system_message = self.action_agent.render_system_message(skills=skills)
        human_message = self.action_agent.render_human_message(
            events=events,
            code="",
            task=prereq_task,
            context=prereq_context,
            critique=""
        )

        self.messages = [system_message, human_message]
        logger.debug(f"New skill request messages prepared for: {item_name}")
        return self.messages

    def _is_top_level_task_complete(self):
        return (self.top_level_task is not None and
                self.htn_orchestrator and
                self.htn_orchestrator.task_queue.empty())

    def _save_skill_tree(self, skill_response, events):
        """Save complete skill tree after successful task completion."""
        logger.info(f"Saving complete skill tree for: {self.top_level_task}")

        info = {
            "task": self.top_level_task,
            "success": True,
            "program_code": skill_response.get("program_code", ""),
            "program_name": skill_response.get("program_name", ""),
            "primitives": list(self.execution_chain),
            "dependencies_resolved": True,
        }

        if "recipe" in skill_response:
            info["recipe"] = skill_response["recipe"]

        self.skill_manager.add_new_skill(info)
        logger.info(f"Skill tree saved with {len(self.execution_chain)} primitives")

        self.execution_chain = []
        self.top_level_task = None
        self.top_level_skill_name = None

    # TODO: Revisit how this is done
    def _initialize_htn_if_needed(self):
        """Lazy initialization of HTN system."""
        if not self._htn_initialized:
            try:
                logger.info("Initializing HTN execution system")
                self.htn_orchestrator = HTNOrchestrator(
                    env=self.env,
                    skill_manager=self.skill_manager,
                    recorder=self.recorder,
                )
                self._htn_initialized = True
                logger.info("HTN system initialized")
            except Exception as e:
                logger.error(f"Failed to initialize HTN: {e}", exc_info=True)
                self._htn_initialized = False

    def step(self):
        if self.action_agent_rollout_num_iter < 0:
            raise ValueError("Agent must be reset before stepping")

        self._initialize_htn_if_needed()

        ai_message = self.action_agent.llm.invoke(self.messages)
        logger.debug("Action Agent LLM response:\n%s", ai_message.content, extra={"llm": True})
        self.conversations.append(
            (self.messages[0].content, self.messages[1].content, ai_message.content)
        )

        parsed_result = None
        try:
            if self.htn_orchestrator:
                response = self.htn_orchestrator.parse_llm_response(ai_message.content)

                if response.get('exec_code') and not response.get('program_code'):
                    logger.info("Executing immediate primitive action")
                    exec_code = response['exec_code']

                    events = self.env.step(code=exec_code, programs=self.skill_manager.programs)

                    success = True
                    exec_error = None
                    for event_type, event_data in events:
                        if event_type == "onError":
                            success = False
                            exec_error = event_data.get("onError", "Unknown error")
                            break

                    if exec_error:
                        parsed_result = f"Execution Error: {exec_error}\nPlease fix the code."
                    else:
                        parsed_result = {
                            "program_code": "",
                            "program_name": "",
                            "exec_code": exec_code
                        }
                        self.recorder.record(events, self.task)
                        self.last_events = copy.deepcopy(events) if events else []

                elif response.get('program_code'):
                    is_valid, error, function_calls = self.htn_orchestrator.validate_skill_code(
                        response['program_code'],
                        response['program_name']
                    )

                    if not is_valid:
                        logger.error(f"Skill validation failed: {error}")
                        parsed_result = f"Validation Error: {error}\nPlease fix your code to only use available primitives and skills."
                    else:
                        logger.info(f"Skill '{response['program_name']}' validated successfully")

                        if self.top_level_skill_name is None:
                            self.top_level_skill_name = response['program_name']

                        tasks_queued = self.htn_orchestrator.queue_tasks_from_skill(
                            response['program_code'],
                            response['program_name']
                        )

                        success, events, exec_error = self.htn_orchestrator.execute_queued_tasks(max_steps=100)

                        if hasattr(self.htn_orchestrator, 'last_primitives_used') and self.htn_orchestrator.last_primitives_used:
                            self.execution_chain.extend(self.htn_orchestrator.last_primitives_used)
                            logger.debug(f"Execution chain now has {len(self.execution_chain)} primitives")

                        if isinstance(exec_error, dict) and exec_error.get("type") == "missing_prereq":
                            missing_items = exec_error.get("items", [])
                            logger.warning(f"Missing prerequisites detected: {missing_items}")

                            unresolved = self.htn_orchestrator.schedule_missing_prereqs(missing_items)

                            if unresolved:
                                logger.info(f"Requesting new skill for unresolved prerequisite: {unresolved[0]}")
                                new_task_msg = self._request_skill_for_prereq(unresolved[0])
                                parsed_result = f"Missing prerequisite: {unresolved[0]}. Generating skill to obtain it..."
                            else:
                                logger.info("All prerequisites scheduled — will continue in next step")
                                parsed_result = f"Prerequisites scheduled. Continue execution in next step."

                        elif exec_error:
                            parsed_result = f"Execution Error: {exec_error}\nPlease fix the code."
                        else:
                            parsed_result = {
                                "program_code": response['program_code'],
                                "program_name": response['program_name'],
                                "exec_code": ""
                            }
                            if "recipe" in response:
                                parsed_result["recipe"] = response["recipe"]
                            self.recorder.record(events, self.task)
                            self.last_events = copy.deepcopy(events) if events else []

                            if self._is_top_level_task_complete():
                                logger.info("Top-level task complete — saving skill tree")
                                self._save_skill_tree(response, events)
                else:
                    raise ValueError("Response must contain either 'program_code' or 'exec_code'")
            else:
                raise ValueError("HTN system not initialized")

        except ValueError as e:
            error_msg = str(e)
            logger.warning(f"HTN processing error: {error_msg}")

            if "JSON" in error_msg or "field" in error_msg:
                parsed_result = f"Format Error: {error_msg}\nPlease provide valid JSON with program_code and program_name fields."
            else:
                logger.warning("Falling back to traditional code parsing")
                try:
                    parsed_result = self.action_agent.process_ai_message(message=ai_message)
                except Exception as fallback_error:
                    parsed_result = f"Error: {error_msg}\nFallback parsing also failed: {fallback_error}"

        except Exception as e:
            logger.error(f"Unexpected error in HTN system: {e}", exc_info=True)
            try:
                parsed_result = self.action_agent.process_ai_message(message=ai_message)
            except Exception as fallback_error:
                parsed_result = f"System Error: {e}\nFallback also failed: {fallback_error}"

        if isinstance(parsed_result, dict):
            if parsed_result.get("exec_code") == "" and self.last_events:
                events = self.last_events
            else:
                code = parsed_result["program_code"] + "\n" + parsed_result["exec_code"]
                events = self.env.step(
                    code,
                    programs=self.skill_manager.programs,
                )
                self.recorder.record(events, self.task)

            if events and len(events) > 0:
                self.action_agent.update_chest_memory(events[-1][1]["nearbyChests"])
            success, critique = self.critic_agent.check_task_success(
                events=events,
                task=self.task,
                context=self.context,
                chest_observation=self.action_agent.render_chest_observation(),
                max_retries=5,
            )

            if self.reset_placed_if_failed and not success and events and len(events) > 0:
                blocks = []
                positions = []
                for event_type, event in events:
                    if event_type == "onSave" and event["onSave"].endswith("_placed"):
                        block = event["onSave"].split("_placed")[0]
                        position = event["status"]["position"]
                        blocks.append(block)
                        positions.append(position)
                new_events = self.env.step(
                    f"await givePlacedItemBack(bot, {U.json_dumps(blocks)}, {U.json_dumps(positions)})",
                    programs=self.skill_manager.programs,
                )
                if new_events and len(new_events) > 0:
                    events[-1][1]["inventory"] = new_events[-1][1]["inventory"]
                    events[-1][1]["voxels"] = new_events[-1][1]["voxels"]

            new_skills = self.skill_manager.retrieve_skills(
                query=self.context
                + "\n\n"
                + self.action_agent.summarize_chatlog(events)
            )
            system_message = self.action_agent.render_system_message(skills=new_skills)
            human_message = self.action_agent.render_human_message(
                events=events,
                code=parsed_result["program_code"],
                task=self.task,
                context=self.context,
                critique=critique,
            )
            self.last_events = copy.deepcopy(events)
            self.messages = [system_message, human_message]
        else:
            assert isinstance(parsed_result, str)
            self.recorder.record([], self.task)
            logger.warning(f"Step failed (string result): {parsed_result}")
            success = False

            failed_code = ""
            if self.conversations:
                last_ai_content = self.conversations[-1][2]
                try:
                    if "```json" in last_ai_content:
                        json_start = last_ai_content.find("```json") + 7
                        json_end = last_ai_content.find("```", json_start)
                        json_str = last_ai_content[json_start:json_end].strip()
                        parsed = json.loads(json_str)
                        failed_code = parsed.get("program_code", "")
                except Exception:
                    failed_code = last_ai_content

            new_skills = self.skill_manager.retrieve_skills(query=self.context)
            system_message = self.action_agent.render_system_message(skills=new_skills)
            error_human_message = self.action_agent.render_human_message(
                events=[],
                code=failed_code,
                task=self.task,
                context=self.context,
                critique=parsed_result,
                observation_override=self.last_events[-1][1]
                if self.last_events and len(self.last_events) > 0
                else None,
            )
            self.messages = [system_message, error_human_message]

        assert len(self.messages) == 2
        self.action_agent_rollout_num_iter += 1
        done = (
            self.action_agent_rollout_num_iter >= self.action_agent_task_max_retries
            or success
        )
        info = {
            "task": self.task,
            "success": success,
            "conversations": self.conversations,
        }
        if success:
            assert (
                "program_code" in parsed_result and "program_name" in parsed_result
            ), "program and program_name must be returned when success"
            info["program_code"] = parsed_result["program_code"]
            info["program_name"] = parsed_result["program_name"]

            if self.htn_orchestrator and self.htn_orchestrator.last_primitives_used:
                info["primitives"] = self.htn_orchestrator.last_primitives_used
                logger.debug(f"Adding {len(info['primitives'])} primitives to skill info")

            if "recipe" in parsed_result and parsed_result["recipe"]:
                info["recipe"] = parsed_result["recipe"]
                logger.debug("Adding recipe metadata to skill info")
        else:
            logger.debug("Action Agent human message (retry):\n%s", self.messages[-1].content, extra={"llm": True})

        return self.messages, 0, done, info

    def rollout(self, *, task, context, reset_env=True):
        self.reset(task=task, context=context, reset_env=reset_env)
        while True:
            messages, reward, done, info = self.step()
            if done:
                break
        return messages, reward, done, info

    def learn(self, reset_env=True):
        if self.resume:
            self.env.reset(
                options={
                    "mode": "soft",
                    "wait_ticks": self.env_wait_ticks,
                }
            )
        else:
            self.env.reset(
                options={
                    "mode": "hard",
                    "wait_ticks": self.env_wait_ticks,
                }
            )
            self.resume = True
        self.last_events = self.env.step("")

        while True:
            if self.recorder.iteration > self.max_iterations:
                logger.info("Iteration limit reached")
                break
            task, context = self.curriculum_agent.propose_next_task(
                events=self.last_events,
                chest_observation=self.action_agent.render_chest_observation(),
                max_retries=5,
            )
            logger.info(f"Starting task '{task}' (max {self.action_agent_task_max_retries} retries)")
            try:
                messages, reward, done, info = self.rollout(
                    task=task,
                    context=context,
                    reset_env=reset_env,
                )
            except Exception as e:
                time.sleep(3)
                info = {
                    "task": task,
                    "success": False,
                }
                if self.last_events and len(self.last_events) > 0:
                    self.last_events = self.env.reset(
                        options={
                            "mode": "hard",
                            "wait_ticks": self.env_wait_ticks,
                            "inventory": self.last_events[-1][1]["inventory"],
                            "equipment": self.last_events[-1][1]["status"]["equipment"],
                            "position": self.last_events[-1][1]["status"]["position"],
                        }
                    )
                else:
                    logger.warning("No previous state to restore — performing clean reset")
                    self.last_events = self.env.reset(
                        options={
                            "mode": "hard",
                            "wait_ticks": self.env_wait_ticks,
                        }
                    )
                logger.error(f"Rollout terminated due to error: {e}", exc_info=True)

            if info["success"]:
                self.skill_manager.add_new_skill(info)

            self.curriculum_agent.update_exploration_progress(info)
            logger.info(f"Completed tasks: {', '.join(self.curriculum_agent.completed_tasks) or 'none'}")
            logger.info(f"Failed tasks: {', '.join(self.curriculum_agent.failed_tasks) or 'none'}")

        return {
            "completed_tasks": self.curriculum_agent.completed_tasks,
            "failed_tasks": self.curriculum_agent.failed_tasks,
            "skills": self.skill_manager.skills,
        }

    def decompose_task(self, task):
        if not self.last_events:
            self.last_events = self.env.reset(
                options={
                    "mode": "hard",
                    "wait_ticks": self.env_wait_ticks,
                }
            )
        return self.curriculum_agent.decompose_task(task, self.last_events)

    def inference(self, task=None, sub_goals=[], reset_mode="hard", reset_env=True):
        if not task and not sub_goals:
            raise ValueError("Either task or sub_goals must be provided")
        if not sub_goals:
            sub_goals = self.decompose_task(task)
        self.env.reset(
            options={
                "mode": reset_mode,
                "wait_ticks": self.env_wait_ticks,
            }
        )
        self.curriculum_agent.completed_tasks = []
        self.curriculum_agent.failed_tasks = []
        self.last_events = self.env.step("")
        while self.curriculum_agent.progress < len(sub_goals):
            next_task = sub_goals[self.curriculum_agent.progress]
            context = self.curriculum_agent.get_task_context(next_task)
            logger.info(f"Starting task '{next_task}' (max {self.action_agent_task_max_retries} retries)")
            messages, reward, done, info = self.rollout(
                task=next_task,
                context=context,
                reset_env=reset_env,
            )
            self.curriculum_agent.update_exploration_progress(info)
            logger.info(f"Completed tasks: {', '.join(self.curriculum_agent.completed_tasks) or 'none'}")
            logger.info(f"Failed tasks: {', '.join(self.curriculum_agent.failed_tasks) or 'none'}")
