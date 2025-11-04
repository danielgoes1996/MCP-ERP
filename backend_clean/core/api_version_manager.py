"""
API Version Manager - Mitigación de riesgos de versionado

Garantiza convivencia segura entre v1 y v2 sin romper integraciones existentes.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi import Request, HTTPException
from functools import wraps

logger = logging.getLogger(__name__)

class APIVersionManager:
    """Gestor seguro de versiones de API."""

    def __init__(self):
        self.deprecated_endpoints = {}
        self.version_usage_stats = {}
        self.breaking_changes_log = []

    def register_v1_endpoint(self, endpoint: str, deprecation_date: Optional[datetime] = None):
        """Registrar endpoint v1 con fecha de deprecación opcional."""
        if deprecation_date:
            self.deprecated_endpoints[endpoint] = {
                "deprecation_date": deprecation_date,
                "replacement": f"/v2{endpoint}",
                "grace_period_days": 180  # 6 meses
            }

    def track_endpoint_usage(self, endpoint: str, version: str, client_info: Dict[str, Any]):
        """Trackear uso de endpoints para análisis de migración."""
        key = f"{version}:{endpoint}"

        if key not in self.version_usage_stats:
            self.version_usage_stats[key] = {
                "total_calls": 0,
                "unique_clients": set(),
                "last_call": None,
                "first_call": datetime.now()
            }

        stats = self.version_usage_stats[key]
        stats["total_calls"] += 1
        stats["unique_clients"].add(client_info.get("user_agent", "unknown"))
        stats["last_call"] = datetime.now()

    def check_deprecation_warnings(self, request: Request) -> Optional[Dict[str, Any]]:
        """Verificar si endpoint está deprecado y generar warning."""
        endpoint = request.url.path

        if endpoint in self.deprecated_endpoints:
            dep_info = self.deprecated_endpoints[endpoint]
            days_until_removal = (dep_info["deprecation_date"] - datetime.now()).days

            if days_until_removal > 0:
                return {
                    "warning": f"Endpoint will be deprecated in {days_until_removal} days",
                    "replacement": dep_info["replacement"],
                    "deprecation_date": dep_info["deprecation_date"].isoformat()
                }
            else:
                # Grace period
                grace_days_left = dep_info["grace_period_days"] - abs(days_until_removal)
                if grace_days_left > 0:
                    return {
                        "warning": f"Endpoint is DEPRECATED. Grace period: {grace_days_left} days",
                        "replacement": dep_info["replacement"],
                        "status": "deprecated"
                    }
                else:
                    # Should be removed, but we'll keep it for safety
                    return {
                        "error": "Endpoint removed. Please migrate immediately",
                        "replacement": dep_info["replacement"],
                        "status": "removed"
                    }

        return None

    def generate_migration_report(self) -> Dict[str, Any]:
        """Generar reporte de migración v1 -> v2."""
        report = {
            "v1_endpoints_still_used": [],
            "v2_adoption_rate": 0.0,
            "clients_needing_migration": [],
            "recommended_actions": []
        }

        v1_calls = sum(
            stats["total_calls"]
            for key, stats in self.version_usage_stats.items()
            if key.startswith("v1:")
        )

        v2_calls = sum(
            stats["total_calls"]
            for key, stats in self.version_usage_stats.items()
            if key.startswith("v2:")
        )

        total_calls = v1_calls + v2_calls
        if total_calls > 0:
            report["v2_adoption_rate"] = v2_calls / total_calls

        # Identify endpoints still heavily used in v1
        for key, stats in self.version_usage_stats.items():
            if key.startswith("v1:") and stats["total_calls"] > 100:  # Threshold
                endpoint = key.replace("v1:", "")
                report["v1_endpoints_still_used"].append({
                    "endpoint": endpoint,
                    "calls": stats["total_calls"],
                    "unique_clients": len(stats["unique_clients"]),
                    "last_used": stats["last_call"].isoformat() if stats["last_call"] else None
                })

        return report

def api_version_middleware():
    """Middleware para manejo seguro de versiones."""

    version_manager = APIVersionManager()

    # Register critical v1 endpoints with deprecation timeline
    critical_endpoints = [
        "/invoicing/tickets",
        "/invoicing/merchants",
        "/invoicing/jobs"
    ]

    # 6 months from now
    deprecation_date = datetime.now() + timedelta(days=180)

    for endpoint in critical_endpoints:
        version_manager.register_v1_endpoint(endpoint, deprecation_date)

    async def middleware(request: Request, call_next):
        """Middleware function."""

        # Determine API version
        path = request.url.path
        if "/v2/" in path:
            version = "v2"
        elif "/invoicing/" in path and "/v2/" not in path:
            version = "v1"
        else:
            version = "unknown"

        # Track usage
        client_info = {
            "user_agent": request.headers.get("user-agent", "unknown"),
            "client_ip": request.client.host if request.client else "unknown"
        }

        version_manager.track_endpoint_usage(path, version, client_info)

        # Check deprecation warnings
        deprecation_warning = version_manager.check_deprecation_warnings(request)

        # Process request
        response = await call_next(request)

        # Add deprecation headers if needed
        if deprecation_warning:
            if deprecation_warning.get("status") == "removed":
                # Block access to truly removed endpoints
                raise HTTPException(
                    status_code=410,  # Gone
                    detail=deprecation_warning["error"],
                    headers={"X-Replacement-Endpoint": deprecation_warning["replacement"]}
                )
            else:
                # Add warning headers
                response.headers["X-API-Deprecation-Warning"] = deprecation_warning["warning"]
                response.headers["X-API-Replacement"] = deprecation_warning["replacement"]

                if "deprecation_date" in deprecation_warning:
                    response.headers["X-API-Deprecation-Date"] = deprecation_warning["deprecation_date"]

        # Add version info
        response.headers["X-API-Version"] = version
        response.headers["X-API-Compatibility"] = "backward-compatible"

        return response

    return middleware

def ensure_v1_compatibility(func):
    """Decorator para garantizar compatibilidad v1."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        """Wrapper que valida respuesta v1."""

        # Execute original function
        result = await func(*args, **kwargs)

        # Validate v1 response format
        if isinstance(result, dict):
            # Ensure v1 required fields exist
            v1_required_fields = {"id", "estado", "created_at"}

            if "tickets" in func.__name__ and not v1_required_fields.issubset(result.keys()):
                logger.error(f"v1 compatibility broken in {func.__name__}: missing required fields")
                # Add missing fields with defaults
                for field in v1_required_fields:
                    if field not in result:
                        result[field] = None

        return result

    return wrapper

def safe_schema_evolution():
    """Helper para evolución segura de schemas."""

    # Schema compatibility rules
    rules = {
        "never_remove_fields": [
            "id", "estado", "created_at", "updated_at",
            "company_id", "ticket_id", "merchant_id"
        ],
        "always_optional_new_fields": True,
        "preserve_enum_values": [
            "pendiente", "procesando", "completado", "fallido"
        ]
    }

    def validate_schema_change(old_schema: Dict, new_schema: Dict) -> List[str]:
        """Validar que cambio de schema es seguro."""
        violations = []

        # Check removed fields
        old_fields = set(old_schema.get("properties", {}).keys())
        new_fields = set(new_schema.get("properties", {}).keys())
        removed_fields = old_fields - new_fields

        for field in removed_fields:
            if field in rules["never_remove_fields"]:
                violations.append(f"Critical field removed: {field}")

        # Check enum changes
        for field_name, field_def in new_schema.get("properties", {}).items():
            if "enum" in field_def:
                old_field_def = old_schema.get("properties", {}).get(field_name, {})
                if "enum" in old_field_def:
                    old_values = set(old_field_def["enum"])
                    new_values = set(field_def["enum"])
                    removed_values = old_values - new_values

                    for value in removed_values:
                        if value in rules["preserve_enum_values"]:
                            violations.append(f"Critical enum value removed: {field_name}.{value}")

        return violations

    return validate_schema_change

class BackwardCompatibilityValidator:
    """Validador de compatibilidad hacia atrás."""

    def __init__(self):
        self.v1_contracts = {}
        self.compatibility_violations = []

    def register_v1_contract(self, endpoint: str, expected_schema: Dict):
        """Registrar contrato v1 que debe mantenerse."""
        self.v1_contracts[endpoint] = expected_schema

    def validate_response(self, endpoint: str, response_data: Any) -> bool:
        """Validar que respuesta mantiene compatibilidad v1."""
        if endpoint not in self.v1_contracts:
            return True  # No contract to validate

        expected = self.v1_contracts[endpoint]

        try:
            # Validate structure
            if isinstance(response_data, dict) and isinstance(expected, dict):
                for required_field in expected.get("required", []):
                    if required_field not in response_data:
                        self.compatibility_violations.append(
                            f"Missing required field: {required_field} in {endpoint}"
                        )
                        return False

            return True

        except Exception as e:
            self.compatibility_violations.append(
                f"Validation error for {endpoint}: {str(e)}"
            )
            return False

# Global instances
version_manager = APIVersionManager()
compatibility_validator = BackwardCompatibilityValidator()

# Register critical v1 contracts
compatibility_validator.register_v1_contract("/invoicing/tickets", {
    "required": ["id", "estado", "created_at", "updated_at"],
    "properties": {
        "estado": {"enum": ["pendiente", "procesando", "completado", "fallido"]}
    }
})

compatibility_validator.register_v1_contract("/invoicing/merchants", {
    "required": ["id", "nombre", "metodo_facturacion", "is_active"],
    "properties": {
        "metodo_facturacion": {"enum": ["portal", "email", "api"]}
    }
})