"""
S.C.O.U.T (Scope Change Observation & Unified Tracking) - Bug Bounty Monitoring Tool
Core package containing all monitoring functionality
"""

__version__ = "1.0.0"
__author__ = "S.C.O.U.T Team"

from .db import Database
from .monitor import SCOUTMonitor
from .notifier import TelegramNotifier, create_notifier

__all__ = [
    'Database',
    'SCOUTMonitor',
    'TelegramNotifier',
    'create_notifier'
]