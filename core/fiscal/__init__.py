"""
Fiscal regulations module for tax compliance and depreciation rates.

This module provides services for:
- Depreciation rate determination using RAG over Mexican tax law (LISR)
- Tax regulation retrieval and semantic search
- Legal compliance validation
"""

from core.fiscal.depreciation_rate_service import (
    get_depreciation_rate_service,
    DepreciationRate,
    DepreciationRateService
)

__all__ = [
    'get_depreciation_rate_service',
    'DepreciationRate',
    'DepreciationRateService'
]
