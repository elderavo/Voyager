import os
from voyager import Voyager
from voyager.config import config

# Disable ChromaDB telemetry to avoid errors
#os.environ["ANONYMIZED_TELEMETRY"] = "False"

# Create Voyager instance — all values come from .env (see .env.example)
voyager = Voyager(
    mc_host=config.MINECRAFT_HOST,
    mc_port=config.MINECRAFT_PORT,
    openai_api_key=config.OPENAI_API_KEY,
    server_port=config.MINEFLAYER_PORT,
    resume=False,
)

# Start the learning process
voyager.learn()
