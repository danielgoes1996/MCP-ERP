"""
Reconciliation Module

Módulo de conciliación bancaria incluyendo:
- Bank: Detección y parsing de bancos
- Matching: Motor de conciliación y matching
- Validation: Detección de duplicados y validación
"""

from . import bank
from . import matching
from . import validation

__all__ = ['bank', 'matching', 'validation']
