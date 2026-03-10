"""
Action LLM Task Executor

Executes tasks using the LLM-based Action Agent.
Wraps the existing action agent loop with critic feedback and retries.
"""

from typing import Any
from voyager.types import ExecutionResult
from voyager.trace import Trace
from .base_executor import TaskExecutor
from ..task_spec import TaskSpec


class ActionLLMExecutor(TaskExecutor):
    """
    Executor for LLM-based action generation.

    Wraps the existing Action Agent:
    - LLM code generation
    - Critic feedback loop
    - Retry logic
    - Message reconstruction
    """

    def __init__(
        self,
        voyager_instance: Any,
        max_retries: int = 4
    ):
        """
        Initialize the ActionLLMExecutor.

        Args:
            voyager_instance: Voyager instance with action_agent, critic_agent, env, etc.
            max_retries: Maximum retry attempts
        """
        self.voyager = voyager_instance
        self.max_retries = max_retries

    def execute(self, task_spec: TaskSpec, plan, world_state) -> ExecutionResult:
        """
        Execute a task using the LLM Action Agent.

        This implements the full rollout logic:
        1. Reset action agent state
        2. Loop: LLM -> Execute -> Critic -> Retry
        3. Return result

        Args:
            task_spec: TaskSpec with task details
            plan: ExecutionPlan (not used much here)
            world_state: WorldStateTracker with current state

        Returns:
            ExecutionResult with outcome
        """
        # Build task string and context
        task_str = task_spec.raw_text
        context = task_spec.metadata.get("context", "")

        # Reset action agent for this task
        self._reset_for_task(task_str, context, world_state)

        conversations = []
        success = False
        last_events = []
        program_code = None
        program_name = None

        # Retry loop
        for iteration in range(self.max_retries):
            try:
                # Get LLM response
                ai_message = self.voyager.action_agent.llm.invoke(self.voyager.messages)
                print(f"\033[34m****Action Agent ai message****\n{ai_message.content}\033[0m")

                # Store conversation
                conversations.append((
                    self.voyager.messages[0].content,
                    self.voyager.messages[1].content,
                    ai_message.content
                ))

                # Parse AI response
                parsed_result = self.voyager.action_agent.process_ai_message(message=ai_message)

                if isinstance(parsed_result, dict):
                    # Execute code
                    code = parsed_result["program_code"] + "\n" + parsed_result["exec_code"]
                    events = self.voyager.env.step(
                        code,
                        programs=self.voyager.skill_manager.programs,
                    )

                    # Record events
                    self.voyager.recorder.record(events, task_str)
                    self.voyager.action_agent.update_chest_memory(events[-1][1]["nearbyChests"])

                    # Check success with critic
                    success, critique = self.voyager.critic_agent.check_task_success(
                        events=events,
                        task=task_str,
                        context=context,
                        chest_observation=self.voyager.action_agent.render_chest_observation(),
                        max_retries=5,
                    )

                    last_events = events

                    if success:
                        # Success! Return result
                        program_code = parsed_result["program_code"]
                        program_name = parsed_result["program_name"]
                        break

                    # Not successful, prepare next iteration
                    new_skills = self.voyager.skill_manager.retrieve_skills(
                        query=context + "\n\n" + self.voyager.action_agent.summarize_chatlog(events)
                    )
                    system_message = self.voyager.action_agent.render_system_message(skills=new_skills)
                    human_message = self.voyager.action_agent.render_human_message(
                        events=events,
                        code=parsed_result["program_code"],
                        task=task_str,
                        context=context,
                        critique=critique,
                    )
                    self.voyager.messages = [system_message, human_message]

                else:
                    # Parse error, try again
                    print(f"\033[34m{parsed_result} Trying again!\033[0m")
                    self.voyager.recorder.record([], task_str)

            except Exception as e:
                print(f"\033[31mAction LLM execution error: {e}\033[0m")
                # Continue to next retry
                continue

        return ExecutionResult(
            success=success,
            trace=Trace.from_events(last_events if last_events else []),
            program_code=program_code,
            program_name=program_name,
            is_one_line_primitive=False,  # LLM-generated code is not primitive
            conversations=conversations
        )

    def _reset_for_task(self, task: str, context: str, world_state):
        """
        Reset action agent state for a new task.

        Similar to Voyager.reset() but doesn't reset the environment.
        """
        # Get current events from world state
        events = world_state.get_last_events() if world_state else self.voyager.last_events

        if not events:
            # Get fresh state
            events = self.voyager.env.step("")

        # Retrieve relevant skills
        skills = self.voyager.skill_manager.retrieve_skills(query=context)
        print(f"\033[33mRender Action Agent system message with {len(skills)} skills\033[0m")

        # Build messages
        system_message = self.voyager.action_agent.render_system_message(skills=skills)
        human_message = self.voyager.action_agent.render_human_message(
            events=events,
            code="",
            task=task,
            context=context,
            critique=""
        )

        self.voyager.messages = [system_message, human_message]
        print(f"\033[32m****Action Agent human message****\n{human_message.content}\033[0m")
