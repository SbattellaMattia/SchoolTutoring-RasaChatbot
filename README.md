# Comandi

```
.\venv\Scripts\activate
python -m pip install requirements.txt   
``` 
python -m pip perchè altrimenti mi prendeva il pip globale anche nel venv.

Avvio dell'addestramento:
```
rasa train --domain domains
``` 
Per avviare da linea di comando e testare:
```
rasa shell
``` 
In un altro terminale attivare: 
```
rasa run actions
``` 
per le action personalizzate (action_...) oltre quelle normali (utter_...).

# Docker
Pullare e runnare Rasa/Duckling per parsing delle stringhe ad orario. 
```
docker pull rasa/duckling:latest
``` 

