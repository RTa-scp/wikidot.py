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

from . import logger
from .customexceptions import *
from .main import Util, Parser, Client, Site, User, UserCollection, SiteMember, SiteMemberCollection, PrivateMessage

logger = logger.logger

nest_asyncio.apply()
