"""
Expenses Module

Módulo de gestión de gastos y facturas incluyendo:
- Invoices: Procesamiento de facturas
- Completion: Sistema de completado inteligente
- Validation: Validación de campos
- Workflow: Flujo de escalación y notificaciones
- Audit: Auditoría y compliance
"""

from . import invoices
from . import completion
from . import validation
from . import workflow
from . import audit

__all__ = ['invoices', 'completion', 'validation', 'workflow', 'audit']
