"""Core application configuration and state management."""
from .config import AppConfig, config
from .session_manager import SessionManager
from .dataset_manager import DatasetManager

__all__ = ["AppConfig", "config", "SessionManager", "DatasetManager"]
