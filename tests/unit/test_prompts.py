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
javascript_module.require = lambda *args, **kwargs: types.SimpleNamespace(default=types.SimpleNamespace())
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

sys.modules.setdefault("langchain_openai", types.SimpleNamespace(ChatOpenAI=_DummyChatOpenAI, OpenAIEmbeddings=_DummyOpenAIEmbeddings))
sys.modules.setdefault("langchain_core.prompts", langchain_core_prompts)
sys.modules.setdefault("langchain_core.messages", langchain_core_messages)

# Stub community vector store
sys.modules.setdefault("langchain_community", types.SimpleNamespace())
sys.modules.setdefault("langchain_community.vectorstores", types.SimpleNamespace(Chroma=object))

from voyager.prompts import load_prompt


def test_action_template_includes_exec_code_guidance():
    prompt = load_prompt("action_template")
    assert "exec_code" in prompt, "Action prompt must mention exec_code option"
    assert "program_code" in prompt and "program_name" in prompt
    assert "Use exec_code when the task requires only a direct primitive action." in prompt


def test_action_response_format_enforces_exec_only_output_option():
    prompt = load_prompt("action_response_format")
    assert "exec_code" in prompt
    assert "program_code MUST be empty string" in prompt
    assert "program_name MUST be empty string" in prompt
