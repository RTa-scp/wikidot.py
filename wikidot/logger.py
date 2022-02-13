import logging

# GetLogger
logger = logging.getLogger("wikidot.py")
logger.setLevel(logging.WARNING)

# StreamHandler
_sh = logging.StreamHandler()
_sh.setFormatter(logging.Formatter("[wikidot.py/%(levelname)s] %(message)s"))
logger.addHandler(_sh)
del _sh
