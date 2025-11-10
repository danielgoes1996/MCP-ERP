"""
Sistema de Validación de Seguridad para Operaciones Masivas de Gastos
Punto 12: Acciones de Gastos - Security Validation System

Este módulo proporciona:
- Validación de permisos en tiempo real
- Detección de patrones sospechosos
- Rate limiting y throttling
- Validación de integridad de datos
- Auditoría de seguridad
- Prevención de ataques de manipulación masiva
"""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import ipaddress
import re
import logging
from collections import defaultdict

from core.expenses.audit.expense_audit_system import ActionType, ActionContext

logger = logging.getLogger(__name__)


class SecurityRiskLevel(Enum):
    """Niveles de riesgo de seguridad"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ValidationResult(Enum):
    """Resultados de validación"""
    APPROVED = "approved"
    REJECTED = "rejected"
    REQUIRES_APPROVAL = "requires_approval"
    REQUIRES_MFA = "requires_mfa"
    BLOCKED = "blocked"


@dataclass
class SecurityRule:
    """Regla de seguridad"""
    rule_id: str
    rule_type: str  # 'permission', 'rate_limit', 'pattern', 'business_logic'
    condition: str
    action: ValidationResult
    priority: int  # 1=highest, 10=lowest
    is_active: bool = True
    metadata: Dict[str, Any] = None


@dataclass
class SecurityValidationResult:
    """Resultado de validación de seguridad"""
    is_valid: bool
    result_type: ValidationResult
    risk_level: SecurityRiskLevel
    violated_rules: List[str]
    warnings: List[str]
    required_approvals: List[str]
    additional_verification: Dict[str, Any]
    security_score: float  # 0.0-1.0, donde 1.0 es más seguro


@dataclass
class RateLimitEntry:
    """Entrada de rate limiting"""
    identifier: str  # user_id, ip_address, etc.
    action_type: ActionType
    count: int
    first_request: datetime
    last_request: datetime
    window_seconds: int


class ExpenseSecurityValidator:
    """Validador de seguridad para operaciones de gastos"""

    def __init__(self, db_adapter):
        self.db = db_adapter

        # Cache de reglas y permisos
        self._security_rules: Dict[str, List[SecurityRule]] = {}
        self._user_permissions_cache: Dict[int, Dict[str, Any]] = {}
        self._rate_limit_store: Dict[str, RateLimitEntry] = {}

        # Configuración de rate limiting
        self.default_rate_limits = {
            ActionType.BULK_UPDATE: {"requests": 10, "window": 3600},  # 10 por hora
            ActionType.MARK_INVOICED: {"requests": 100, "window": 3600},  # 100 por hora
            ActionType.DELETE: {"requests": 5, "window": 3600},  # 5 por hora
            ActionType.ARCHIVE: {"requests": 50, "window": 3600}  # 50 por hora
        }

        # Patrones sospechosos
        self.suspicious_patterns = {
            "rapid_fire": {"threshold": 20, "window": 60},  # 20 acciones en 1 minuto
            "large_batch": {"threshold": 500, "single_operation": True},
            "unusual_hours": {"start_hour": 0, "end_hour": 6},  # 12-6 AM
            "weekend_bulk": {"days": [5, 6]}  # Sábado y Domingo
        }

        # IPs confiables (whitelist)
        self.trusted_ip_ranges = [
            ipaddress.IPv4Network("10.0.0.0/8"),
            ipaddress.IPv4Network("172.16.0.0/12"),
            ipaddress.IPv4Network("192.168.0.0/16")
        ]

    async def validate_bulk_operation(
        self,
        action_type: ActionType,
        context: ActionContext,
        target_expense_ids: List[int],
        parameters: Dict[str, Any],
        estimated_impact: Dict[str, Any]
    ) -> SecurityValidationResult:
        """Validación completa de seguridad para operación masiva"""

        violated_rules = []
        warnings = []
        required_approvals = []
        additional_verification = {}
        risk_factors = []

        try:
            # 1. Validación de permisos básicos
            permission_result = await self._validate_user_permissions(
                context.user_id, action_type, context.company_id
            )
            if not permission_result["has_permission"]:
                return SecurityValidationResult(
                    is_valid=False,
                    result_type=ValidationResult.REJECTED,
                    risk_level=SecurityRiskLevel.HIGH,
                    violated_rules=["insufficient_permissions"],
                    warnings=[],
                    required_approvals=[],
                    additional_verification={},
                    security_score=0.0
                )

            # 2. Validación de rate limiting
            rate_limit_result = await self._check_rate_limits(
                context, action_type, len(target_expense_ids)
            )
            if not rate_limit_result["within_limits"]:
                violated_rules.append("rate_limit_exceeded")
                risk_factors.append("rate_limit")

            # 3. Detección de patrones sospechosos
            pattern_result = await self._detect_suspicious_patterns(
                context, action_type, target_expense_ids, parameters
            )
            if pattern_result["is_suspicious"]:
                violated_rules.extend(pattern_result["patterns"])
                risk_factors.extend(pattern_result["patterns"])
                warnings.extend(pattern_result["warnings"])

            # 4. Validación de integridad de datos
            integrity_result = await self._validate_data_integrity(
                target_expense_ids, parameters, action_type
            )
            if not integrity_result["is_valid"]:
                violated_rules.extend(integrity_result["violations"])
                warnings.extend(integrity_result["warnings"])

            # 5. Validación de reglas de negocio específicas
            business_result = await self._validate_business_rules(
                action_type, context, target_expense_ids, parameters
            )
            if not business_result["is_valid"]:
                violated_rules.extend(business_result["violations"])
                if business_result.get("requires_approval"):
                    required_approvals.extend(business_result["required_approvals"])

            # 6. Evaluación de riesgo geográfico/temporal
            geo_temporal_result = await self._evaluate_geo_temporal_risk(
                context, action_type, len(target_expense_ids)
            )
            if geo_temporal_result["risk_level"] != SecurityRiskLevel.LOW:
                risk_factors.append("geo_temporal")
                warnings.extend(geo_temporal_result["warnings"])

            # 7. Validación de impacto financiero
            financial_risk = await self._assess_financial_impact_risk(
                target_expense_ids, parameters, estimated_impact
            )
            if financial_risk["risk_level"] != SecurityRiskLevel.LOW:
                risk_factors.append("financial_impact")
                if financial_risk["requires_approval"]:
                    required_approvals.append("financial_supervisor")

            # Calcular score de seguridad
            security_score = self._calculate_security_score(
                risk_factors, violated_rules, len(target_expense_ids)
            )

            # Determinar nivel de riesgo general
            risk_level = self._determine_overall_risk_level(risk_factors, security_score)

            # Determinar resultado final
            result_type = self._determine_validation_result(
                violated_rules, required_approvals, risk_level, security_score
            )

            # Configurar verificación adicional si es necesaria
            if result_type in [ValidationResult.REQUIRES_APPROVAL, ValidationResult.REQUIRES_MFA]:
                additional_verification = await self._configure_additional_verification(
                    result_type, risk_level, context
                )

            # Log de auditoría de seguridad
            await self._log_security_validation(
                context, action_type, len(target_expense_ids), result_type, risk_level
            )

            return SecurityValidationResult(
                is_valid=(result_type == ValidationResult.APPROVED),
                result_type=result_type,
                risk_level=risk_level,
                violated_rules=violated_rules,
                warnings=warnings,
                required_approvals=required_approvals,
                additional_verification=additional_verification,
                security_score=security_score
            )

        except Exception as e:
            logger.error(f"Security validation failed: {e}")
            return SecurityValidationResult(
                is_valid=False,
                result_type=ValidationResult.BLOCKED,
                risk_level=SecurityRiskLevel.CRITICAL,
                violated_rules=["validation_error"],
                warnings=[f"Security validation system error: {str(e)}"],
                required_approvals=["security_admin"],
                additional_verification={},
                security_score=0.0
            )

    async def validate_single_expense_modification(
        self,
        expense_id: int,
        modifications: Dict[str, Any],
        context: ActionContext
    ) -> SecurityValidationResult:
        """Validación de seguridad para modificación de gasto individual"""

        # Para modificaciones individuales, usar validación simplificada
        return await self.validate_bulk_operation(
            ActionType.UPDATE_CATEGORY,  # Tipo genérico
            context,
            [expense_id],
            modifications,
            {"financial_impact": "low"}
        )

    async def check_operation_authorization(
        self,
        user_id: int,
        action_type: ActionType,
        company_id: str,
        additional_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Verifica autorización para un tipo de operación"""

        try:
            # Verificar permisos básicos
            permissions = await self._validate_user_permissions(user_id, action_type, company_id)

            # Verificar límites del usuario
            user_limits = await self._get_user_operation_limits(user_id, action_type)

            # Verificar estado de la cuenta
            account_status = await self._check_account_security_status(user_id)

            return {
                "authorized": permissions["has_permission"] and account_status["is_active"],
                "permissions": permissions,
                "limits": user_limits,
                "account_status": account_status,
                "restrictions": account_status.get("restrictions", [])
            }

        except Exception as e:
            logger.error(f"Authorization check failed for user {user_id}: {e}")
            return {
                "authorized": False,
                "error": str(e),
                "permissions": {},
                "limits": {},
                "account_status": {"is_active": False}
            }

    # Métodos privados de validación

    async def _validate_user_permissions(
        self,
        user_id: int,
        action_type: ActionType,
        company_id: str
    ) -> Dict[str, Any]:
        """Valida permisos del usuario"""

        # Cache hit
        cache_key = f"{user_id}_{company_id}"
        if cache_key in self._user_permissions_cache:
            cached_perms = self._user_permissions_cache[cache_key]
            if (datetime.utcnow() - cached_perms["cached_at"]).total_seconds() < 300:  # 5 min cache
                return cached_perms

        try:
            # Obtener información del usuario
            user_query = """
            SELECT u.id, u.role, u.is_active, u.company_id
            FROM users u
            WHERE u.id = $1 AND u.company_id = $2 AND u.is_active = TRUE
            """

            user = await self.db.fetch_one(user_query, user_id, company_id)
            if not user:
                return {"has_permission": False, "reason": "user_not_found"}

            # Mapeo de permisos por rol y acción
            role_permissions = {
                "admin": {
                    ActionType.BULK_UPDATE: True,
                    ActionType.DELETE: True,
                    ActionType.MARK_INVOICED: True,
                    ActionType.ARCHIVE: True,
                    ActionType.MARK_NO_INVOICE: True
                },
                "manager": {
                    ActionType.BULK_UPDATE: True,
                    ActionType.DELETE: False,
                    ActionType.MARK_INVOICED: True,
                    ActionType.ARCHIVE: True,
                    ActionType.MARK_NO_INVOICE: True
                },
                "user": {
                    ActionType.BULK_UPDATE: False,
                    ActionType.DELETE: False,
                    ActionType.MARK_INVOICED: True,
                    ActionType.ARCHIVE: False,
                    ActionType.MARK_NO_INVOICE: True
                }
            }

            user_role = user["role"]
            has_permission = role_permissions.get(user_role, {}).get(action_type, False)

            result = {
                "has_permission": has_permission,
                "user_role": user_role,
                "user_id": user_id,
                "company_id": company_id,
                "cached_at": datetime.utcnow()
            }

            # Cache result
            self._user_permissions_cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Permission validation failed: {e}")
            return {"has_permission": False, "reason": "validation_error", "error": str(e)}

    async def _check_rate_limits(
        self,
        context: ActionContext,
        action_type: ActionType,
        record_count: int
    ) -> Dict[str, Any]:
        """Verifica límites de velocidad"""

        current_time = datetime.utcnow()
        limits = self.default_rate_limits.get(action_type, {"requests": 50, "window": 3600})

        # Identificadores para rate limiting
        identifiers = [
            f"user_{context.user_id}",
            f"company_{context.company_id}",
            f"session_{context.session_id}"
        ]

        if context.ip_address:
            identifiers.append(f"ip_{context.ip_address}")

        violations = []

        for identifier in identifiers:
            key = f"{identifier}_{action_type.value}"

            if key in self._rate_limit_store:
                entry = self._rate_limit_store[key]

                # Limpiar ventana de tiempo si ha expirado
                if (current_time - entry.first_request).total_seconds() > entry.window_seconds:
                    entry.count = 0
                    entry.first_request = current_time

                # Verificar límite
                if entry.count >= limits["requests"]:
                    violations.append({
                        "identifier": identifier,
                        "current_count": entry.count,
                        "limit": limits["requests"],
                        "window_seconds": limits["window"],
                        "time_until_reset": entry.window_seconds - (current_time - entry.first_request).total_seconds()
                    })

                # Actualizar contador
                entry.count += 1
                entry.last_request = current_time

            else:
                # Crear nueva entrada
                self._rate_limit_store[key] = RateLimitEntry(
                    identifier=identifier,
                    action_type=action_type,
                    count=1,
                    first_request=current_time,
                    last_request=current_time,
                    window_seconds=limits["window"]
                )

        return {
            "within_limits": len(violations) == 0,
            "violations": violations,
            "limits": limits
        }

    async def _detect_suspicious_patterns(
        self,
        context: ActionContext,
        action_type: ActionType,
        target_expense_ids: List[int],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Detecta patrones sospechosos"""

        patterns_detected = []
        warnings = []
        current_time = datetime.utcnow()

        # 1. Patrón de fuego rápido (rapid fire)
        recent_actions = await self._get_recent_user_actions(context.user_id, 60)  # Últimos 60 segundos
        if len(recent_actions) >= self.suspicious_patterns["rapid_fire"]["threshold"]:
            patterns_detected.append("rapid_fire")
            warnings.append(f"Usuario realizó {len(recent_actions)} acciones en el último minuto")

        # 2. Lote muy grande
        if len(target_expense_ids) >= self.suspicious_patterns["large_batch"]["threshold"]:
            patterns_detected.append("large_batch")
            warnings.append(f"Operación muy grande: {len(target_expense_ids)} registros")

        # 3. Horario inusual
        current_hour = current_time.hour
        unusual_hours = self.suspicious_patterns["unusual_hours"]
        if unusual_hours["start_hour"] <= current_hour <= unusual_hours["end_hour"]:
            patterns_detected.append("unusual_hours")
            warnings.append(f"Operación realizada en horario inusual: {current_hour}:00")

        # 4. Operación masiva en fin de semana
        if current_time.weekday() in self.suspicious_patterns["weekend_bulk"]["days"]:
            if len(target_expense_ids) > 50:  # Solo para operaciones grandes
                patterns_detected.append("weekend_bulk")
                warnings.append("Operación masiva realizada en fin de semana")

        # 5. Patrón geográfico sospechoso
        if context.ip_address:
            geo_suspicious = await self._check_geographical_pattern(context)
            if geo_suspicious:
                patterns_detected.append("geographical_anomaly")
                warnings.append("Dirección IP inusual para este usuario")

        return {
            "is_suspicious": len(patterns_detected) > 0,
            "patterns": patterns_detected,
            "warnings": warnings
        }

    async def _validate_data_integrity(
        self,
        target_expense_ids: List[int],
        parameters: Dict[str, Any],
        action_type: ActionType
    ) -> Dict[str, Any]:
        """Valida integridad de datos"""

        violations = []
        warnings = []

        try:
            # 1. Verificar que los gastos existen y son accesibles
            existing_count = await self.db.fetch_one(
                "SELECT COUNT(*) as count FROM expenses WHERE id = ANY($1)",
                target_expense_ids
            )

            if existing_count["count"] != len(target_expense_ids):
                violations.append("missing_expenses")
                warnings.append(f"Algunos gastos no existen: {len(target_expense_ids) - existing_count['count']} faltantes")

            # 2. Verificar estados consistentes
            if action_type == ActionType.MARK_INVOICED:
                already_invoiced = await self.db.fetch_one("""
                    SELECT COUNT(*) as count FROM expenses
                    WHERE id = ANY($1) AND invoice_status = 'invoiced'
                """, target_expense_ids)

                if already_invoiced["count"] > 0:
                    warnings.append(f"{already_invoiced['count']} gastos ya están facturados")

            # 3. Verificar valores válidos en parámetros
            if "categoria" in parameters:
                categoria = parameters["categoria"]
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', categoria):
                    violations.append("invalid_category_format")

            # 4. Verificar límites de campos
            if "descripcion" in parameters:
                if len(parameters["descripcion"]) > 500:
                    violations.append("description_too_long")

            # 5. Verificar duplicados en la operación actual
            if len(target_expense_ids) != len(set(target_expense_ids)):
                violations.append("duplicate_target_ids")

            return {
                "is_valid": len(violations) == 0,
                "violations": violations,
                "warnings": warnings
            }

        except Exception as e:
            logger.error(f"Data integrity validation failed: {e}")
            return {
                "is_valid": False,
                "violations": ["integrity_check_failed"],
                "warnings": [f"Validation error: {str(e)}"]
            }

    async def _validate_business_rules(
        self,
        action_type: ActionType,
        context: ActionContext,
        target_expense_ids: List[int],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Valida reglas de negocio específicas"""

        violations = []
        required_approvals = []

        try:
            # Obtener reglas activas para la empresa
            rules = await self._get_active_business_rules(context.company_id, action_type)

            for rule in rules:
                rule_result = await self._evaluate_business_rule(rule, {
                    "action_type": action_type,
                    "context": context,
                    "target_expense_ids": target_expense_ids,
                    "parameters": parameters
                })

                if not rule_result["compliant"]:
                    violations.append(rule["rule_name"])
                    if rule_result.get("requires_approval"):
                        required_approvals.extend(rule_result["required_approvers"])

            # Reglas específicas hardcodeadas
            if action_type == ActionType.DELETE:
                # Verificar que no se intenten eliminar gastos facturados
                invoiced_count = await self.db.fetch_one("""
                    SELECT COUNT(*) as count FROM expenses
                    WHERE id = ANY($1) AND invoice_status = 'invoiced'
                """, target_expense_ids)

                if invoiced_count["count"] > 0:
                    violations.append("cannot_delete_invoiced_expenses")

            return {
                "is_valid": len(violations) == 0,
                "violations": violations,
                "requires_approval": len(required_approvals) > 0,
                "required_approvals": required_approvals
            }

        except Exception as e:
            logger.error(f"Business rules validation failed: {e}")
            return {
                "is_valid": False,
                "violations": ["business_rules_error"],
                "requires_approval": True,
                "required_approvals": ["supervisor"]
            }

    async def _evaluate_geo_temporal_risk(
        self,
        context: ActionContext,
        action_type: ActionType,
        record_count: int
    ) -> Dict[str, Any]:
        """Evalúa riesgo geográfico y temporal"""

        risk_level = SecurityRiskLevel.LOW
        warnings = []

        try:
            # Riesgo temporal
            current_hour = datetime.utcnow().hour
            current_day = datetime.utcnow().weekday()

            # Horario de alto riesgo
            if 0 <= current_hour <= 6:  # 12-6 AM
                risk_level = SecurityRiskLevel.MEDIUM
                warnings.append("Operación en horario de bajo tráfico")

            # Fin de semana con operaciones grandes
            if current_day in [5, 6] and record_count > 100:
                risk_level = max(risk_level, SecurityRiskLevel.MEDIUM)
                warnings.append("Operación masiva en fin de semana")

            # Riesgo geográfico
            if context.ip_address:
                try:
                    ip = ipaddress.IPv4Address(context.ip_address)
                    is_trusted = any(ip in trusted_range for trusted_range in self.trusted_ip_ranges)

                    if not is_trusted:
                        risk_level = max(risk_level, SecurityRiskLevel.MEDIUM)
                        warnings.append("IP address outside trusted ranges")

                    # Verificar si es IP conocida para el usuario
                    ip_history = await self._check_user_ip_history(context.user_id, context.ip_address)
                    if not ip_history["is_known"]:
                        risk_level = max(risk_level, SecurityRiskLevel.HIGH)
                        warnings.append("New IP address for user")

                except ValueError:
                    warnings.append("Invalid IP address format")

            return {
                "risk_level": risk_level,
                "warnings": warnings,
                "temporal_risk": current_hour in range(0, 7) or current_day in [5, 6],
                "geographical_risk": context.ip_address and not is_trusted if context.ip_address else False
            }

        except Exception as e:
            logger.error(f"Geo-temporal risk evaluation failed: {e}")
            return {
                "risk_level": SecurityRiskLevel.MEDIUM,
                "warnings": ["Risk evaluation error"],
                "temporal_risk": False,
                "geographical_risk": False
            }

    async def _assess_financial_impact_risk(
        self,
        target_expense_ids: List[int],
        parameters: Dict[str, Any],
        estimated_impact: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evalúa riesgo de impacto financiero"""

        risk_level = SecurityRiskLevel.LOW
        requires_approval = False

        try:
            # Calcular impacto financiero total
            financial_query = """
            SELECT
                COUNT(*) as expense_count,
                COALESCE(SUM(monto_total), 0) as total_amount,
                COALESCE(AVG(monto_total), 0) as avg_amount,
                COALESCE(MAX(monto_total), 0) as max_amount
            FROM expenses
            WHERE id = ANY($1)
            """

            impact = await self.db.fetch_one(financial_query, target_expense_ids)

            total_amount = float(impact["total_amount"])
            expense_count = impact["expense_count"]

            # Umbrales de riesgo financiero
            if total_amount > 100000:  # > $100,000
                risk_level = SecurityRiskLevel.HIGH
                requires_approval = True
            elif total_amount > 50000:  # > $50,000
                risk_level = SecurityRiskLevel.MEDIUM
                requires_approval = True
            elif expense_count > 200:  # Muchos registros
                risk_level = SecurityRiskLevel.MEDIUM

            # Verificar cambios que afecten montos
            if "monto_total" in parameters:
                new_amount = float(parameters["monto_total"])
                if new_amount > 10000:  # Cambio a monto muy alto
                    risk_level = max(risk_level, SecurityRiskLevel.HIGH)
                    requires_approval = True

            return {
                "risk_level": risk_level,
                "requires_approval": requires_approval,
                "total_amount": total_amount,
                "expense_count": expense_count,
                "avg_amount": float(impact["avg_amount"]),
                "max_amount": float(impact["max_amount"])
            }

        except Exception as e:
            logger.error(f"Financial impact assessment failed: {e}")
            return {
                "risk_level": SecurityRiskLevel.MEDIUM,
                "requires_approval": True,
                "total_amount": 0,
                "expense_count": 0
            }

    def _calculate_security_score(
        self,
        risk_factors: List[str],
        violated_rules: List[str],
        record_count: int
    ) -> float:
        """Calcula score de seguridad (0.0-1.0)"""

        base_score = 1.0

        # Penalizar por factores de riesgo
        risk_penalty = len(risk_factors) * 0.1
        violation_penalty = len(violated_rules) * 0.15

        # Penalizar por tamaño de operación
        size_penalty = min(record_count / 1000, 0.2)  # Máximo 20% de penalización

        final_score = max(0.0, base_score - risk_penalty - violation_penalty - size_penalty)

        return round(final_score, 2)

    def _determine_overall_risk_level(
        self,
        risk_factors: List[str],
        security_score: float
    ) -> SecurityRiskLevel:
        """Determina el nivel de riesgo general"""

        if security_score <= 0.3:
            return SecurityRiskLevel.CRITICAL
        elif security_score <= 0.5:
            return SecurityRiskLevel.HIGH
        elif security_score <= 0.7 or len(risk_factors) >= 2:
            return SecurityRiskLevel.MEDIUM
        else:
            return SecurityRiskLevel.LOW

    def _determine_validation_result(
        self,
        violated_rules: List[str],
        required_approvals: List[str],
        risk_level: SecurityRiskLevel,
        security_score: float
    ) -> ValidationResult:
        """Determina el resultado de la validación"""

        # Bloquear si hay violaciones críticas
        critical_violations = [
            "insufficient_permissions",
            "rate_limit_exceeded",
            "validation_error",
            "cannot_delete_invoiced_expenses"
        ]

        if any(rule in critical_violations for rule in violated_rules):
            return ValidationResult.BLOCKED

        # Requerir aprobación si hay aprobaciones pendientes
        if required_approvals:
            return ValidationResult.REQUIRES_APPROVAL

        # Requerir MFA para riesgo alto
        if risk_level == SecurityRiskLevel.HIGH and security_score < 0.6:
            return ValidationResult.REQUIRES_MFA

        # Rechazar riesgo crítico
        if risk_level == SecurityRiskLevel.CRITICAL:
            return ValidationResult.REJECTED

        # Aprobar si todo está bien
        return ValidationResult.APPROVED

    # Métodos auxiliares

    async def _get_recent_user_actions(self, user_id: int, seconds: int) -> List[Dict[str, Any]]:
        """Obtiene acciones recientes del usuario"""
        try:
            query = """
            SELECT action_type, started_at, target_expense_ids
            FROM expense_action_audit
            WHERE user_id = $1
            AND started_at >= CURRENT_TIMESTAMP - INTERVAL '%s seconds'
            ORDER BY started_at DESC
            """

            return await self.db.fetch_all(query % seconds, user_id)
        except:
            return []

    async def _check_geographical_pattern(self, context: ActionContext) -> bool:
        """Verifica patrones geográficos sospechosos"""
        # Implementación simplificada - en producción usaría geolocalización
        return False

    async def _get_active_business_rules(self, company_id: str, action_type: ActionType) -> List[Dict[str, Any]]:
        """Obtiene reglas de negocio activas"""
        try:
            query = """
            SELECT rule_name, rule_config
            FROM expense_action_rules
            WHERE company_id = $1
            AND action_type = $2
            AND is_active = TRUE
            ORDER BY priority ASC
            """

            return await self.db.fetch_all(query, company_id, action_type.value)
        except:
            return []

    async def _evaluate_business_rule(self, rule: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Evalúa una regla de negocio específica"""
        # Implementación simplificada - en producción sería un engine de reglas
        return {
            "compliant": True,
            "requires_approval": False,
            "required_approvers": []
        }

    async def _check_user_ip_history(self, user_id: int, ip_address: str) -> Dict[str, Any]:
        """Verifica historial de IPs del usuario"""
        # Implementación simplificada
        return {"is_known": True}

    async def _get_user_operation_limits(self, user_id: int, action_type: ActionType) -> Dict[str, Any]:
        """Obtiene límites de operación del usuario"""
        return {
            "max_records_per_operation": 1000,
            "max_operations_per_hour": 10,
            "max_financial_impact": 100000
        }

    async def _check_account_security_status(self, user_id: int) -> Dict[str, Any]:
        """Verifica estado de seguridad de la cuenta"""
        try:
            query = """
            SELECT is_active, role, email_verified
            FROM users
            WHERE id = $1
            """

            user = await self.db.fetch_one(query, user_id)
            return {
                "is_active": user["is_active"] if user else False,
                "restrictions": []
            }
        except:
            return {"is_active": False, "restrictions": ["verification_failed"]}

    async def _configure_additional_verification(
        self,
        result_type: ValidationResult,
        risk_level: SecurityRiskLevel,
        context: ActionContext
    ) -> Dict[str, Any]:
        """Configura verificación adicional requerida"""

        if result_type == ValidationResult.REQUIRES_MFA:
            return {
                "mfa_required": True,
                "mfa_methods": ["totp", "sms"],
                "timeout_minutes": 5
            }
        elif result_type == ValidationResult.REQUIRES_APPROVAL:
            return {
                "approval_required": True,
                "approval_level": "supervisor" if risk_level == SecurityRiskLevel.MEDIUM else "admin",
                "timeout_hours": 24
            }

        return {}

    async def _log_security_validation(
        self,
        context: ActionContext,
        action_type: ActionType,
        record_count: int,
        result_type: ValidationResult,
        risk_level: SecurityRiskLevel
    ):
        """Log de auditoría de seguridad"""

        try:
            query = """
            INSERT INTO security_audit_log (
                user_id, company_id, session_id, ip_address,
                action_type, record_count, validation_result,
                risk_level, timestamp, user_agent
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """

            await self.db.execute(
                query,
                context.user_id,
                context.company_id,
                context.session_id,
                context.ip_address,
                action_type.value,
                record_count,
                result_type.value,
                risk_level.value,
                datetime.utcnow(),
                context.user_agent
            )

        except Exception as e:
            logger.error(f"Failed to log security validation: {e}")


# Singleton instance
security_validator = ExpenseSecurityValidator(None)  # Se inicializa con el adaptador de BD


# Helper functions

async def validate_bulk_expense_operation(
    action_type: ActionType,
    context: ActionContext,
    target_expense_ids: List[int],
    parameters: Dict[str, Any]
) -> SecurityValidationResult:
    """Helper para validar operación masiva"""
    return await security_validator.validate_bulk_operation(
        action_type, context, target_expense_ids, parameters, {}
    )


async def check_user_authorization(
    user_id: int,
    action_type: ActionType,
    company_id: str
) -> Dict[str, Any]:
    """Helper para verificar autorización"""
    return await security_validator.check_operation_authorization(
        user_id, action_type, company_id
    )