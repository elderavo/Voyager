import os

# Disable ChromaDB telemetry before importing
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import voyager.utils as U
from voyager.utils import get_logger
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.vectorstores import Chroma

from voyager.prompts import load_prompt
from voyager.control_primitives import load_control_primitives

logger = get_logger(__name__)


class SkillManager:
    def __init__(
        self,
        model="gpt-3.5-turbo",
        temperature=0,
        retrieval_top_k=5,
        http_timeout=120,
        ckpt_dir="ckpt",
        resume=False,
    ):
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_retries=3,
            request_timeout=http_timeout,
        )
        U.f_mkdir(f"{ckpt_dir}/skill/code")
        U.f_mkdir(f"{ckpt_dir}/skill/description")
        U.f_mkdir(f"{ckpt_dir}/skill/vectordb")
        self.control_primitives = load_control_primitives()
        if resume:
            logger.info(f"Loading Skill Manager from {ckpt_dir}/skill")
            self.skills = U.load_json(f"{ckpt_dir}/skill/skills.json")
        else:
            self.skills = {}
        self.retrieval_top_k = retrieval_top_k
        self.ckpt_dir = ckpt_dir
        self.vectordb = Chroma(
            collection_name="skill_vectordb",
            embedding_function=OpenAIEmbeddings(),
            persist_directory=f"{ckpt_dir}/skill/vectordb",
        )
        assert self.vectordb._collection.count() == len(self.skills), (
            f"Skill Manager's vectordb is not synced with skills.json.\n"
            f"There are {self.vectordb._collection.count()} skills in vectordb but {len(self.skills)} skills in skills.json.\n"
            f"Did you set resume=False when initializing the manager?\n"
            f"You may need to manually delete the vectordb directory for running from scratch."
        )

    @property
    def programs(self):
        programs = ""
        for skill_name, entry in self.skills.items():
            programs += f"{entry['code']}\n\n"
        for primitives in self.control_primitives:
            programs += f"{primitives}\n\n"
        return programs

    def add_new_skill(self, info):
        if info["task"].startswith("Deposit useless items into the chest at"):
            return
        program_name = info["program_name"]
        program_code = info["program_code"]
        skill_description = self.generate_skill_description(program_name, program_code)
        logger.info(f"Generated description for '{program_name}':\n{skill_description}")

        primitives = info.get("primitives", [])
        if primitives:
            logger.info(f"Storing {len(primitives)} primitives for '{program_name}'")

        recipe = info.get("recipe", None)
        if recipe:
            logger.info(
                f"Storing recipe for '{program_name}': "
                f"output={recipe.get('output', '?')} "
                f"inputs={recipe.get('inputs', [])} "
                f"craftIn={recipe.get('craftIn', '?')}"
            )

        if program_name in self.skills:
            logger.warning(f"Skill '{program_name}' already exists — rewriting")
            self.vectordb._collection.delete(ids=[program_name])
            i = 2
            while f"{program_name}V{i}.js" in os.listdir(f"{self.ckpt_dir}/skill/code"):
                i += 1
            dumped_program_name = f"{program_name}V{i}"
        else:
            dumped_program_name = program_name
        self.vectordb.add_texts(
            texts=[skill_description],
            ids=[program_name],
            metadatas=[{"name": program_name}],
        )
        self.skills[program_name] = {
            "code": program_code,
            "description": skill_description,
            "primitives": primitives,
            "recipe": recipe,
        }
        assert self.vectordb._collection.count() == len(
            self.skills
        ), "vectordb is not synced with skills.json"
        U.dump_text(
            program_code, f"{self.ckpt_dir}/skill/code/{dumped_program_name}.js"
        )
        U.dump_text(
            skill_description,
            f"{self.ckpt_dir}/skill/description/{dumped_program_name}.txt",
        )
        U.dump_json(self.skills, f"{self.ckpt_dir}/skill/skills.json")
        self.vectordb.persist()

    def generate_skill_description(self, program_name, program_code):
        messages = [
            SystemMessage(content=load_prompt("skill")),
            HumanMessage(
                content=program_code
                + "\n\n"
                + f"The main function is `{program_name}`."
            ),
        ]
        logger.debug("LLM request [skill-description] for %s", program_name, extra={"llm": True})
        content = self.llm.invoke(messages).content
        logger.debug("LLM response [skill-description]:\n%s", content, extra={"llm": True})
        skill_description = f"    // {content}"
        return f"async function {program_name}(bot) {{\n{skill_description}\n}}"

    def retrieve_skills(self, query):
        k = min(self.vectordb._collection.count(), self.retrieval_top_k)
        if k == 0:
            return []
        logger.debug(f"Retrieving top {k} skills for query")
        docs_and_scores = self.vectordb.similarity_search_with_score(query, k=k)
        names = [doc.metadata['name'] for doc, _ in docs_and_scores]
        logger.info(f"Retrieved skills: {', '.join(names)}")
        skills = []
        for doc, _ in docs_and_scores:
            skills.append(self.skills[doc.metadata["name"]]["code"])
        return skills
