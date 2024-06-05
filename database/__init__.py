import os
import aiosqlite

DB: aiosqlite.Connection = None


async def init_database(database: str = "./mugs.sqlite"):
    global DB
    DB = await aiosqlite.connect(database)
    cur = await DB.cursor()
    await cur.execute("PRAGMA user_version")
    skip: int = (await cur.fetchone())[0]
    print("Database migration: found user_version =", skip)
    files = os.listdir("migrations/")
    cnt = 0
    ver = skip
    for file_name in files:
        if os.path.isfile(os.path.join("migrations/", file_name)):
            cnt += 1
            if skip > 0:
                skip -= 1
                continue
            with open(os.path.join("migrations/", file_name), "r") as file:
                await cur.executescript(file.read())
    print(f"Database migration: applied {cnt-ver} migrations of {cnt} total")
    if ver != cnt:
        await cur.execute(f"PRAGMA user_version = {cnt}")
        await DB.commit()
        print(f"Database migration: set user_version = {cnt}")


async def get_connection() -> aiosqlite.Cursor:
    global DB
    return await DB.cursor()


async def commit_changes() -> None:
    global DB
    await DB.commit()
