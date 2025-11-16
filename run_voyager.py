import os
from voyager import Voyager

# Disable ChromaDB telemetry to avoid errors
#os.environ["ANONYMIZED_TELEMETRY"] = "False"

# Configuration for your LAN homelab server
HOMELAB_IP = "10.0.132.101"  # Your homelab Minecraft server IP
MC_PORT = 25565              # Your Minecraft server port (default: 25565)

# Read your OpenAI API key
with open(r"C:\Users\Alex\OneDrive - Naval Postgraduate School\Desktop\openAIKey.txt", "r") as f:
    openai_api_key = f.read().strip()

# Create Voyager instance connected to your homelab
voyager = Voyager(
    mc_host=HOMELAB_IP,      # LAN server IP
    mc_port=MC_PORT, 
    resume=False,    # LAN server port
    openai_api_key=openai_api_key,
    server_port=3000,        # Mineflayer runs locally on port 3000
)

# Start the learning process
voyager.learn()