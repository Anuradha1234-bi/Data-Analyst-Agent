import logging
import sys


def setup_logger(name: str = "ai_data_analyst") -> logging.Logger:
    """Configure and return a standardized application logger."""
    app_logger = logging.getLogger(name)

    if not app_logger.handlers:
        app_logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        app_logger.addHandler(handler)
        app_logger.propagate = False

    return app_logger


logger = setup_logger()
