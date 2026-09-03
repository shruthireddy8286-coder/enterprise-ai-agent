"""
Shared logging setup. Import get_logger(__name__) in any module instead of
using print() -- gives you timestamps, levels, and module names for free,
and makes debugging "why didn't my message get stored" actually possible.
"""

import logging

_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        _configured = True
    return logging.getLogger(name)