# School Tutoring - Rasa Chatbot
Bot Telegram per prenotare ripetizioni scolastiche.

<div align="center">
  <img width="300" height="429" src="https://github.com/user-attachments/assets/a07803ea-ec27-4990-adf8-b3bcb3e0904e" />
</div>


## Prerequisiti
- Docker e Docker Compose
- ngrok (per esporre il bot su internet)
- Token bot Telegram (da @BotFather)

## Setup

### 1. Clona il repository

```bash
git clone https://github.com/SbattellaMattia/SchoolTutoring-RasaChatbot.git
```


### 2. Configura le variabili d'ambiente

Crea il file `.env` nella root del progetto:

```bash
TELEGRAM_ACCESS_TOKEN=il_tuo_token_da_botfather
TELEGRAM_VERIFY=il_tuo_username_bot
TELEGRAM_WEBHOOK_URL=https://your-ngrok-url.ngrok-free.app/webhooks/telegram/webhook
```

**Nota:** L'URL di ngrok verrà generato al passo 3.


### 3. Avvia ngrok

In un terminale separato:

```bash
ngrok http 5005
```

Copia l'URL generato (es. `https://<tuo_url>`) e aggiornalo nel `.env`:

```bash
TELEGRAM_WEBHOOK_URL=https://<tuo_url>/webhooks/telegram/webhook
```


### 4. Train del modello

```bash
docker-compose run rasa train --domain domains
```
Occorre esplicitare il domain poichè diviso in sottofile.

### 6. Avvia il Bot

```bash
docker-compose up -d --build
```

Verifica i log :

```bash
docker-compose logs -f rasa
```
Dovresti vedere una cosa del genere al termine

```bash
rasa           | 2026-01-04 00:25:03 INFO     root  - Rasa server is up and running.
```

## Test su Telegram
Prima di iniziare digita il comando:

```bash
py ./actions/telegram/set_buttons.py
```
Imposterà i comandi rapidi nel pulsante home in basso a sinistra.
Dopodichè cerca il bot su Telegram e prova:

- `ciao` → saluto iniziale
- `vorrei ripetizioni` → avvia il form di prenotazione


## Comandi Utili

```bash
# Riavvia il bot
docker-compose restart rasa

# Retrain del modello
docker-compose run rasa train --force
docker-compose restart rasa

# Stop di tutti i container
docker-compose down -v

# Visualizza i log
docker-compose logs -f
```
