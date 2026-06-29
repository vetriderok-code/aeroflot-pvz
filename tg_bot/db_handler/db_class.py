import psycopg2
import logging
from decouple import config
from functools import wraps
from asyncpg_lite import DatabaseManager

logger = logging.getLogger(__name__)
pg_link = config('PG_LINK')

def log_query(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        query = args[1] if len(args) > 1 else kwargs.get('query', '')
        params = args[2:] if len(args) > 2 else []

        logger.info(f"Executing query: {query}")
        logger.debug(f"Parameters: {params}")

        try:
            result = await func(*args, **kwargs)
            logger.info("Query executed successfully")
            return result
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise

    return wrapper


class PostgresHandler:
    def __init__(self):
        self.conn = None
        self.cur = None
        self.connect()

    def connect(self):
        self.conn = psycopg2.connect(user=config('POSTGRES_USER'),
                                     password=config('POSTGRES_PASSWORD'),
                                     host=config('POSTGRES_HOST'),
                                     port=config('POSTGRES_PORT'),
                                     dbname=config('POSTGRES_DB'))
        self.cur = self.conn.cursor()

    def disconnect(self):
        self.conn.close()

    # @log_query
    def execute(self, query, *args):
        try:
            self.cur.execute(query, *args)
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Query failed: {e}")

    # @log_query
    def fetch(self, query, *args):
        self.execute(query, *args)
        return self.cur.fetchall()

    #@log_query
    def fetchrow(self, query, *args):
        self.execute(query, *args)
        return self.cur.fetchone()
