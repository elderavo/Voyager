"""
Refactored Voyager Learn Methods

This file contains the new refactored learn_v2() method and supporting functions.
Add these methods to the Voyager class in voyager.py
"""

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
            from voyager.types import ExecutionResult
            from voyager.trace import Trace
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

        # g. Save skill if allowed and successful
        if result.success and execution_plan.save_as_skill:
            if not result.is_one_line_primitive:
                self.skill_manager.add_new_skill(info)
                print(f"\033[32m[V2] Saved skill: {result.program_name}\033[0m")
            else:
                print(f"\033[33m[V2] Skipping skill save for primitive: {result.program_name}\033[0m")

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


def _execute_task(self, task_spec, plan):
    """
    Execute a task using the appropriate executor.

    This method contains NO business logic - just routing to executors.

    Args:
        task_spec: Classified task specification
        plan: Execution plan from router

    Returns:
        ExecutionResult
    """
    from .execution_plan import ExecutionMode

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
