import logging
from typing import Any, Dict, Optional, Text

import aiohttp
from sanic import Blueprint, response
from sanic.request import Request

from rasa.core.channels.telegram import TelegramInput

logger = logging.getLogger(__name__)


class TelegramMetadataInput(TelegramInput):
    """Telegram channel che passa a Rasa anche nome/cognome/username come metadata
    e fa ack delle callback_query (inline keyboard) con answerCallbackQuery.
    """

    def get_metadata(self, request: Request) -> Optional[Dict[Text, Any]]:
        data = request.json or {}

        # Per i messaggi normali i dati stanno in message/edited_message
        message = data.get("message") or data.get("edited_message") or {}
        from_user = message.get("from", {})

        # Per le inline keyboard i dati stanno in callback_query
        callback_query = data.get("callback_query") or {}
        cb_from = callback_query.get("from", {}) or from_user

        chat = message.get("chat") or callback_query.get("message", {}).get("chat") or {}

        metadata = {
            "first_name": cb_from.get("first_name"),
            "last_name": cb_from.get("last_name"),
            "username": cb_from.get("username"),
            "chat_id": chat.get("id"),
        }
        logger.debug(f"Telegram metadata: {metadata}")
        return metadata

    async def _answer_callback_query(self, callback_query_id: Text) -> None:
    # Telegram Bot API: answerCallbackQuery
        token = getattr(self, "access_token", None)
        if not token:
            logger.warning("Telegram access_token not set; cannot answerCallbackQuery.")
            return

        url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=5) as resp:
                    if resp.status != 200:
                        txt = await resp.text()
                        logger.warning(
                            "answerCallbackQuery failed: status=%s body=%s",
                            resp.status,
                            txt,
                        )
        except Exception:
            logger.exception("answerCallbackQuery exception")

    def blueprint(self, on_new_message):
        # Blueprint originale (registra /webhooks/telegram/webhook)
        bp = super().blueprint(on_new_message)

        # Middleware che, se l'update è una callback_query,
        # risponde subito con answerCallbackQuery per togliere lo spinner.
        @bp.middleware("request")
        async def _ack_callback_query(request: Request):
            data = request.json or {}
            cb = data.get("callback_query")
            if cb and cb.get("id"):
                await self._answer_callback_query(cb["id"])

        return bp
