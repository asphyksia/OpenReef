"""Shared rate limiter for all API routers.

Import this module directly instead of creating a Limiter in each router.
This ensures a single rate limiter instance is used across the application.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
