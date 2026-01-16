FROM rasa/rasa-sdk:3.6.0

USER root

# Installa pandas
RUN pip install --no-cache-dir pandas flask

# Copia le actions
COPY . /app/actions

