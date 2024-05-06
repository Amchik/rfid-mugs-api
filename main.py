import asyncio
from database import init_database
from httpserver import start_server
from telegram import start_bot
import uvicorn
from models.config import get_config


async def main():
    await init_database(get_config().database)
    app = start_server(None)
    # config = uvicorn.Config(app, loop=loop)
    config = uvicorn.Config(app)
    server = uvicorn.Server(config)
    # loop.run_until_complete(server.serve())
    await asyncio.gather(
        start_bot(),
        # app(scope, receive, send),
        server.serve(),
    )


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
