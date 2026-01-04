"""Base interfaces and registry for vertical modules."""

from .vertical_interface import VerticalBase
from .registry import vertical_registry, get_active_vertical

__all__ = [
    'VerticalBase',
    'vertical_registry',
    'get_active_vertical'
]
