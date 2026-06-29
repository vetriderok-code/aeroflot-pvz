"""Реакции на обработанные сообщения в Telegram."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ReactionTypeEmoji

logger = logging.getLogger(__name__)

PROCESSED_OK_EMOJI = '👌'


async def mark_message_processed_ok(bot: Bot, *, chat_id: int, message_id: int) -> bool:
    try:
        await bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[ReactionTypeEmoji(emoji=PROCESSED_OK_EMOJI)],
            is_big=False,
        )
        return True
    except TelegramBadRequest as exc:
        logger.warning('Не удалось поставить реакцию msg=%s: %s', message_id, exc)
        return False
    except Exception as exc:
        logger.warning('Реакция msg=%s: %s', message_id, exc)
        return False
