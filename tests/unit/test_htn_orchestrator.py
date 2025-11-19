import sys
import types

# Stub heavy dependencies so voyager import works without external packages
requests_stub = types.SimpleNamespace(exceptions=types.SimpleNamespace(ConnectionError=Exception))
sys.modules.setdefault("requests", requests_stub)

gym_stub = types.SimpleNamespace(Env=object, core=types.SimpleNamespace(ObsType=object))
sys.modules.setdefault("gymnasium", gym_stub)
sys.modules.setdefault("gymnasium.core", gym_stub.core)

# Stub environment control dependencies
sys.modules.setdefault("minecraft_launcher_lib", types.SimpleNamespace())
sys.modules.setdefault("psutil", types.SimpleNamespace())

javascript_module = types.ModuleType("javascript")
def _stub_require(*args, **kwargs):
    return types.SimpleNamespace(default=types.SimpleNamespace())
javascript_module.require = _stub_require
sys.modules.setdefault("javascript", javascript_module)
sys.modules.setdefault("javascript.proxy", types.SimpleNamespace(Proxy=object))

# Stub langchain dependencies used at import time
class _DummyChatOpenAI:
    def __init__(self, *args, **kwargs):
        pass

class _DummyOpenAIEmbeddings:
    def __init__(self, *args, **kwargs):
        pass

class _DummySystemMessagePromptTemplate:
    def __init__(self, template=None):
        self.template = template

    @classmethod
    def from_template(cls, template):
        return cls(template)

    def format(self, **kwargs):
        return f"formatted:{self.template}"

class _DummyMessage:
    pass

langchain_core_prompts = types.SimpleNamespace(SystemMessagePromptTemplate=_DummySystemMessagePromptTemplate)
langchain_core_messages = types.SimpleNamespace(AIMessage=_DummyMessage, HumanMessage=_DummyMessage, SystemMessage=_DummyMessage)

sys.modules.setdefault(
    "langchain_openai",
    types.SimpleNamespace(ChatOpenAI=_DummyChatOpenAI, OpenAIEmbeddings=_DummyOpenAIEmbeddings),
)
sys.modules.setdefault("langchain_core.prompts", langchain_core_prompts)
sys.modules.setdefault("langchain_core.messages", langchain_core_messages)

# Stub community vector store
sys.modules.setdefault("langchain_community", types.SimpleNamespace())
sys.modules.setdefault("langchain_community.vectorstores", types.SimpleNamespace(Chroma=object))

from voyager.htn.orchestrator import HTNOrchestrator
from voyager.agents.task_queue import Task


class DummyEnv:
    def __init__(self, events_sequence):
        self.events_sequence = events_sequence
        self.calls = 0

    def step(self, code=None, programs=None):
        # Return the next event sequence or the last one if exhausted
        if self.calls < len(self.events_sequence):
            events = self.events_sequence[self.calls]
        else:
            events = self.events_sequence[-1]
        self.calls += 1
        return events


class DummySkillManager:
    def __init__(self, skills=None):
        self.skills = skills or {}
        self.programs = {}

    def add_skill(self, name, code, output_item=None):
        self.skills[name] = {
            "code": code,
            "recipe": {"output": output_item} if output_item else None,
        }


def test_parse_missing_items_handles_common_error_strings():
    orchestrator = HTNOrchestrator(env=None, skill_manager=DummySkillManager())

    complex_error = "I cannot make wooden_pickaxe because I need: stick, oak_planks"
    assert orchestrator._parse_missing_items(complex_error) == ["stick", "oak_planks"]

    short_error = "MissingIngredient: oak_planks"
    assert orchestrator._parse_missing_items(short_error) == ["oak_planks"]

    unrelated_error = "Something else failed"
    assert orchestrator._parse_missing_items(unrelated_error) == []


def test_check_execution_success_returns_missing_prereq_dict():
    env_events = [[
        ("onError", {"onError": "I cannot make wooden_pickaxe because I need: stick, oak_planks"})
    ]]
    orchestrator = HTNOrchestrator(env=None, skill_manager=DummySkillManager())

    success, error = orchestrator._check_execution_success(env_events[0])
    assert success is False
    assert error == {"type": "missing_prereq", "items": ["stick", "oak_planks"]}


def test_schedule_missing_prereqs_queues_known_skills_and_returns_unresolved():
    skill_manager = DummySkillManager()
    skill_manager.add_skill(
        name="makeStick",
        code="async function makeStick(bot) { await craftItem(bot, 'stick', 1); }",
        output_item="stick",
    )
    orchestrator = HTNOrchestrator(env=None, skill_manager=skill_manager)

    # Stub analyzer and decomposition to avoid full JS parsing and recursion
    orchestrator.analyzer = types.SimpleNamespace(
        extract_function_calls_with_args=lambda code: [
            {"function": "craftItem", "args": ["bot", "'stick'", "1"], "line": 1}
        ]
    )
    orchestrator.decompose_skill_to_primitives = lambda code, name, known_skills=None: [
        Task(
            action="primitive",
            payload={"function": "craftItem", "args": ["bot", "'stick'", "1"], "skill": name, "line": 1},
            parent=name,
        )
    ]

    unresolved = orchestrator.schedule_missing_prereqs(["stick", "oak_planks"])

    # Only oak_planks should remain unresolved
    assert unresolved == ["oak_planks"]

    # Queue should have tasks for the known skill
    assert orchestrator.task_queue.size() > 0
    next_task = orchestrator.task_queue.pop()
    assert isinstance(next_task, Task)
    assert next_task.payload["function"] == "craftItem"


def test_execute_queued_tasks_requeues_on_missing_prereq():
    missing_error_events = [
        [("onError", {"onError": "I cannot make wooden_pickaxe because I need: stick"})]
    ]
    env = DummyEnv(missing_error_events)
    orchestrator = HTNOrchestrator(env=env, skill_manager=DummySkillManager())

    # Preload queue with a single primitive task
    orchestrator.task_queue.push(
        Task(
            action="primitive",
            payload={"function": "craftItem", "args": ["bot", "'wooden_pickaxe'", "1"], "skill": "test", "line": 1},
            parent="test",
        )
    )

    success, events, error = orchestrator.execute_queued_tasks(max_steps=1)

    assert success is False
    assert isinstance(error, dict)
    assert error.get("type") == "missing_prereq"
    # Task should have been requeued for retry
    assert orchestrator.task_queue.size() == 1
    assert orchestrator.last_primitives_used == []
