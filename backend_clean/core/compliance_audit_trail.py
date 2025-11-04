"""
Compliance & Audit Trail - Mitigación de riesgos de cumplimiento

Sistema inmutable de auditoría y cumplimiento regulatorio.
"""

import json
import sqlite3
import hashlib
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
from cryptography.fernet import Fernet
import base64

logger = logging.getLogger(__name__)

class AuditEventType(Enum):
    """Tipos de eventos de auditoría."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    DATA_ACCESS = "data_access"
    DATA_CREATION = "data_creation"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    AUTOMATION_STARTED = "automation_started"
    AUTOMATION_COMPLETED = "automation_completed"
    AUTOMATION_FAILED = "automation_failed"
    FEATURE_FLAG_CHANGED = "feature_flag_changed"
    SYSTEM_CONFIG_CHANGED = "system_config_changed"
    SECURITY_EVENT = "security_event"
    COMPLIANCE_CHECK = "compliance_check"
    DATA_EXPORT = "data_export"
    SENSITIVE_DATA_ACCESS = "sensitive_data_access"

class ComplianceStandard(Enum):
    """Estándares de cumplimiento."""
    GDPR = "gdpr"
    SOX = "sox"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"
    CFDI_SAT = "cfdi_sat"  # Específico para México

class SensitivityLevel(Enum):
    """Niveles de sensibilidad de datos."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

@dataclass
class AuditEvent:
    """Evento de auditoría inmutable."""
    id: str
    event_type: AuditEventType
    timestamp: datetime
    tenant_id: str
    user_id: Optional[str]
    session_id: Optional[str]
    resource_type: str
    resource_id: Optional[str]
    action: str
    details: Dict[str, Any]
    ip_address: Optional[str]
    user_agent: Optional[str]
    sensitivity_level: SensitivityLevel
    compliance_tags: List[ComplianceStandard]
    checksum: str
    encrypted_data: Optional[str]

@dataclass
class ComplianceRule:
    """Regla de cumplimiento."""
    id: str
    name: str
    standard: ComplianceStandard
    description: str
    required_events: List[AuditEventType]
    retention_days: int
    encryption_required: bool
    notification_required: bool
    validation_function: Optional[str]

class ImmutableAuditLogger:
    """Logger de auditoría inmutable con verificación de integridad."""

    def __init__(self, db_path: str = "expenses.db", encryption_key: str = None):
        self.db_path = db_path
        self.encryption_key = encryption_key or self._generate_encryption_key()
        self.cipher = Fernet(self.encryption_key.encode() if isinstance(self.encryption_key, str) else self.encryption_key)
        self.event_chain: List[str] = []  # Cadena de checksums para verificar integridad
        self._initialize_audit_tables()

    def _generate_encryption_key(self) -> bytes:
        """Generar clave de encriptación."""
        return Fernet.generate_key()

    def _initialize_audit_tables(self):
        """Inicializar tablas de auditoría."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Tabla principal de auditoría
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_events (
                        id TEXT PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        user_id TEXT,
                        session_id TEXT,
                        resource_type TEXT NOT NULL,
                        resource_id TEXT,
                        action TEXT NOT NULL,
                        details TEXT NOT NULL,
                        ip_address TEXT,
                        user_agent TEXT,
                        sensitivity_level TEXT NOT NULL,
                        compliance_tags TEXT NOT NULL,
                        checksum TEXT NOT NULL,
                        encrypted_data TEXT,
                        previous_checksum TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Tabla de cadena de integridad
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_integrity_chain (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT NOT NULL,
                        previous_hash TEXT,
                        current_hash TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (event_id) REFERENCES audit_events (id)
                    )
                """)

                # Tabla de reglas de cumplimiento
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS compliance_rules (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        standard TEXT NOT NULL,
                        description TEXT,
                        required_events TEXT NOT NULL,
                        retention_days INTEGER NOT NULL,
                        encryption_required BOOLEAN NOT NULL,
                        notification_required BOOLEAN NOT NULL,
                        validation_function TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Tabla de reportes de cumplimiento
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS compliance_reports (
                        id TEXT PRIMARY KEY,
                        standard TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        report_period_start TEXT NOT NULL,
                        report_period_end TEXT NOT NULL,
                        compliance_status TEXT NOT NULL,
                        violations TEXT,
                        recommendations TEXT,
                        generated_by TEXT,
                        generated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Índices para performance
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_tenant_timestamp
                    ON audit_events(tenant_id, timestamp)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_event_type
                    ON audit_events(event_type, timestamp)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_compliance
                    ON audit_events(compliance_tags, sensitivity_level)
                """)

                conn.commit()

        except Exception as e:
            logger.error(f"Error initializing audit tables: {e}")

    async def log_event(
        self,
        event_type: AuditEventType,
        tenant_id: str,
        resource_type: str,
        action: str,
        details: Dict[str, Any],
        user_id: str = None,
        session_id: str = None,
        resource_id: str = None,
        ip_address: str = None,
        user_agent: str = None,
        sensitivity_level: SensitivityLevel = SensitivityLevel.INTERNAL,
        compliance_tags: List[ComplianceStandard] = None
    ) -> str:
        """Registrar evento de auditoría."""
        try:
            # Generar ID único
            event_id = str(uuid.uuid4())

            # Obtener último checksum de la cadena
            previous_checksum = self._get_last_checksum()

            # Preparar datos para checksum
            event_data = {
                "id": event_id,
                "event_type": event_type.value,
                "timestamp": datetime.now().isoformat(),
                "tenant_id": tenant_id,
                "user_id": user_id,
                "session_id": session_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                "details": details,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "sensitivity_level": sensitivity_level.value,
                "compliance_tags": [tag.value for tag in (compliance_tags or [])],
                "previous_checksum": previous_checksum
            }

            # Calcular checksum del evento
            event_checksum = self._calculate_event_checksum(event_data)

            # Encriptar datos sensibles si es necesario
            encrypted_data = None
            if sensitivity_level in [SensitivityLevel.CONFIDENTIAL, SensitivityLevel.RESTRICTED]:
                sensitive_data = {
                    "details": details,
                    "user_id": user_id,
                    "ip_address": ip_address
                }
                encrypted_data = self.cipher.encrypt(json.dumps(sensitive_data).encode()).decode()

                # Limpiar datos sensibles de details para almacenamiento no encriptado
                details = {"encrypted": True, "sensitivity_level": sensitivity_level.value}

            # Crear evento de auditoría
            audit_event = AuditEvent(
                id=event_id,
                event_type=event_type,
                timestamp=datetime.now(),
                tenant_id=tenant_id,
                user_id=user_id if sensitivity_level not in [SensitivityLevel.CONFIDENTIAL, SensitivityLevel.RESTRICTED] else "[ENCRYPTED]",
                session_id=session_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                details=details,
                ip_address=ip_address if sensitivity_level not in [SensitivityLevel.CONFIDENTIAL, SensitivityLevel.RESTRICTED] else "[ENCRYPTED]",
                user_agent=user_agent,
                sensitivity_level=sensitivity_level,
                compliance_tags=compliance_tags or [],
                checksum=event_checksum,
                encrypted_data=encrypted_data
            )

            # Persistir evento
            await self._persist_audit_event(audit_event, previous_checksum)

            # Actualizar cadena de integridad
            self.event_chain.append(event_checksum)

            logger.info(f"Audit event logged: {event_type.value} for tenant {tenant_id}")
            return event_id

        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
            raise

    def _calculate_event_checksum(self, event_data: Dict[str, Any]) -> str:
        """Calcular checksum del evento."""
        # Crear string determinístico del evento
        event_str = json.dumps(event_data, sort_keys=True, default=str)
        return hashlib.sha256(event_str.encode()).hexdigest()

    def _get_last_checksum(self) -> Optional[str]:
        """Obtener último checksum de la cadena."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT current_hash FROM audit_integrity_chain
                    ORDER BY id DESC LIMIT 1
                """)
                result = cursor.fetchone()
                return result[0] if result else None

        except Exception as e:
            logger.error(f"Error getting last checksum: {e}")
            return None

    async def _persist_audit_event(self, event: AuditEvent, previous_checksum: Optional[str]):
        """Persistir evento de auditoría."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Insertar evento principal
                conn.execute("""
                    INSERT INTO audit_events (
                        id, event_type, timestamp, tenant_id, user_id, session_id,
                        resource_type, resource_id, action, details, ip_address,
                        user_agent, sensitivity_level, compliance_tags, checksum,
                        encrypted_data, previous_checksum
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    event.id,
                    event.event_type.value,
                    event.timestamp.isoformat(),
                    event.tenant_id,
                    event.user_id,
                    event.session_id,
                    event.resource_type,
                    event.resource_id,
                    event.action,
                    json.dumps(event.details),
                    event.ip_address,
                    event.user_agent,
                    event.sensitivity_level.value,
                    json.dumps([tag.value for tag in event.compliance_tags]),
                    event.checksum,
                    event.encrypted_data,
                    previous_checksum
                ])

                # Insertar en cadena de integridad
                conn.execute("""
                    INSERT INTO audit_integrity_chain (
                        event_id, previous_hash, current_hash, timestamp
                    ) VALUES (?, ?, ?, ?)
                """, [
                    event.id,
                    previous_checksum,
                    event.checksum,
                    event.timestamp.isoformat()
                ])

                conn.commit()

        except Exception as e:
            logger.error(f"Error persisting audit event: {e}")
            raise

    async def verify_audit_integrity(self, tenant_id: str = None) -> Dict[str, Any]:
        """Verificar integridad de la cadena de auditoría."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Query base
                query = """
                    SELECT id, checksum, previous_checksum, timestamp, tenant_id
                    FROM audit_events
                """
                params = []

                if tenant_id:
                    query += " WHERE tenant_id = ?"
                    params.append(tenant_id)

                query += " ORDER BY timestamp ASC"

                cursor = conn.execute(query, params)
                events = cursor.fetchall()

                # Verificar cadena
                verification_result = {
                    "total_events": len(events),
                    "verified_events": 0,
                    "integrity_violations": [],
                    "is_valid": True
                }

                previous_hash = None
                for event in events:
                    event_id, checksum, stored_previous_checksum, timestamp, event_tenant_id = event

                    # Verificar que el previous_checksum coincida con el hash anterior
                    if previous_hash is not None and stored_previous_checksum != previous_hash:
                        verification_result["integrity_violations"].append({
                            "event_id": event_id,
                            "timestamp": timestamp,
                            "tenant_id": event_tenant_id,
                            "violation": "Previous checksum mismatch",
                            "expected": previous_hash,
                            "found": stored_previous_checksum
                        })
                        verification_result["is_valid"] = False

                    # TODO: Recalcular checksum del evento y verificar que coincida
                    # (requeriría reconstruir el event_data original)

                    verification_result["verified_events"] += 1
                    previous_hash = checksum

                return verification_result

        except Exception as e:
            logger.error(f"Error verifying audit integrity: {e}")
            return {"error": str(e), "is_valid": False}

    async def get_audit_trail(
        self,
        tenant_id: str,
        start_date: datetime = None,
        end_date: datetime = None,
        event_types: List[AuditEventType] = None,
        resource_type: str = None,
        user_id: str = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Obtener trail de auditoría filtrado."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Construir query dinámico
                query = "SELECT * FROM audit_events WHERE tenant_id = ?"
                params = [tenant_id]

                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date.isoformat())

                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date.isoformat())

                if event_types:
                    event_type_placeholders = ",".join("?" * len(event_types))
                    query += f" AND event_type IN ({event_type_placeholders})"
                    params.extend([et.value for et in event_types])

                if resource_type:
                    query += " AND resource_type = ?"
                    params.append(resource_type)

                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor = conn.execute(query, params)
                columns = [description[0] for description in cursor.description]

                results = []
                for row in cursor.fetchall():
                    event_dict = dict(zip(columns, row))

                    # Desencriptar datos si es necesario y se tiene permisos
                    if event_dict["encrypted_data"]:
                        try:
                            decrypted_data = self.cipher.decrypt(event_dict["encrypted_data"].encode())
                            sensitive_data = json.loads(decrypted_data.decode())
                            event_dict["decrypted_details"] = sensitive_data
                        except Exception:
                            event_dict["decrypted_details"] = {"error": "Decryption failed or access denied"}

                    # Parsear JSON fields
                    event_dict["details"] = json.loads(event_dict["details"])
                    event_dict["compliance_tags"] = json.loads(event_dict["compliance_tags"])

                    results.append(event_dict)

                return results

        except Exception as e:
            logger.error(f"Error getting audit trail: {e}")
            return []

class ComplianceManager:
    """Gestor de cumplimiento regulatorio."""

    def __init__(self, audit_logger: ImmutableAuditLogger):
        self.audit_logger = audit_logger
        self.compliance_rules: Dict[str, ComplianceRule] = {}
        self._initialize_default_rules()

    def _initialize_default_rules(self):
        """Inicializar reglas de cumplimiento por defecto."""
        # GDPR
        gdpr_rule = ComplianceRule(
            id="gdpr_data_processing",
            name="GDPR Data Processing",
            standard=ComplianceStandard.GDPR,
            description="GDPR compliance for data processing activities",
            required_events=[
                AuditEventType.DATA_ACCESS,
                AuditEventType.DATA_CREATION,
                AuditEventType.DATA_MODIFICATION,
                AuditEventType.DATA_DELETION,
                AuditEventType.SENSITIVE_DATA_ACCESS
            ],
            retention_days=2555,  # 7 años
            encryption_required=True,
            notification_required=True,
            validation_function=None
        )
        self.compliance_rules[gdpr_rule.id] = gdpr_rule

        # SOX
        sox_rule = ComplianceRule(
            id="sox_financial_controls",
            name="SOX Financial Controls",
            standard=ComplianceStandard.SOX,
            description="Sarbanes-Oxley compliance for financial systems",
            required_events=[
                AuditEventType.DATA_MODIFICATION,
                AuditEventType.SYSTEM_CONFIG_CHANGED,
                AuditEventType.AUTOMATION_COMPLETED
            ],
            retention_days=2555,  # 7 años
            encryption_required=True,
            notification_required=True,
            validation_function=None
        )
        self.compliance_rules[sox_rule.id] = sox_rule

        # CFDI SAT (México)
        cfdi_rule = ComplianceRule(
            id="cfdi_sat_mexico",
            name="CFDI SAT Mexico",
            standard=ComplianceStandard.CFDI_SAT,
            description="Cumplimiento CFDI para SAT México",
            required_events=[
                AuditEventType.AUTOMATION_STARTED,
                AuditEventType.AUTOMATION_COMPLETED,
                AuditEventType.AUTOMATION_FAILED,
                AuditEventType.DATA_CREATION
            ],
            retention_days=1825,  # 5 años mínimo para SAT
            encryption_required=False,
            notification_required=False,
            validation_function=None
        )
        self.compliance_rules[cfdi_rule.id] = cfdi_rule

    async def check_compliance(
        self,
        tenant_id: str,
        standard: ComplianceStandard,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Verificar cumplimiento para un estándar específico."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)

            # Obtener reglas aplicables
            applicable_rules = [
                rule for rule in self.compliance_rules.values()
                if rule.standard == standard
            ]

            compliance_report = {
                "tenant_id": tenant_id,
                "standard": standard.value,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "rules_checked": len(applicable_rules),
                "violations": [],
                "recommendations": [],
                "compliance_score": 0.0,
                "status": "compliant"
            }

            total_checks = 0
            passed_checks = 0

            for rule in applicable_rules:
                rule_result = await self._check_rule_compliance(
                    tenant_id, rule, start_date, end_date
                )

                total_checks += rule_result["total_checks"]
                passed_checks += rule_result["passed_checks"]

                if rule_result["violations"]:
                    compliance_report["violations"].extend(rule_result["violations"])

                if rule_result["recommendations"]:
                    compliance_report["recommendations"].extend(rule_result["recommendations"])

            # Calcular score de cumplimiento
            if total_checks > 0:
                compliance_report["compliance_score"] = passed_checks / total_checks

            # Determinar status
            if compliance_report["compliance_score"] < 0.8:
                compliance_report["status"] = "non_compliant"
            elif compliance_report["compliance_score"] < 0.95:
                compliance_report["status"] = "partially_compliant"

            # Persistir reporte
            await self._save_compliance_report(compliance_report)

            return compliance_report

        except Exception as e:
            logger.error(f"Error checking compliance: {e}")
            return {"error": str(e), "status": "error"}

    async def _check_rule_compliance(
        self,
        tenant_id: str,
        rule: ComplianceRule,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Verificar cumplimiento de una regla específica."""
        result = {
            "rule_id": rule.id,
            "total_checks": 0,
            "passed_checks": 0,
            "violations": [],
            "recommendations": []
        }

        try:
            # Obtener eventos relevantes
            events = await self.audit_logger.get_audit_trail(
                tenant_id=tenant_id,
                start_date=start_date,
                end_date=end_date,
                event_types=rule.required_events,
                limit=10000
            )

            result["total_checks"] = len(events)

            # Verificar cada evento
            for event in events:
                event_compliant = True

                # Verificar encriptación si es requerida
                if rule.encryption_required:
                    if event["sensitivity_level"] in ["confidential", "restricted"]:
                        if not event["encrypted_data"]:
                            event_compliant = False
                            result["violations"].append({
                                "event_id": event["id"],
                                "violation": "Missing encryption for sensitive data",
                                "rule": rule.name
                            })

                # Verificar retención
                event_age_days = (datetime.now() - datetime.fromisoformat(event["timestamp"])).days
                if event_age_days > rule.retention_days:
                    result["recommendations"].append({
                        "event_id": event["id"],
                        "recommendation": f"Event older than {rule.retention_days} days, consider archival",
                        "rule": rule.name
                    })

                if event_compliant:
                    result["passed_checks"] += 1

            return result

        except Exception as e:
            logger.error(f"Error checking rule compliance for {rule.id}: {e}")
            return result

    async def _save_compliance_report(self, report: Dict[str, Any]):
        """Guardar reporte de cumplimiento."""
        try:
            with sqlite3.connect(self.audit_logger.db_path) as conn:
                conn.execute("""
                    INSERT INTO compliance_reports (
                        id, standard, tenant_id, report_period_start,
                        report_period_end, compliance_status, violations,
                        recommendations, generated_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    str(uuid.uuid4()),
                    report["standard"],
                    report["tenant_id"],
                    report["period_start"],
                    report["period_end"],
                    report["status"],
                    json.dumps(report["violations"]),
                    json.dumps(report["recommendations"]),
                    "system"
                ])

                conn.commit()

        except Exception as e:
            logger.error(f"Error saving compliance report: {e}")

    async def generate_compliance_export(
        self,
        tenant_id: str,
        standard: ComplianceStandard,
        start_date: datetime,
        end_date: datetime,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Generar export de cumplimiento para auditorías externas."""
        try:
            # Log del export para auditoría
            await self.audit_logger.log_event(
                event_type=AuditEventType.DATA_EXPORT,
                tenant_id=tenant_id,
                resource_type="compliance_data",
                action="export_compliance_report",
                details={
                    "standard": standard.value,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "format": format
                },
                sensitivity_level=SensitivityLevel.CONFIDENTIAL,
                compliance_tags=[standard]
            )

            # Obtener datos de auditoría
            audit_trail = await self.audit_logger.get_audit_trail(
                tenant_id=tenant_id,
                start_date=start_date,
                end_date=end_date,
                limit=50000
            )

            # Verificar integridad
            integrity_check = await self.audit_logger.verify_audit_integrity(tenant_id)

            # Generar reporte de cumplimiento
            compliance_check = await self.check_compliance(
                tenant_id, standard, (end_date - start_date).days
            )

            export_data = {
                "export_metadata": {
                    "tenant_id": tenant_id,
                    "standard": standard.value,
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                    "generated_at": datetime.now().isoformat(),
                    "format": format,
                    "total_events": len(audit_trail)
                },
                "integrity_verification": integrity_check,
                "compliance_assessment": compliance_check,
                "audit_events": audit_trail
            }

            return export_data

        except Exception as e:
            logger.error(f"Error generating compliance export: {e}")
            return {"error": str(e)}

# Global instances
audit_logger = ImmutableAuditLogger()
compliance_manager = ComplianceManager(audit_logger)

# Decorador para auto-logging de auditoría
def audit_trail(
    event_type: AuditEventType,
    resource_type: str,
    action: str = None,
    sensitivity_level: SensitivityLevel = SensitivityLevel.INTERNAL,
    compliance_tags: List[ComplianceStandard] = None
):
    """Decorador para logging automático de auditoría."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extraer contexto
            tenant_id = kwargs.get("tenant_id") or kwargs.get("company_id")
            user_id = kwargs.get("user_id")
            session_id = kwargs.get("session_id")

            # Ejecutar función
            start_time = datetime.now()
            success = True
            error = None

            try:
                result = await func(*args, **kwargs)

                # Log evento exitoso
                await audit_logger.log_event(
                    event_type=event_type,
                    tenant_id=tenant_id or "system",
                    resource_type=resource_type,
                    action=action or func.__name__,
                    details={
                        "function": func.__name__,
                        "duration_ms": (datetime.now() - start_time).total_seconds() * 1000,
                        "success": True,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys())
                    },
                    user_id=user_id,
                    session_id=session_id,
                    sensitivity_level=sensitivity_level,
                    compliance_tags=compliance_tags
                )

                return result

            except Exception as e:
                success = False
                error = str(e)

                # Log evento fallido
                await audit_logger.log_event(
                    event_type=AuditEventType.SECURITY_EVENT,
                    tenant_id=tenant_id or "system",
                    resource_type=resource_type,
                    action=f"{action or func.__name__}_failed",
                    details={
                        "function": func.__name__,
                        "duration_ms": (datetime.now() - start_time).total_seconds() * 1000,
                        "success": False,
                        "error": error,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys())
                    },
                    user_id=user_id,
                    session_id=session_id,
                    sensitivity_level=SensitivityLevel.CONFIDENTIAL,
                    compliance_tags=compliance_tags or []
                )

                raise

        return wrapper
    return decorator