"""Shared logging config.

Keep this package name to match the platform README. Do not `import logging`
from files in this folder — that shadows the stdlib module. Configure logging
in each service `main.py` instead:

    import logging
    logging.basicConfig(level=logging.INFO)
"""
