import os
import aiosqlite

DB: aiosqlite.Connection = None


async def init_database(database: str = "./mugs.sqlite"):
    global DB
    DB = await aiosqlite.connect(database)
    cur = await DB.cursor()
    files = os.listdir("migrations/")
    for file_name in files:
        if os.path.isfile(os.path.join("migrations/", file_name)):
            with open(os.path.join("migrations/", file_name), "r") as file:
                await cur.executescript(file.read())


async def get_connection() -> aiosqlite.Cursor:
    global DB
    return await DB.cursor()


async def commit_changes() -> None:
    global DB
    await DB.commit()
