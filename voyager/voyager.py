import copy
import json
import os
import re
import time
from typing import Dict

import voyager.utils as U
from .env import VoyagerEnv

from .agents import ActionAgent
from .agents import CriticAgent
from .agents import CurriculumAgent
from .agents import SkillManager
from .executor import Executor

# New modular architecture imports
from .task_spec import TaskSpec, TaskType
from .task_classifier import TaskClassifier
from .execution_plan import ExecutionPlan, ExecutionMode
from .execution_router import ExecutionRouter
from .world_state_tracker import WorldStateTracker
from .reset_manager import ResetManager, ResetMode
from voyager.types import ExecutionResult
from voyager.trace import Trace
from .task_executors import (
    PrimitiveExecutor,
    SkillExecutor,
    ActionLLMExecutor,
)


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
        :param mc_port: minecraft in-game port
        :param azure_login: minecraft login config
        :param server_port: mineflayer port
        :param openai_api_key: openai api key
        :param env_wait_ticks: how many ticks at the end each step will wait, if you found some chat log missing,
        you should increase this value
        :param env_step_timeout: how many seconds to wait for each step, if the code execution exceeds this time,
        python side will terminate the connection and need to be resumed
        :param reset_placed_if_failed: whether to reset placed blocks if failed, useful for building task
        :param action_agent_model: action agent model name
        :param action_agent_temperature: action agent temperature
        :param action_agent_task_max_retries: how many times to retry if failed
        :param curriculum_agent_model: curriculum agent model name
        :param curriculum_agent_temperature: curriculum agent temperature
        :param curriculum_agent_qa_model: curriculum agent qa model name
        :param curriculum_agent_qa_temperature: curriculum agent qa temperature
        :param curriculum_agent_warm_up: info will show in curriculum human message
        if completed task larger than the value in dict, available keys are:
        {
            "context": int,
            "biome": int,
            "time": int,
            "other_blocks": int,
            "nearby_entities": int,
            "health": int,
            "hunger": int,
            "position": int,
            "equipment": int,
            "chests": int,
            "optional_inventory_items": int,
        }
        :param curriculum_agent_core_inventory_items: only show these items in inventory before optional_inventory_items
        reached in warm up
        :param curriculum_agent_mode: "auto" for automatic curriculum, "manual" for human curriculum
        :param critic_agent_model: critic agent model name
        :param critic_agent_temperature: critic agent temperature
        :param critic_agent_mode: "auto" for automatic critic ,"manual" for human critic
        :param skill_manager_model: skill manager model name
        :param skill_manager_temperature: skill manager temperature
        :param skill_manager_retrieval_top_k: how many skills to retrieve for each task
        :param openai_api_timeout: how many seconds to wait for openai api
        :param ckpt_dir: checkpoint dir
        :param skill_library_dir: skill library dir
        :param resume: whether to resume from checkpoint
        """
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

        # init Executor for direct primitive execution and recursive skill discovery
        self.executor = Executor(
            env=self.env,
            skill_manager=self.skill_manager,
            ckpt_dir=skill_library_dir if skill_library_dir else ckpt_dir,
            max_recursion_depth=5,
        )

        # init variables for rollout
        self.action_agent_rollout_num_iter = -1
        self.task = None
        self.context = ""
        self.messages = None
        self.conversations = []
        self.last_events = None

        # Initialize new modular architecture components
        self.task_classifier = TaskClassifier()
        self.execution_router = ExecutionRouter(skill_manager=self.skill_manager)
        self.world_state = WorldStateTracker()
        self.reset_manager = ResetManager(env=self.env, env_wait_ticks=env_wait_ticks)

        # Initialize task executors
        self.primitive_executor = PrimitiveExecutor(executor=self.executor)
        self.skill_executor = SkillExecutor(executor=self.executor)
        self.action_llm_executor = ActionLLMExecutor(
            voyager_instance=self,
            max_retries=action_agent_task_max_retries
        )

    def reset(self, task, context="", reset_env=True):
        self.action_agent_rollout_num_iter = 0
        self.task = task
        self.context = context
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
        # step to peek an observation
        events = self.env.step(
            "bot.chat(`/time set ${getNextTime()}`);\n"
            + f"bot.chat('/difficulty {difficulty}');"
        )
        skills = self.skill_manager.retrieve_skills(query=self.context)
        print(
            f"\033[33mRender Action Agent system message with {len(skills)} skills\033[0m"
        )
        system_message = self.action_agent.render_system_message(skills=skills)
        human_message = self.action_agent.render_human_message(
            events=events, code="", task=self.task, context=context, critique=""
        )
        self.messages = [system_message, human_message]
        print(
            f"\033[32m****Action Agent human message****\n{human_message.content}\033[0m"
        )
        assert len(self.messages) == 2
        self.conversations = []
        return self.messages

    def close(self):
        self.env.close()

    def step(self):
        if self.action_agent_rollout_num_iter < 0:
            raise ValueError("Agent must be reset before stepping")
        ai_message = self.action_agent.llm.invoke(self.messages)
        print(f"\033[34m****Action Agent ai message****\n{ai_message.content}\033[0m")
        self.conversations.append(
            (self.messages[0].content, self.messages[1].content, ai_message.content)
        )
        parsed_result = self.action_agent.process_ai_message(message=ai_message)
        success = False
        if isinstance(parsed_result, dict):
            code = parsed_result["program_code"] + "\n" + parsed_result["exec_code"]
            events = self.env.step(
                code,
                programs=self.skill_manager.programs,
            )
            self.recorder.record(events, self.task)
            self.action_agent.update_chest_memory(events[-1][1]["nearbyChests"])
            success, critique = self.critic_agent.check_task_success(
                events=events,
                task=self.task,
                context=self.context,
                chest_observation=self.action_agent.render_chest_observation(),
                max_retries=5,
            )

            if self.reset_placed_if_failed and not success:
                # revert all the placing event in the last step
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
            print(f"\033[34m{parsed_result} Trying again!\033[0m")
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
            info["is_one_line_primitive"] = parsed_result.get("is_one_line_primitive", False)
        else:
            print(
                f"\033[32m****Action Agent human message****\n{self.messages[-1].content}\033[0m"
            )
        return self.messages, 0, done, info

    def executor_craft(self, item_name: str, task_type: str = "craft") -> Dict:
        """
        Executor-based crafting with quantity support.
        """

        print(f"\033[35m****Executor Mode: Crafting {item_name}****\033[0m")

        try:
            success, events, normalized_name = self.executor.craft_item(item_name, task_type=task_type)

            print(f"[DEBUG] Executor returned success={success}, events count={len(events) if events else 0}")

            # Only store Mineflayer-style events
            if isinstance(events, list) and events and isinstance(events[0], tuple):
                self.last_events = events

            info = {
                "task": f"Craft {item_name}",
                "success": success,
                "executor_mode": True,
            }

            if success:
                skill_name = f"craft{self.executor._to_camel_case(normalized_name)}"
                if skill_name in self.skill_manager.skills:
                    info["program_name"] = skill_name
                    info["program_code"] = self.skill_manager.skills[skill_name]["code"]

            return info

        except Exception as e:
            print(f"\033[31mExecutor crafting error: {e}\033[0m")
            import traceback
            traceback.print_exc()
            return {
                "task": f"Craft {item_name}",
                "success": False,
                "error": str(e),
            }


    def rollout(self, *, task, context, reset_env=True):
        self.reset(task=task, context=context, reset_env=reset_env)
        while True:
            messages, reward, done, info = self.step()
            if done:
                break
        return messages, reward, done, info

    def learn(self, reset_env=True, use_executor=True):
        if self.resume:
            # keep the inventory
            print(f"\033[36m[DEBUG] Resuming with soft reset (keeping inventory)\033[0m")
            self.last_events = self.env.reset(
                options={
                    "mode": "soft",
                    "wait_ticks": self.env_wait_ticks,
                }
            )
        else:
            # clear the inventory - MUST use hard reset with no inventory parameter
            print(f"\033[36m[DEBUG] Starting fresh with HARD reset (clearing inventory)\033[0m")
            self.last_events = self.env.reset(
                options={
                    "mode": "hard",
                    "wait_ticks": self.env_wait_ticks,
                    # Explicitly do NOT pass inventory - let it default to {}
                }
            )
            # After initial hard reset, subsequent resets within the learning loop
            # will preserve inventory between tasks
            self.resume = True

        # Get fresh state after reset
        self.last_events = self.env.step("")
        print(f"\033[36m[DEBUG] Initial inventory after reset: {self.last_events[-1][1].get('inventory', {}) if self.last_events else 'N/A'}\033[0m")

        while True:
            if self.recorder.iteration > self.max_iterations:
                print("Iteration limit reached")
                break
            task, context = self.curriculum_agent.propose_next_task(
                events=self.last_events,
                chest_observation=self.action_agent.render_chest_observation(),
                max_retries=5,
            )
            print(
                f"\033[35mStarting task {task} for at most {self.action_agent_task_max_retries} times\033[0m"
            )

            # Classify task type
            if task.lower().startswith("craft"):
                task_type = "craft"
            else:
                task_type = "unknown"

            # Check if we should use executor mode for this task
            if use_executor and task_type == "craft":
                # Extract item name from task
                match = re.match(r"craft\s+(.+)", task, re.IGNORECASE)
                if match: item_name = match.group(1).strip()

                #item_name = task[6:].strip()  # Remove "Craft " prefix
                print(f"\033[36m[Executor Mode] Crafting: {item_name}\033[0m")
                #print(f"\033[36m[DEBUG] Current inventory before crafting: {self.last_events[-1][1].get('inventory', {}) if self.last_events else 'N/A'}\033[0m")

                try:
                    info = self.executor_craft(item_name, task_type="craft")
                    # Ensure we have valid last_events
                    if not self.last_events:
                        self.last_events = self.env.step("")
                except Exception as e:
                    info = {
                        "task": task,
                        "success": False,
                    }
                    print(f"\033[31m[Executor Mode] Error: {e}\033[0m")
                    import traceback
                    traceback.print_exc()
                    # Get fresh state after error
                    try:
                        self.last_events = self.env.step("")
                    except Exception:
                        pass  # If even this fails, we'll handle it in the next iteration
            else:
                # Use existing Action Agent path
                # No need to reset env between tasks - we already have fresh state
                try:
                    messages, reward, done, info = self.rollout(
                        task=task,
                        context=context,
                        reset_env=False,  # State is already fresh from previous task
                    )
                except Exception as e:
                    info = {
                        "task": task,
                        "success": False,
                    }
                    # use red color background to print the error
                    print("Your last round rollout terminated due to error:")
                    print(f"\033[41m{e}\033[0m")
                    # Get fresh state after error
                    try:
                        self.last_events = self.env.step("")
                    except Exception:
                        pass  # If even this fails, we'll handle it in the next iteration

            # Soft reset between tasks - no need to restart mineflayer server
            # Just get fresh state with a simple step
            print(f"\033[36m[DEBUG] Getting fresh state after task (soft refresh, no restart)\033[0m")
            self.last_events = self.env.step("")
            #print(f"\033[36m[DEBUG] Inventory after task: {self.last_events[-1][1].get('inventory', {}) if self.last_events else 'N/A'}\033[0m")

            if info["success"]:
                # Only save as a new skill if it's not a one-line primitive
                if not info.get("is_one_line_primitive", False):
                    self.skill_manager.add_new_skill(info)
                else:
                    print(f"\033[33mSkipping skill save for one-line primitive: {info.get('program_name', 'unknown')}\033[0m")

            self.curriculum_agent.update_exploration_progress(info)
            print(
                f"\033[35mCompleted tasks: {', '.join(self.curriculum_agent.completed_tasks)}\033[0m"
            )
            print(
                f"\033[35mFailed tasks: {', '.join(self.curriculum_agent.failed_tasks)}\033[0m"
            )

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
            print(
                f"\033[35mStarting task {next_task} for at most {self.action_agent_task_max_retries} times\033[0m"
            )
            messages, reward, done, info = self.rollout(
                task=next_task,
                context=context,
                reset_env=reset_env,
            )
            self.curriculum_agent.update_exploration_progress(info)
            print(
                f"\033[35mCompleted tasks: {', '.join(self.curriculum_agent.completed_tasks)}\033[0m"
            )
            print(
                f"\033[35mFailed tasks: {', '.join(self.curriculum_agent.failed_tasks)}\033[0m"
            )

    def learn_v2(self, reset_env=True):
        """
        Refactored learn loop using modular architecture.

        This is the new clean implementation that:
        1. Uses TaskClassifier for parsing
        2. Uses ExecutionRouter for routing decisions
        3. Uses specialized executors for execution
        4. Uses WorldStateTracker for state management
        5. Uses ResetManager for reset semantics

        The loop is now a thin orchestrator with no business logic.
        """
        print("\033[36m=== Using Refactored Learn V2 Architecture ===\033[0m")

        # 1. Initial reset
        events = self.reset_manager.apply_initial_reset(
            world_state=self.world_state,
            resume=self.resume
        )

        # After initial hard reset, preserve inventory between tasks
        if not self.resume:
            self.resume = True

        # Get fresh state
        events = self.reset_manager.soft_refresh(self.world_state)
        print(f"\033[36m[V2] Initial inventory: {self.world_state.get_inventory()}\033[0m")

        # 2. Main learning loop
        while True:
            if self.recorder.iteration > self.max_iterations:
                print("Iteration limit reached")
                break

            # a. Get next task from curriculum
            raw_task, context = self.curriculum_agent.propose_next_task(
                events=self.world_state.get_last_events(),
                chest_observation=self.action_agent.render_chest_observation(),
                max_retries=5,
            )
            print(f"\033[35m[V2] Starting task: {raw_task}\033[0m")

            # b. Classify task
            task_spec = self.task_classifier.classify(
                raw_task=raw_task,
                context=context,
                world_state=self.world_state
            )
            print(f"\033[36m[V2] Classified as: {task_spec}\033[0m")

            # c. Route to execution mode
            execution_plan = self.execution_router.route(
                task_spec=task_spec,
                world_state=self.world_state
            )
            print(f"\033[36m[V2] Execution plan: {execution_plan}\033[0m")

            # d. Execute via appropriate executor
            try:
                result = self._execute_task(task_spec, execution_plan)
            except Exception as e:
                print(f"\033[31m[V2] Execution error: {e}\033[0m")
                import traceback
                traceback.print_exc()
                result = ExecutionResult(
                    success=False,
                    trace=Trace.from_events([]),
                    errors=[str(e)]
                )

            # e. Update world state from result
            if result.events:
                self.world_state.update_from_events(result.events)
                self.last_events = result.events  # For backward compatibility

            # f. Update curriculum
            info = {
                "task": raw_task,
                "success": result.success,
                "conversations": result.conversations,
            }
            if result.program_code and result.program_name:
                info["program_code"] = result.program_code
                info["program_name"] = result.program_name
                info["is_one_line_primitive"] = result.is_one_line_primitive

            self.curriculum_agent.update_exploration_progress(info)

            # g. Persist all synthesized skills
            if result.success and result.new_skills and execution_plan.save_as_skill:
                for skill_name, skill_code in result.new_skills:
                    skill_info = {
                        "task": raw_task,
                        "program_name": skill_name,
                        "program_code": skill_code,
                        "is_one_line_primitive": False,  # Synthesized skills are never primitives
                    }
                    self.skill_manager.add_new_skill(skill_info)
                    print(f"\033[32m[V2] Saved skill: {skill_name}\033[0m")

            # h. Soft refresh for next iteration
            self.reset_manager.soft_refresh(self.world_state, result)

            print(f"\033[35m[V2] Completed: {', '.join(self.curriculum_agent.completed_tasks)}\033[0m")
            print(f"\033[35m[V2] Failed: {', '.join(self.curriculum_agent.failed_tasks)}\033[0m")

        # 3. Return summary
        return {
            "completed_tasks": self.curriculum_agent.completed_tasks,
            "failed_tasks": self.curriculum_agent.failed_tasks,
            "skills": self.skill_manager.skills,
        }

    def _execute_task(self, task_spec: TaskSpec, plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute a task using the appropriate executor.

        This method contains NO business logic - just routing to executors.

        Args:
            task_spec: Classified task specification
            plan: Execution plan from router

        Returns:
            ExecutionResult
        """
        if plan.mode == ExecutionMode.EXISTING_SKILL:
            print(f"\033[36m[V2] Using existing skill: {plan.skill_name}\033[0m")
            return self.skill_executor.execute(task_spec, plan, self.world_state)

        elif plan.mode == ExecutionMode.EXECUTOR_PRIMITIVE:
            print(f"\033[36m[V2] Using primitive executor\033[0m")
            return self.primitive_executor.execute(task_spec, plan, self.world_state)

        elif plan.mode == ExecutionMode.ACTION_LLM:
            print(f"\033[36m[V2] Using Action LLM executor\033[0m")
            return self.action_llm_executor.execute(task_spec, plan, self.world_state)

        elif plan.mode == ExecutionMode.HTN_PLAN:
            print(f"\033[33m[V2] HTN planning not yet implemented, falling back to LLM\033[0m")
            return self.action_llm_executor.execute(task_spec, plan, self.world_state)

        else:
            raise ValueError(f"Unknown execution mode: {plan.mode}")
