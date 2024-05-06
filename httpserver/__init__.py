from .app import app
from models.appstate import AppState

from .v0 import router as _


def start_server(_app_state: AppState):
    return app
