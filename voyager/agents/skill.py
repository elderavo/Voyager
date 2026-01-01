import os

# Disable ChromaDB telemetry before importing
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import voyager.utils as U
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.vectorstores import Chroma

from voyager.prompts import load_prompt
from voyager.control_primitives import load_control_primitives


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
        U.f_mkdir(f"{ckpt_dir}/skill/vectordb")
        # programs for env execution
        self.control_primitives = load_control_primitives()
        if resume:
            print(f"\033[33mLoading Skill Manager from {ckpt_dir}/skill\033[0m")
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
        
        # === SHOULD WE SAVE THIS SKILL? ===========================================
        # 1. Skip deposits (not reusable)
        if info["task"].startswith("Deposit useless items into the chest at"):
            return

        program_name = info["program_name"]
        program_code = info["program_code"]

        # 2. Skip saving *only when explicitly marked* as a primitive
        #    Default = False → treat as a full skill unless ActionAgent explicitly says otherwise
        is_primitive = info.get("is_one_line_primitive", False)
        if is_primitive:
            print(f"[DEBUG] Not saving primitive skill: {program_name}")
            return

        # 3. Check if skill already persisted to disk
        code_file_exists = os.path.exists(f"{self.ckpt_dir}/skill/code/{program_name}.js")

        # If skill exists in memory AND on disk with identical code → skip save
        if program_name in self.skills and code_file_exists:
            existing = self.skills[program_name]["code"]
            if existing.strip() == program_code.strip():
                # Already persisted, nothing to do
                return

        # 4. If skill exists but code differs → ONLY rewrite if "force_relearn" flag is set
        force_relearn = info.get("force_relearn", False)
        if program_name in self.skills and code_file_exists and not force_relearn:
            print(f"[DEBUG] Skill {program_name} exists but no force_relearn flag — NOT overwriting.")
            return

        # 5. Determine dumped program name (version if overwriting)
        if program_name in self.skills:
            print(f"[DEBUG] force_relearn=True → rewriting skill {program_name}")
            i = 2
            while f"{program_name}V{i}.js" in os.listdir(f"{self.ckpt_dir}/skill/code"):
                i += 1
            dumped_program_name = f"{program_name}V{i}"
        else:
            dumped_program_name = program_name


        # === TRANSACTIONAL WRITE PHASE ===
        # 1. Write to temporary files first
        code_tmp_path = f"{self.ckpt_dir}/skill/code/{dumped_program_name}.js.tmp"
        json_tmp_path = f"{self.ckpt_dir}/skill/skills.json.tmp"

        try:
            # Write code to temp file
            U.dump_text(program_code, code_tmp_path)

            # Create updated skills dict and write to temp JSON
            # Only store code - no description required
            skills_tmp = dict(self.skills)
            skills_tmp[program_name] = {
                "code": program_code,
            }
            U.dump_json(skills_tmp, json_tmp_path)

            # 2. Update vectordb (if rewriting, delete old entry first)
            # Use program_name as the searchable text for retrieval
            if program_name in self.skills:
                self.vectordb._collection.delete(ids=[program_name])

            self.vectordb.add_texts(
                texts=[program_name],
                ids=[program_name],
                metadatas=[{"name": program_name}],
            )

            # 3. Commit: update in-memory state
            self.skills = skills_tmp

            # 4. Commit: rename temp files to final files
            code_final_path = f"{self.ckpt_dir}/skill/code/{dumped_program_name}.js"
            json_final_path = f"{self.ckpt_dir}/skill/skills.json"

            if os.path.exists(code_final_path):
                os.remove(code_final_path)
            os.rename(code_tmp_path, code_final_path)

            if os.path.exists(json_final_path):
                os.remove(json_final_path)
            os.rename(json_tmp_path, json_final_path)

            # 5. Persist vectordb
            self.vectordb.persist()

            # Verify sync
            assert self.vectordb._collection.count() == len(
                self.skills
            ), "vectordb is not synced with skills.json"

            print(f"\033[32mSkill Manager successfully saved {program_name} (as {dumped_program_name})\033[0m")

        except Exception as e:
            # Rollback: clean up temp files on failure
            print(f"\033[31mSkill Manager failed to save {program_name}: {e}\033[0m")
            for tmp_path in [code_tmp_path, json_tmp_path]:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            raise

    def generate_skill_description(self, program_name, program_code):
        messages = [
            SystemMessage(content=load_prompt("skill")),
            HumanMessage(
                content=program_code
                + "\n\n"
                + f"The main function is `{program_name}`."
            ),
        ]
        skill_description = f"    // { self.llm.invoke(messages).content}"
        return f"async function {program_name}(bot) {{\n{skill_description}\n}}"

    def retrieve_skills(self, query):
        k = min(self.vectordb._collection.count(), self.retrieval_top_k)
        if k == 0:
            return []
        print(f"\033[33mSkill Manager retrieving for {k} skills\033[0m")
        docs_and_scores = self.vectordb.similarity_search_with_score(query, k=k)
        print(
            f"\033[33mSkill Manager retrieved skills: "
            f"{', '.join([doc.metadata['name'] for doc, _ in docs_and_scores])}\033[0m"
        )
        skills = []
        for doc, _ in docs_and_scores:
            skills.append(self.skills[doc.metadata["name"]]["code"])
        return skills
