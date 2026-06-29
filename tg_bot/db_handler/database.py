import asyncio
from typing import Union
from decouple import config
import asyncpg
import asyncio
from asyncpg import Connection
from asyncpg.pool import Pool


class DataBaseClass:
    def __init__(self):
        self.pool: Union[Pool, None] = None

    async def create_pool(self):
        self.pool = await asyncpg.create_pool(config("PG_LINK"))

    async def execute(self, command: str, *args,
                      fetch: bool = False,
                      fetchval: bool = False,
                      fetchrow: bool = False,
                      execute: bool = False):
        async with self.pool.acquire() as connection:
            connection: Connection
            async with connection.transaction():
                if fetch:
                    result = await connection.fetch(command, *args)
                elif fetchval:
                    result = await connection.fetchval(command, *args)
                elif fetchrow:
                    result = await connection.fetchrow(command, *args)
                elif execute:
                    result = await connection.execute(command, *args)
        return await result


async def main():
    DataBase = DataBaseClass()
    query = 'SELECT * FROM flights'
    await DataBase.execute(query, fetch=True)

asyncio.run(main())