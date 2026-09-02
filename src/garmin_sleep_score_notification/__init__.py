import logging
import os

__version__ = "0.1.0"


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("garminconnect", "garth", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
