import copy
import json
import os
import time
from typing import Dict

import voyager.utils as U
from .env import VoyagerEnv

from .agents import ActionAgent
from .agents import CriticAgent
from .agents import CurriculumAgent
from .agents import SkillManager
from .htn import HTNOrchestrator


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
        self.execution_chain = []  # Track all primitives executed for current top-level task
        self.top_level_task = None  # Track original curriculum task
        self.top_level_skill_name = None  # Track original skill name

    def reset(self, task, context="", reset_env=True):
        self.action_agent_rollout_num_iter = 0
        self.task = task
        self.context = context

        # Track top-level task for skill tree building
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

    def _request_skill_for_prereq(self, item_name):
        """
        Request Action LLM to generate a new skill for a missing prerequisite.

        This resets the conversation context to focus on producing the missing item,
        without resetting the Mineflayer environment state.

        Args:
            item_name (str): Name of the missing item

        Returns:
            list: New messages for Action LLM
        """
        print(f"\033[35m[Voyager] Requesting skill generation for: {item_name}\033[0m")

        # Create a focused task for producing this item
        prereq_task = f"Obtain {item_name}"
        prereq_context = (
            f"Generate a skill to obtain {item_name}. "
            f"Use only primitive functions (mineBlock, craftItem, smeltItem, etc.) or known skills. "
            f"This is a prerequisite for a larger task."
        )

        # Reset conversation without resetting environment
        # Use soft reset to keep bot state
        self.task = prereq_task
        self.context = prereq_context
        self.action_agent_rollout_num_iter = 0

        # Get current observation without env reset
        events = self.env.step("bot.chat('Preparing to obtain prerequisite');")

        # Build new messages for Action LLM
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
        print(f"\033[35m[Voyager] New skill request prepared for: {item_name}\033[0m")

        return self.messages

    def _is_top_level_task_complete(self):
        """
        Check if we've completed the original top-level task.

        Returns:
            bool: True if all prerequisites resolved and main task done
        """
        # If queue is empty and we have a top-level task tracked
        return (self.top_level_task is not None and
                self.htn_orchestrator and
                self.htn_orchestrator.task_queue.empty())

    def _save_skill_tree(self, skill_response, events):
        """
        Save complete skill tree after successful task completion.

        This combines:
        - Original skill code from Action LLM
        - All primitives executed (including prerequisites)
        - Recipe metadata for skill matching

        Args:
            skill_response (dict): Parsed LLM response with program_code, program_name
            events (list): Execution events
        """
        print(f"\033[32m[Voyager] Saving complete skill tree for: {self.top_level_task}\033[0m")

        info = {
            "task": self.top_level_task,
            "success": True,
            "program_code": skill_response.get("program_code", ""),
            "program_name": skill_response.get("program_name", ""),
            "primitives": list(self.execution_chain),  # Complete execution trace
            "dependencies_resolved": True,  # Mark as complete HTN skill
        }

        # Add recipe metadata if present
        if "recipe" in skill_response:
            info["recipe"] = skill_response["recipe"]

        # Save to skill manager
        self.skill_manager.add_new_skill(info)

        print(f"\033[32m[Voyager] Skill tree saved with {len(self.execution_chain)} primitives\033[0m")

        # Reset execution tracking
        self.execution_chain = []
        self.top_level_task = None
        self.top_level_skill_name = None

    # TODO: Revisit how this is done
    def _initialize_htn_if_needed(self):
        """Lazy initialization of HTN system."""
        if not self._htn_initialized:
            try:
                print(f"\033[36m[HTN] Initializing HTN execution system...\033[0m")
                self.htn_orchestrator = HTNOrchestrator(
                    env=self.env,
                    skill_manager=self.skill_manager,
                    recorder=self.recorder,
                )
                self._htn_initialized = True
                print(f"\033[36m[HTN] HTN system initialized\033[0m")
            except Exception as e:
                print(f"\033[31m[HTN] Failed to initialize HTN: {e}\033[0m")
                self._htn_initialized = False

    def step(self):
        if self.action_agent_rollout_num_iter < 0:
            raise ValueError("Agent must be reset before stepping")

        # Initialize HTN system if not already done
        self._initialize_htn_if_needed()

        ai_message = self.action_agent.llm.invoke(self.messages)
        print(f"\033[34m****Action Agent ai message****\n{ai_message.content}\033[0m")
        self.conversations.append(
            (self.messages[0].content, self.messages[1].content, ai_message.content)
        )

        # Use new HTN system: parse skill code from LLM, validate, and execute
        parsed_result = None
        try:
            if self.htn_orchestrator:
                # Parse LLM response (expecting program_code and program_name, or exec_code)
                response = self.htn_orchestrator.parse_llm_response(ai_message.content)

                # Check if this is immediate execution mode (exec_code instead of skill)
                if response.get('exec_code') and not response.get('program_code'):
                    # Immediate primitive execution - run directly without skill creation
                    print(f"\033[33m[Voyager] Executing immediate primitive action\033[0m")
                    exec_code = response['exec_code']

                    # Execute the primitive directly
                    events = self.env.step(code=exec_code, programs=self.skill_manager.programs)

                    # Check for errors
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
                        # Success - return result
                        parsed_result = {
                            "program_code": "",
                            "program_name": "",
                            "exec_code": exec_code
                        }
                        self.recorder.record(events, self.task)
                        self.last_events = copy.deepcopy(events) if events else []
                elif response.get('program_code'):
                    # Skill creation mode - validate and decompose
                    # Validate that skill code only uses known functions
                    is_valid, error, function_calls = self.htn_orchestrator.validate_skill_code(
                        response['program_code'],
                        response['program_name']
                    )

                    if not is_valid:
                        # Validation failed - return error to trigger LLM retry
                        print(f"\033[31m[Voyager] Skill validation failed: {error}\033[0m")
                        parsed_result = f"Validation Error: {error}\nPlease fix your code to only use available primitives and skills."
                    else:
                        # Validation passed - decompose and queue
                        print(f"\033[32m[Voyager] Skill validated successfully\033[0m")

                        if self.top_level_skill_name is None:
                            self.top_level_skill_name = response['program_name']

                        # Decompose skill into primitives and queue them
                        tasks_queued = self.htn_orchestrator.queue_tasks_from_skill(
                            response['program_code'],
                            response['program_name']
                        )

                        # Execute queued primitive tasks
                        success, events, exec_error = self.htn_orchestrator.execute_queued_tasks(max_steps=100)

                        if hasattr(self.htn_orchestrator, 'last_primitives_used') and self.htn_orchestrator.last_primitives_used:
                            self.execution_chain.extend(self.htn_orchestrator.last_primitives_used)
                            print(f"\033[36m[Voyager] Execution chain now has {len(self.execution_chain)} primitives\033[0m")

                        # Handle missing prerequisites
                        if isinstance(exec_error, dict) and exec_error.get("type") == "missing_prereq":
                            missing_items = exec_error.get("items", [])
                            print(f"\033[35m[Voyager] Missing prerequisites detected: {missing_items}\033[0m")

                            # Try to schedule known skills for missing items
                            unresolved = self.htn_orchestrator.schedule_missing_prereqs(missing_items)

                            if unresolved:
                                # We don't have skills for these items - request Action LLM to generate new skill
                                print(f"\033[35m[Voyager] Requesting new skill for unresolved prerequisite: {unresolved[0]}\033[0m")

                                # Generate new skill for first unresolved item
                                new_task_msg = self._request_skill_for_prereq(unresolved[0])

                                # Return error to trigger new skill generation in next step
                                parsed_result = f"Missing prerequisite: {unresolved[0]}. Generating skill to obtain it..."
                            else:
                                # All prerequisites resolved with known skills - continue execution
                                print(f"\033[32m[Voyager] All prerequisites scheduled - will continue in next step\033[0m")
                                # Return error to continue execution loop
                                parsed_result = f"Prerequisites scheduled. Continue execution in next step."
                        elif exec_error:
                            # Execution error (not missing prereq) - return to trigger retry
                            parsed_result = f"Execution Error: {exec_error}\nPlease fix the code."
                        else:
                            # Success - return result in expected format
                            parsed_result = {
                                "program_code": response['program_code'],
                                "program_name": response['program_name'],
                                "exec_code": ""  # Code already executed by HTN via queue
                            }
                            # Include recipe metadata if present
                            if "recipe" in response:
                                parsed_result["recipe"] = response["recipe"]
                            self.recorder.record(events, self.task)
                            self.last_events = copy.deepcopy(events) if events else []

                            # Check if top-level task is complete and save skill tree
                            if self._is_top_level_task_complete():
                                print(f"\033[32m[Voyager] Top-level task complete! Saving skill tree...\033[0m")
                                self._save_skill_tree(response, events)
                else:
                    # Neither program_code nor exec_code provided
                    raise ValueError("Response must contain either 'program_code' or 'exec_code'")
            else:
                raise ValueError("HTN system not initialized")

        except ValueError as e:
            # JSON parsing or validation error - try to provide helpful feedback
            error_msg = str(e)
            print(f"\033[33m[Voyager] Error in HTN processing: {error_msg}\033[0m")

            # If it's a parsing/format error, let LLM retry
            if "JSON" in error_msg or "field" in error_msg:
                parsed_result = f"Format Error: {error_msg}\nPlease provide valid JSON with program_code and program_name fields."
            else:
                # Other errors - could be code that doesn't match expected format
                # Fall back to old parsing method
                print(f"\033[33m[Voyager] Falling back to traditional code parsing\033[0m")
                try:
                    parsed_result = self.action_agent.process_ai_message(message=ai_message)
                except Exception as fallback_error:
                    parsed_result = f"Error: {error_msg}\nFallback parsing also failed: {fallback_error}"

        except Exception as e:
            # Unexpected error - fall back to old system
            print(f"\033[31m[Voyager] Unexpected error in HTN system: {e}\033[0m")
            import traceback
            traceback.print_exc()
            try:
                parsed_result = self.action_agent.process_ai_message(message=ai_message)
            except Exception as fallback_error:
                parsed_result = f"System Error: {e}\nFallback also failed: {fallback_error}"

        if isinstance(parsed_result, dict):
            # Check if code was already executed by HTN
            if parsed_result.get("exec_code") == "" and self.last_events:
                # HTN already executed, use cached events
                events = self.last_events
            else:
                # Traditional execution path - execute code in env
                code = parsed_result["program_code"] + "\n" + parsed_result["exec_code"]
                events = self.env.step(
                    code,
                    programs=self.skill_manager.programs,
                )
                self.recorder.record(events, self.task)

            # Only update chest memory if we have events
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
            print(f"\033[34m{parsed_result} Trying again!\033[0m")
            success = False  # String result means failure - need to retry

            # CRITICAL FIX: Add error feedback to conversation so LLM learns from mistakes
            # Extract the code that failed from the last AI message
            failed_code = ""
            if self.conversations:
                # Last conversation is (system, human, ai)
                last_ai_content = self.conversations[-1][2]
                # Try to extract program_code from the JSON response
                try:
                    import json
                    # AI message might have markdown code fence
                    if "```json" in last_ai_content:
                        json_start = last_ai_content.find("```json") + 7
                        json_end = last_ai_content.find("```", json_start)
                        json_str = last_ai_content[json_start:json_end].strip()
                        parsed = json.loads(json_str)
                        failed_code = parsed.get("program_code", "")
                except Exception:
                    # If parsing fails, just use the whole AI message
                    failed_code = last_ai_content

            # Retrieve skills for updated system message (may have changed)
            new_skills = self.skill_manager.retrieve_skills(query=self.context)
            system_message = self.action_agent.render_system_message(skills=new_skills)

            # Create human message with error feedback as critique
            error_human_message = self.action_agent.render_human_message(
                events=[],  # No events since validation failed before execution
                code=failed_code,  # Show the code that failed validation
                task=self.task,
                context=self.context,
                critique=parsed_result,  # The validation error becomes the critique
                observation_override=self.last_events[-1][1]
                if self.last_events and len(self.last_events) > 0
                else None,
            )

            # Update messages for next retry - LLM will now see the error!
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

            # Add primitive decomposition from HTN orchestrator
            if self.htn_orchestrator and self.htn_orchestrator.last_primitives_used:
                info["primitives"] = self.htn_orchestrator.last_primitives_used
                print(f"\033[36m[Voyager] Adding {len(info['primitives'])} primitives to skill info\033[0m")

            # Add recipe metadata from LLM response
            if "recipe" in parsed_result and parsed_result["recipe"]:
                info["recipe"] = parsed_result["recipe"]
                print(f"\033[36m[Voyager] Adding recipe metadata to skill info\033[0m")
        else:
            print(
                f"\033[32m****Action Agent human message****\n{self.messages[-1].content}\033[0m"
            )
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
            # keep the inventory
            self.env.reset(
                options={
                    "mode": "soft",
                    "wait_ticks": self.env_wait_ticks,
                }
            )
        else:
            # clear the inventory
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
            try:
                messages, reward, done, info = self.rollout(
                    task=task,
                    context=context,
                    reset_env=reset_env,
                )
            except Exception as e:
                time.sleep(3)  # wait for mineflayer to exit
                info = {
                    "task": task,
                    "success": False,
                }
                # reset bot status here
                # Check if last_events has data before trying to restore state
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
                    # No previous state to restore, do a clean reset
                    print("\033[33mNo previous state to restore, performing clean reset\033[0m")
                    self.last_events = self.env.reset(
                        options={
                            "mode": "hard",
                            "wait_ticks": self.env_wait_ticks,
                        }
                    )
                # use red color background to print the error
                print("Your last round rollout terminated due to error:")
                print(f"\033[41m{e}\033[0m")

            if info["success"]:
                self.skill_manager.add_new_skill(info)

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
