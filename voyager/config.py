"""
Central configuration. All values come from environment variables.
Copy .env.example to .env and fill in your values.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    # LLM
    OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]  # required — fail fast if missing

    # Minecraft server
    MINECRAFT_HOST: str = os.getenv("MINECRAFT_HOST", "localhost")
    MINECRAFT_PORT: int = int(os.getenv("MINECRAFT_PORT", "25565"))

    # Mineflayer bot server
    MINEFLAYER_PORT: int = int(os.getenv("MINEFLAYER_PORT", "3000"))

    # Paths
    CONTROL_PRIMITIVES_PATH: str = os.getenv(
        "CONTROL_PRIMITIVES_PATH",
        str(Path(__file__).parent / "control_primitives_context"),
    )

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
