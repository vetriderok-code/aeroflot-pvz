"""Long polling MAX updates (параллельно с Telegram polling)."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from bridge.config import bridge_enabled, max_bot_token
from bridge.max_client import MaxApiError, MaxClient
from bridge.mirror import mirror_max_to_tg
from bridge.store import get_store

logger = logging.getLogger(__name__)


async def run_max_bridge_loop(bot: Bot) -> None:
    if not bridge_enabled():
        logger.info('MAX bridge disabled (MAX_BRIDGE_ENABLED=false)')
        return

    token = max_bot_token()
    if not token:
        logger.warning('MAX bridge enabled but MAX_BOT_TOKEN is empty')
        return

    client = MaxClient(token)
    max_bot_user_id: int | None = None
    try:
        me = await client.get_me()
        max_bot_user_id = int(me.get('user_id') or me.get('id') or 0) or None
        logger.info('MAX bridge started (bot user_id=%s)', max_bot_user_id)
    except MaxApiError as exc:
        logger.error('MAX get_me failed: %s', exc)
        await client.aclose()
        return

    store = get_store()
    marker_raw = store.get_marker('max_updates_marker')
    marker: int | None = int(marker_raw) if marker_raw else None

    try:
        while True:
            try:
                payload = await client.get_updates(
                    marker=marker,
                    timeout=25,
                    types=['message_created', 'message_edited', 'bot_added'],
                )
            except MaxApiError as exc:
                logger.warning('MAX get_updates error: %s', exc)
                await asyncio.sleep(3)
                continue

            updates = payload.get('updates') or []
            new_marker = payload.get('marker')
            if new_marker is not None:
                marker = int(new_marker)
                store.set_marker('max_updates_marker', str(marker))

            for update in updates:
                update_type = update.get('update_type')
                if update_type == 'bot_added':
                    chat_id = update.get('chat_id')
                    logger.info('MAX bot_added chat_id=%s — добавьте в mapping.yaml / .env', chat_id)
                    continue
                try:
                    await mirror_max_to_tg(
                        update,
                        bot=bot,
                        max_client=client,
                        max_bot_user_id=max_bot_user_id,
                    )
                except Exception:
                    logger.exception('MAX update handling failed: %s', update_type)
    finally:
        await client.aclose()
