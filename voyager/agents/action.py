import re
import time

import voyager.utils as U
from javascript import require
from langchain_openai import ChatOpenAI
from langchain_core.prompts import SystemMessagePromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from voyager.prompts import load_prompt
from voyager.control_primitives_context import load_control_primitives_context
from voyager.agents.agents_common import WorldStateBuilder, ObservationFormatter, PrimitiveDetector

class ActionAgent:
    def __init__(
        self,
        model="gpt-4o-mini",
        temperature=0,
        http_timeout=120,
        ckpt_dir="ckpt",
        resume=False,
        chat_log=True,
        execution_error=True,
    ):
        self.ckpt_dir = ckpt_dir
        self.chat_log = chat_log
        self.execution_error = execution_error

        U.f_mkdir(f"{ckpt_dir}/action")

        if resume:
            print(f"\033[32mLoading Action Agent from {ckpt_dir}/action\033[0m")
            self.chest_memory = U.load_json(f"{ckpt_dir}/action/chest_memory.json")
        else:
            self.chest_memory = {}

        # ---- Modern LangChain + OpenAI client usage ----
        #
        # 1. `ChatOpenAI` now uses `model=` consistently.
        # 2. Timeouts are configured via the HTTP client settings.
        #
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_retries=3,
            # Set timeout via request_timeout parameter
            request_timeout=http_timeout,
        )
        self.model = model

    def update_chest_memory(self, chests):
        for position, chest in chests.items():
            if position in self.chest_memory:
                if isinstance(chest, dict):
                    self.chest_memory[position] = chest
                if chest == "Invalid":
                    print(
                        f"\033[32mAction Agent removing chest {position}: {chest}\033[0m"
                    )
                    self.chest_memory.pop(position)
            else:
                if chest != "Invalid":
                    print(f"\033[32mAction Agent saving chest {position}: {chest}\033[0m")
                    self.chest_memory[position] = chest
        U.dump_json(self.chest_memory, f"{self.ckpt_dir}/action/chest_memory.json")

    def render_chest_observation(self):
        chests = []
        for chest_position, chest in self.chest_memory.items():
            if isinstance(chest, dict) and len(chest) > 0:
                chests.append(f"{chest_position}: {chest}")
        for chest_position, chest in self.chest_memory.items():
            if isinstance(chest, dict) and len(chest) == 0:
                chests.append(f"{chest_position}: Empty")
        for chest_position, chest in self.chest_memory.items():
            if isinstance(chest, str):
                assert chest == "Unknown"
                chests.append(f"{chest_position}: Unknown items inside")
        assert len(chests) == len(self.chest_memory)
        if chests:
            chests = "\n".join(chests)
            return f"Chests:\n{chests}\n\n"
        else:
            return f"Chests: None\n\n"

    def render_system_message(self, skills=[]):
        system_template = load_prompt("action_template")
        # FIXME: Hardcoded control_primitives
        base_skills = [
            "exploreUntil",
            "mineBlock",
            "craftItem",
            "placeItem",
            "smeltItem",
            "killMob",
        ]
        if self.model != "gpt-3.5-turbo":
            base_skills += [
                "useChest",
                "mineflayer",
            ]
        programs = "\n\n".join(load_control_primitives_context(base_skills) + skills)
        response_format = load_prompt("action_response_format")
        system_message_prompt = SystemMessagePromptTemplate.from_template(
            system_template
        )
        system_message = system_message_prompt.format(
            programs=programs, response_format=response_format
        )
        assert isinstance(system_message, SystemMessage)
        return system_message

    def render_human_message(
        self, *, events, code="", task="", context="", critique=""
    ):
        # Extract chat and error messages from events
        chat_messages = []
        error_messages = []
        for i, (event_type, event) in enumerate(events):
            if event_type == "onChat":
                chat_messages.append(event["onChat"])
            elif event_type == "onError":
                error_messages.append(event["onError"])

        # Build WorldState using shared builder
        chest_observation = self.render_chest_observation()
        world = WorldStateBuilder.from_events(
            events=events,
            chest_observation=chest_observation
        )

        # Use shared formatter to create observation string
        observation = ObservationFormatter.format_for_action(
            world=world,
            code=code,
            task=task,
            context=context,
            critique=critique,
            include_errors=self.execution_error,
            include_chat=self.chat_log,
            chat_messages=chat_messages,
            error_messages=error_messages
        )

        return HumanMessage(content=observation)

    def process_ai_message(self, message):
        assert isinstance(message, AIMessage)

        retry = 3
        error = None
        while retry > 0:
            try:
                babel = require("@babel/core")
                babel_generator = require("@babel/generator").default

                code_pattern = re.compile(r"```(?:javascript|js)(.*?)```", re.DOTALL)
                code = "\n".join(code_pattern.findall(message.content))
                parsed = babel.parse(code)
                functions = []
                assert len(list(parsed.program.body)) > 0, "No functions found"
                for i, node in enumerate(parsed.program.body):
                    if node.type != "FunctionDeclaration":
                        continue
                    node_type = (
                        "AsyncFunctionDeclaration"
                        if node["async"]
                        else "FunctionDeclaration"
                    )
                    functions.append(
                        {
                            "name": node.id.name,
                            "type": node_type,
                            "body": babel_generator(node).code,
                            "params": list(node["params"]),
                        }
                    )
                # find the last async function
                main_function = None
                for function in reversed(functions):
                    if function["type"] == "AsyncFunctionDeclaration":
                        main_function = function
                        break
                assert (
                    main_function is not None
                ), "No async function found. Your main function must be async."
                assert (
                    len(main_function["params"]) == 1
                    and main_function["params"][0].name == "bot"
                ), f"Main function {main_function['name']} must take a single argument named 'bot'"
                program_code = "\n\n".join(function["body"] for function in functions)
                exec_code = f"await {main_function['name']}(bot);"

                # Check if this is a one-line primitive call
                is_one_line_primitive = self._is_one_line_primitive(parsed, main_function)

                return {
                    "program_code": program_code,
                    "program_name": main_function["name"],
                    "exec_code": exec_code,
                    "is_one_line_primitive": is_one_line_primitive,
                }
            except Exception as e:
                retry -= 1
                error = e
                time.sleep(1)
        return f"Error parsing action response (before program execution): {error}"

    def _is_one_line_primitive(self, parsed_code, main_function):
        """
        Check if the main function body contains only a single statement that is
        a direct call to a primitive or known skill (not a new skill worth saving).

        Returns True if:
        - The function body has exactly 1 statement
        - That statement is a return/expression statement with an await call
        """
        try:
            babel = require("@babel/core")

            # Find the main function's AST node
            main_func_node = None
            for node in parsed_code.program.body:
                if (node.type == "FunctionDeclaration" and
                    hasattr(node, 'id') and
                    node.id.name == main_function["name"]):
                    main_func_node = node
                    break

            if not main_func_node:
                return False

            # Check the function body
            body_statements = list(main_func_node.body.body)

            # Filter out empty statements or pure comments
            actual_statements = [
                stmt for stmt in body_statements
                if stmt.type not in ["EmptyStatement"]
            ]

            # Must be exactly 1 statement
            if len(actual_statements) != 1:
                return False

            stmt = actual_statements[0]

            # Check if it's a return statement with await, or expression statement with await
            if stmt.type == "ReturnStatement":
                return stmt.argument and stmt.argument.type == "AwaitExpression"
            elif stmt.type == "ExpressionStatement":
                return stmt.expression.type == "AwaitExpression"

            return False

        except Exception as e:
            # If we can't parse it properly, assume it's not a one-liner
            print(f"\033[33mWarning: Could not check if one-line primitive: {e}\033[0m")
            return False

    def summarize_chatlog(self, events):
        def filter_item(message: str):
            craft_pattern = r"I cannot make \w+ because I need: (.*)"
            craft_pattern2 = (
                r"I cannot make \w+ because there is no crafting table nearby"
            )
            mine_pattern = r"I need at least a (.*) to mine \w+!"
            if re.match(craft_pattern, message):
                return re.match(craft_pattern, message).groups()[0]
            elif re.match(craft_pattern2, message):
                return "a nearby crafting table"
            elif re.match(mine_pattern, message):
                return re.match(mine_pattern, message).groups()[0]
            else:
                return ""

        chatlog = set()
        for event_type, event in events:
            if event_type == "onChat":
                item = filter_item(event["onChat"])
                if item:
                    chatlog.add(item)
        return "I also need " + ", ".join(chatlog) + "." if chatlog else ""
