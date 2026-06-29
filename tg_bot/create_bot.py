import logging
import redis
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from decouple import config
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from db_handler.db_class import PostgresHandler

#from dispatcher import CustomDispatcher

pg_db = PostgresHandler()
redis_storage = RedisStorage.from_url(config('REDIS_URL'))

scheduler = AsyncIOScheduler(timezone='Europe/Moscow')
#admins = [int(admin_id) for admin_id in config('ADMINS').split(',')]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _create_bot() -> Bot:
    """Основной бот — облачный API (polling, сообщения). Скачивание видео — отдельно, см. report_video_download."""
    token = config('TOKEN')
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


bot = _create_bot()
#dp = CustomDispatcher(storage=MemoryStorage())
dp = Dispatcher(storage=redis_storage)
