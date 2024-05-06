from pydantic import BaseModel
from json import loads


class Config(BaseModel):
    tokens: dict[str, str]
    bot_token: str
    database: str

    def box_token(self) -> str:
        return self.tokens["box"]

    def lock_token(self) -> str:
        return self.tokens["lock"]


CONFIG = None

with open("config.json", "r") as fp:
    cfg = fp.read()
    cfg = loads(cfg)
    CONFIG = Config(
        bot_token=cfg["telegram_token"],
        tokens=cfg["shared_keys"],
        database=cfg["database"],
    )
    CONFIG.box_token()
    CONFIG.lock_token()


def get_config() -> Config:
    return CONFIG
