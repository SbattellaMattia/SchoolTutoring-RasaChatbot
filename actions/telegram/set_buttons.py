import requests
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_ACCESS_TOKEN")

# Define the commands
commands = [
    {"command": "start", "description": "🚀 Avvia il bot tutoring"},
    {"command": "prenota", "description": "📅 Prenota una lezione"},
    {"command": "materie", "description": "📚 Vedi le materie disponibili"},
    {"command": "tutor", "description": "👨‍🏫 Vedi i tutor disponibili per materia"},
    {"command": "prenotazioni", "description": "📖 Le mie lezioni prenotate"},
    {"command": "restart", "description": "🔄 Nuova conversazione"},
    {"command": "help", "description": "❓ Come funziona il bot"}
]

# Set the commands via Telegram API
url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands"
response = requests.post(url, json={"commands": commands})

if response.status_code == 200:
    print("Commands set successfully!")
else:
    print(f"Failed to set commands: {response.status_code}, {response.text}")
