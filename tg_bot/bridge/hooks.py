"""Точки входа для зеркалирования из aiogram handlers."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import Message

from bridge.config import bridge_enabled, max_bot_token
from bridge.max_client import MaxClient
from bridge.mirror import mirror_tg_to_max

logger = logging.getLogger(__name__)

_max_client: MaxClient | None = None


async def _get_max_client() -> MaxClient | None:
    global _max_client
    if not bridge_enabled():
        return None
    token = max_bot_token()
    if not token:
        return None
    if _max_client is None:
        _max_client = MaxClient(token)
    return _max_client


async def bridge_tg_message(message: Message, bot: Bot) -> None:
    client = await _get_max_client()
    if not client:
        return
    try:
        me = await bot.get_me()
        await mirror_tg_to_max(message, bot=bot, max_client=client, tg_bot_id=me.id)
    except Exception:
        logger.exception('bridge_tg_message failed msg=%s', message.message_id)
