"""Зеркалирование сообщений TG ↔ MAX."""
from __future__ import annotations

import logging
import re
from uuid import uuid4

from aiogram import Bot
from aiogram.types import Message

from bridge.config import (
    bridge_enabled,
    find_max_channel,
    find_tg_channel,
    load_channels,
    topic_label,
)
from bridge.max_client import MaxApiError, MaxClient
from bridge.store import get_store

logger = logging.getLogger(__name__)

_PREFIX_RE = re.compile(r'^\[(?P<label>[^\]]+)\]\s*', re.MULTILINE)


def _tg_topic_id(message: Message) -> int | None:
    return getattr(message, 'message_thread_id', None)


def _author_name(message: Message) -> str:
    user = message.from_user
    if not user:
        return 'Unknown'
    if user.username:
        return f'@{user.username}'
    parts = [user.first_name or '', user.last_name or '']
    return ' '.join(p for p in parts if p).strip() or str(user.id)


def _format_outgoing_text(message: Message) -> str | None:
    chat_id = message.chat.id
    topic_id = _tg_topic_id(message)
    label = topic_label(chat_id, topic_id)
    author = _author_name(message)
    body = (message.text or message.caption or '').strip()

    lines: list[str] = []
    if label:
        lines.append(f'[{label}]')
    if body:
        lines.append(f'{author}: {body}')
    elif message.photo or message.video or message.document:
        lines.append(f'{author}:')
    else:
        return None
    return '\n'.join(lines)


def _guess_filename(message: Message) -> tuple[str, str]:
    if message.video:
        return 'video.mp4', 'video'
    if message.photo:
        return 'photo.jpg', 'image'
    if message.document:
        name = message.document.file_name or 'file.bin'
        mime = (message.document.mime_type or '').lower()
        if mime.startswith('video/'):
            return name, 'video'
        if mime.startswith('image/'):
            return name, 'image'
        return name, 'file'
    return 'file.bin', 'file'


async def _download_tg_file(bot: Bot, message: Message) -> tuple[bytes, str, str] | None:
    file_id = None
    if message.video:
        file_id = message.video.file_id
    elif message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    if not file_id:
        return None

    filename, kind = _guess_filename(message)
    buf = await bot.download(file_id)
    if buf is None:
        return None
    data = buf.read() if hasattr(buf, 'read') else buf.getvalue()
    return data, filename, kind


async def _build_max_attachments(bot: Bot, message: Message, client: MaxClient) -> list[dict]:
    downloaded = await _download_tg_file(bot, message)
    if not downloaded:
        return []
    data, filename, kind = downloaded
    try:
        if kind == 'video':
            return [await client.upload_video(data, filename)]
        if kind == 'image':
            return [await client.upload_image(data, filename)]
        return [await client.upload_file(data, filename)]
    except MaxApiError as exc:
        logger.warning('MAX upload failed for tg msg=%s: %s', message.message_id, exc)
        return []


def _extract_max_message_id(result: dict | None) -> str | None:
    if not result:
        return None
    message = result.get('message') or result
    for key in ('message_id', 'mid', 'id'):
        value = message.get(key) if isinstance(message, dict) else None
        if value is not None:
            return str(value)
    return None


async def mirror_tg_to_max(message: Message, *, bot: Bot, max_client: MaxClient, tg_bot_id: int) -> None:
    if not bridge_enabled():
        return
    if message.from_user and message.from_user.id == tg_bot_id:
        return

    store = get_store()
    if store.is_known_dst('tg', message.chat.id, message.message_id):
        return

    channel = find_tg_channel(load_channels(), message.chat.id, _tg_topic_id(message))
    if not channel or not channel.max_chat_id:
        return

    text = _format_outgoing_text(message)
    if not text and not (message.photo or message.video or message.document):
        return

    bridge_key = uuid4().hex
    attachments = await _build_max_attachments(bot, message, max_client)
    if not text and attachments:
        text = _format_outgoing_text(message) or f'{_author_name(message)}:'

    try:
        result = await max_client.send_with_retry(
            chat_id=channel.max_chat_id,
            text=text or ' ',
            attachments=attachments or None,
        )
    except MaxApiError as exc:
        logger.exception('TG→MAX failed chat=%s msg=%s: %s', message.chat.id, message.message_id, exc)
        return

    max_msg_id = _extract_max_message_id(result)
    store.save_pair(
        bridge_key=bridge_key,
        src_platform='tg',
        src_chat_id=message.chat.id,
        src_message_id=str(message.message_id),
        dst_platform='max',
        dst_chat_id=channel.max_chat_id,
        dst_message_id=max_msg_id,
    )
    logger.info(
        'TG→MAX %s: tg %s/%s → max %s/%s',
        channel.id,
        message.chat.id,
        message.message_id,
        channel.max_chat_id,
        max_msg_id,
    )


def _parse_max_text(raw: str, channel) -> tuple[int | None, str]:
    text = (raw or '').strip()
    if not text:
        return None, text

    labels = _labels_for_chat(channel.tg_chat_id)
    match = _PREFIX_RE.match(text)
    if match:
        label = match.group('label')
        topic_id = labels.get(label)
        rest = text[match.end():].strip()
        return topic_id, rest
    return None, text


def _labels_for_chat(chat_id: int) -> dict[str, int | None]:
    from bridge.config import load_topic_labels

    mapping = load_topic_labels()
    result: dict[str, int | None] = {}
    for (cid, topic_id), label in mapping.items():
        if cid == chat_id:
            result[label] = topic_id
    return result


def _max_message_body(update: dict) -> str:
    message = update.get('message') or {}
    body = message.get('body') or {}
    if isinstance(body, dict):
        return str(body.get('text') or '')
    return str(body or '')


def _max_message_id(update: dict) -> str | None:
    message = update.get('message') or {}
    for key in ('message_id', 'mid', 'id'):
        if message.get(key) is not None:
            return str(message.get(key))
    if update.get('message_id') is not None:
        return str(update.get('message_id'))
    return None


def _max_chat_id(update: dict) -> int | None:
    message = update.get('message') or {}
    recipient = message.get('recipient') or {}
    for key in ('chat_id', 'chatId'):
        if recipient.get(key) is not None:
            return int(recipient[key])
    if update.get('chat_id') is not None:
        return int(update['chat_id'])
    return None


def _max_sender_id(update: dict) -> int | None:
    message = update.get('message') or {}
    sender = message.get('sender') or message.get('author') or {}
    for key in ('user_id', 'id'):
        if sender.get(key) is not None:
            return int(sender[key])
    return None


def _max_attachments(update: dict) -> list[dict]:
    message = update.get('message') or {}
    body = message.get('body') or {}
    attachments = body.get('attachments') or message.get('attachments') or []
    return attachments if isinstance(attachments, list) else []


async def mirror_max_to_tg(
    update: dict,
    *,
    bot: Bot,
    max_client: MaxClient,
    max_bot_user_id: int | None,
) -> None:
    if not bridge_enabled():
        return
    if update.get('update_type') not in ('message_created', 'message_edited'):
        return

    max_chat_id = _max_chat_id(update)
    max_msg_id = _max_message_id(update)
    if max_chat_id is None or max_msg_id is None:
        return

    store = get_store()
    if store.is_known_dst('max', max_chat_id, max_msg_id):
        return

    sender_id = _max_sender_id(update)
    if max_bot_user_id and sender_id == max_bot_user_id:
        return

    channel = find_max_channel(load_channels(), max_chat_id)
    if not channel:
        return

    raw_text = _max_message_body(update)
    topic_id, text = _parse_max_text(raw_text, channel)
    if not text and not _max_attachments(update):
        return

    bridge_key = uuid4().hex
    kwargs: dict = {'chat_id': channel.tg_chat_id}
    if topic_id is not None:
        kwargs['message_thread_id'] = topic_id

    try:
        sent = await _send_tg_from_max(bot, text, _max_attachments(update), max_client, **kwargs)
    except Exception:
        logger.exception('MAX→TG failed max %s/%s', max_chat_id, max_msg_id)
        return

    store.save_pair(
        bridge_key=bridge_key,
        src_platform='max',
        src_chat_id=max_chat_id,
        src_message_id=max_msg_id,
        dst_platform='tg',
        dst_chat_id=channel.tg_chat_id,
        dst_message_id=str(sent.message_id),
    )
    logger.info(
        'MAX→TG %s: max %s/%s → tg %s/%s',
        channel.id,
        max_chat_id,
        max_msg_id,
        channel.tg_chat_id,
        sent.message_id,
    )


async def _send_tg_from_max(
    bot: Bot,
    text: str,
    attachments: list[dict],
    max_client: MaxClient,
    **kwargs,
):
    # MVP: текст + первая ссылка на медиа (полная медиа-матрица — позже)
    if attachments:
        first = attachments[0] or {}
        att_type = str(first.get('type') or '').lower()
        payload = first.get('payload') or {}
        url = payload.get('url') or payload.get('src_url') or payload.get('link')
        if url and att_type in ('image', 'video', 'file'):
            caption = text[:1024] if text else None
            if att_type == 'image':
                return await bot.send_photo(kwargs['chat_id'], url, caption=caption, **{
                    k: v for k, v in kwargs.items() if k != 'chat_id'
                })
            if att_type == 'video':
                return await bot.send_video(kwargs['chat_id'], url, caption=caption, **{
                    k: v for k, v in kwargs.items() if k != 'chat_id'
                })
            return await bot.send_document(kwargs['chat_id'], url, caption=caption, **{
                k: v for k, v in kwargs.items() if k != 'chat_id'
            })

    return await bot.send_message(kwargs['chat_id'], text or '(пусто)', **{
        k: v for k, v in kwargs.items() if k != 'chat_id'
    })
