import requests
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Define the commands
commands = [
    {"command": "start", "description": "🚩 Avvia la sessione"},
    {"command": "info", "description": "ℹ️ Come posso prenotare?"},
    {"command": "bot_challenge", "description": "🤖 Sto parlando con un bot?"},
    {"command": "security", "description": ""},
    {"command": "ricomincia", "description": "👉🏼 Comincia una nuova sessione"},
]

# Set the commands via Telegram API
url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands"
response = requests.post(url, json={"commands": commands})

if response.status_code == 200:
    print("Commands set successfully!")
else:
    print(f"Failed to set commands: {response.status_code}, {response.text}")
