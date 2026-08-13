"""
Rate limiter singleton.
Extracted to its own module to avoid circular imports between main.py and routers.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter — keyed by client IP
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
