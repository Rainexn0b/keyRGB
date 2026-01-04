"""ITE 8291r3 USB RGB keyboard backend.

This package name is intentionally explicit about the protocol dialect.
"""

from .backend import Ite8291r3Backend

__all__ = ["Ite8291r3Backend"]
