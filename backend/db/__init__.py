"""db package — exposes connection utilities at the package level."""
from .connection import get_db, get_connection, init_db, close_db

__all__ = ["get_db", "get_connection", "init_db", "close_db"]