from voyager.prompts import load_prompt
from voyager.utils.json_utils import fix_and_parse_json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from voyager.agents.agents_common import WorldStateBuilder, ObservationFormatter, LLMJsonParser


class CriticAgent:
    def __init__(
        self,
        model="gpt-3.5-turbo",
        temperature=0,
        http_timeout=120,
        mode="auto",
    ):
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_retries=3,
            request_timeout=http_timeout,
        )
        assert mode in ["auto", "manual"]
        self.mode = mode

    def render_system_message(self):
        system_message = SystemMessage(content=load_prompt("critic"))
        return system_message

    def render_human_message(self, *, events, task, context, chest_observation):
        # Check for errors first
        for i, (event_type, event) in enumerate(events):
            if event_type == "onError":
                print(f"\033[31mCritic Agent: Error occurs {event['onError']}\033[0m")
                return None

        # Build WorldState using shared builder
        world = WorldStateBuilder.from_events(
            events=events,
            chest_observation=chest_observation
        )

        # Use shared formatter to create observation string
        observation = ObservationFormatter.format_for_critic(
            world=world,
            task=task,
            context=context
        )

        print(f"\033[31m****Critic Agent human message****\n{observation}\033[0m")
        return HumanMessage(content=observation)

    def human_check_task_success(self):
        confirmed = False
        success = False
        critique = ""
        while not confirmed:
            success = input("Success? (y/n)")
            success = success.lower() == "y"
            critique = input("Enter your critique:")
            print(f"Success: {success}\nCritique: {critique}")
            confirmed = input("Confirm? (y/n)") in ["y", ""]
        return success, critique

    def ai_check_task_success(self, messages, max_retries=5):
        if max_retries == 0:
            print(
                "\033[31mFailed to parse Critic Agent response. Consider updating your prompt.\033[0m"
            )
            return False, ""

        if messages[1] is None:
            return False, ""

        critic = self.llm.invoke(messages).content
        print(f"\033[31m****Critic Agent ai message****\n{critic}\033[0m")
        try:
            # Use shared JSON parser
            response = LLMJsonParser.parse_json_or_fail(critic, who="critic")
            assert response["success"] in [True, False]
            if "critique" not in response:
                response["critique"] = ""
            return response["success"], response["critique"]
        except Exception as e:
            print(f"\033[31mError parsing critic response: {e} Trying again!\033[0m")
            return self.ai_check_task_success(
                messages=messages,
                max_retries=max_retries - 1,
            )

    def check_task_success(
        self, *, events, task, context, chest_observation, max_retries=5
    ):
        human_message = self.render_human_message(
            events=events,
            task=task,
            context=context,
            chest_observation=chest_observation,
        )

        messages = [
            self.render_system_message(),
            human_message,
        ]

        if self.mode == "manual":
            return self.human_check_task_success()
        elif self.mode == "auto":
            return self.ai_check_task_success(
                messages=messages, max_retries=max_retries
            )
        else:
            raise ValueError(f"Invalid critic agent mode: {self.mode}")
