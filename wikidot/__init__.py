"""
wikidot.py
~~~~~~~~~~
Wikidot Ajax/API Request Wrapper

version:
    2.0.0
copyright:
    (c) 2020-2022 ukwhatn
license:
    MIT License
"""

import nest_asyncio

from .main import Client, Site, User
from .customexceptions import *

nest_asyncio.apply()
