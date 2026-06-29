"""Конфигурация моста TG ↔ MAX."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml
from decouple import config

logger = logging.getLogger(__name__)

BRIDGE_DIR = Path(__file__).resolve().parent
DEFAULT_MAPPING = BRIDGE_DIR / 'mapping.yaml'

ENV_MAX_CHAT = {
    'dirty': 'MAX_BRIDGE_CHAT_DIRTY',
    'td_quarter': 'MAX_BRIDGE_CHAT_TD',
}


@dataclass(frozen=True)
class BridgeChannel:
    id: str
    label: str
    tg_chat_id: int
    tg_topic_id: int | None
    max_chat_id: int | None

    def matches_tg(self, chat_id: int, topic_id: int | None) -> bool:
        if int(chat_id) != self.tg_chat_id:
            return False
        if self.tg_topic_id is None:
            return True
        return topic_id is not None and int(topic_id) == self.tg_topic_id

    def matches_max(self, max_chat_id: int) -> bool:
        return self.max_chat_id is not None and int(self.max_chat_id) == int(max_chat_id)


def bridge_enabled() -> bool:
    return config('MAX_BRIDGE_ENABLED', default='false').lower() in ('1', 'true', 'yes')


def max_bot_token() -> str:
    return config('MAX_BOT_TOKEN', default='').strip()


def bridge_db_path() -> Path:
    raw = config('MAX_BRIDGE_DB', default='').strip()
    if raw:
        return Path(raw)
    return BRIDGE_DIR / 'data' / 'bridge.db'


def _parse_int(value) -> int | None:
    if value in (None, '', 'null'):
        return None
    return int(value)


def load_channels() -> list[BridgeChannel]:
    mapping_path = Path(config('MAX_BRIDGE_MAPPING', default=str(DEFAULT_MAPPING)))
    if not mapping_path.is_file():
        logger.warning('MAX bridge mapping not found: %s', mapping_path)
        return []

    with mapping_path.open(encoding='utf-8') as fh:
        data = yaml.safe_load(fh) or {}

    channels: list[BridgeChannel] = []
    for row in data.get('channels') or []:
        channel_id = str(row.get('id') or '').strip()
        env_key = ENV_MAX_CHAT.get(channel_id, '')
        max_from_env = config(env_key, default='').strip() if env_key else ''
        max_chat_id = _parse_int(row.get('max_chat_id'))
        if max_from_env:
            try:
                max_chat_id = int(max_from_env)
            except ValueError:
                logger.warning('Invalid %s=%s', env_key, max_from_env)

        channels.append(
            BridgeChannel(
                id=channel_id,
                label=str(row.get('label') or channel_id),
                tg_chat_id=int(row['tg_chat_id']),
                tg_topic_id=_parse_int(row.get('tg_topic_id')),
                max_chat_id=max_chat_id,
            )
        )
    return channels


def load_topic_labels() -> dict[tuple[int, int | None], str]:
    mapping_path = Path(config('MAX_BRIDGE_MAPPING', default=str(DEFAULT_MAPPING)))
    if not mapping_path.is_file():
        return {}

    with mapping_path.open(encoding='utf-8') as fh:
        data = yaml.safe_load(fh) or {}

    result: dict[tuple[int, int | None], str] = {}
    for chat_key, topics in (data.get('topic_labels') or {}).items():
        try:
            chat_id = int(chat_key)
        except (TypeError, ValueError):
            continue
        if not isinstance(topics, dict):
            continue
        for topic_key, label in topics.items():
            try:
                topic_id = int(topic_key)
            except (TypeError, ValueError):
                continue
            result[(chat_id, topic_id)] = str(label)
    return result


def find_tg_channel(channels: list[BridgeChannel], chat_id: int, topic_id: int | None) -> BridgeChannel | None:
    for ch in channels:
        if ch.matches_tg(chat_id, topic_id):
            return ch
    return None


def find_max_channel(channels: list[BridgeChannel], max_chat_id: int) -> BridgeChannel | None:
    for ch in channels:
        if ch.matches_max(max_chat_id):
            return ch
    return None


def topic_label(chat_id: int, topic_id: int | None) -> str | None:
    labels = load_topic_labels()
    if topic_id is not None:
        label = labels.get((int(chat_id), int(topic_id)))
        if label:
            return label
    return labels.get((int(chat_id), None))
