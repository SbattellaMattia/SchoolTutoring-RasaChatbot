import logging
from typing import Text, Dict, Any, Optional

from rasa.core.channels.telegram import TelegramInput
from sanic.request import Request

logger = logging.getLogger(__name__)

class TelegramMetadataInput(TelegramInput):
    """Telegram channel che passa a Rasa anche nome/cognome/username come metadata."""

    def get_metadata(self, request: Request) -> Optional[Dict[Text, Any]]:
        data = request.json
        message = data.get("message") or data.get("edited_message") or {}
        from_user = message.get("from", {})

        metadata = {
            "first_name": from_user.get("first_name"),
            "last_name": from_user.get("last_name"),
            "username": from_user.get("username"),
            "chat_id": message.get("chat", {}).get("id"),
        }
        logger.debug(f"Telegram metadata: {metadata}")
        return metadata
