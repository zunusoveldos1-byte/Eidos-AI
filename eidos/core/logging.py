"""Operational logging without audio or transcripts."""

import logging


def configure_logging() -> None:
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    logging.getLogger('eidos').setLevel(logging.INFO)
