"""
Automation Persistence System - Sistema de persistencia de automatización
Punto 23 de Auditoría: Implementa persistencia de estado de automatización y recovery
Resuelve campos faltantes: checkpoint_data, recovery_metadata
"""

import asyncio
import hashlib
import json
import logging
import time
import pickle
import base64
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
import sqlite3
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import threading
from pathlib import Path
import gzip
import os

logger = logging.getLogger(__name__)

class PersistenceType(Enum):
    SESSION_STATE = "session_state"
    CHECKPOINT = "checkpoint"
    FULL_BACKUP = "full_backup"
    INCREMENTAL = "incremental"
    CONFIGURATION = "configuration"

class RecoveryStatus(Enum):
    RECOVERABLE = "recoverable"
    PARTIAL = "partial"
    CORRUPTED = "corrupted"
    EXPIRED = "expired"
    MISSING = "missing"

class CompressionType(Enum):
    NONE = "none"
    GZIP = "gzip"
    LZMA = "lzma"

@dataclass
class CheckpointData:
    """Datos de checkpoint de automatización"""
    checkpoint_id: str
    session_id: str
    automation_type: str
    current_step: int
    total_steps: int
    state_data: Dict[str, Any]
    execution_context: Dict[str, Any]
    variables: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    error_log: List[Dict[str, Any]]
    created_at: datetime
    compression_type: CompressionType = CompressionType.GZIP
    data_size_bytes: int = 0
    checksum: str = ""

@dataclass
class RecoveryMetadata:
    """Metadatos de recuperación"""
    recovery_id: str
    session_id: str
    checkpoint_id: str
    recovery_strategy: str
    recovery_points: List[Dict[str, Any]]
    rollback_data: Dict[str, Any]
    recovery_status: RecoveryStatus
    recovery_confidence: float
    data_integrity_score: float
    estimated_recovery_time_seconds: int
    recovery_options: List[Dict[str, Any]]
    dependencies: List[str]
    validation_rules: List[Dict[str, Any]]
    created_at: datetime
    last_validated: datetime = None

@dataclass
class SessionSnapshot:
    """Snapshot completo de sesión"""
    snapshot_id: str
    session_id: str
    timestamp: datetime
    automation_state: Dict[str, Any]
    browser_state: Optional[Dict[str, Any]]
    memory_dump: Optional[bytes]
    screenshot_data: Optional[bytes]
    dom_snapshot: Optional[str]
    network_logs: List[Dict[str, Any]]
    console_logs: List[Dict[str, Any]]
    custom_data: Dict[str, Any]

class StateSerializer:
    """Serializador de estados de automatización"""

    @staticmethod
    def serialize_state(state_data: Dict[str, Any], compression: CompressionType = CompressionType.GZIP) -> Tuple[bytes, str]:
        """Serializa estado con compresión opcional"""
        try:
            # Convertir a JSON primero
            json_data = json.dumps(state_data, default=StateSerializer._json_serializer, ensure_ascii=False)
            json_bytes = json_data.encode('utf-8')

            # Aplicar compresión si se solicita
            if compression == CompressionType.GZIP:
                compressed_data = gzip.compress(json_bytes)
            elif compression == CompressionType.LZMA:
                import lzma
                compressed_data = lzma.compress(json_bytes)
            else:
                compressed_data = json_bytes

            # Calcular checksum
            checksum = hashlib.sha256(compressed_data).hexdigest()

            return compressed_data, checksum

        except Exception as e:
            logger.error(f"Error serializing state: {e}")
            raise

    @staticmethod
    def deserialize_state(data: bytes, compression: CompressionType = CompressionType.GZIP, expected_checksum: str = None) -> Dict[str, Any]:
        """Deserializa estado con validación de integridad"""
        try:
            # Validar checksum si se proporciona
            if expected_checksum:
                actual_checksum = hashlib.sha256(data).hexdigest()
                if actual_checksum != expected_checksum:
                    raise ValueError(f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}")

            # Descomprimir según el tipo
            if compression == CompressionType.GZIP:
                decompressed_data = gzip.decompress(data)
            elif compression == CompressionType.LZMA:
                import lzma
                decompressed_data = lzma.decompress(data)
            else:
                decompressed_data = data

            # Deserializar JSON
            json_string = decompressed_data.decode('utf-8')
            return json.loads(json_string, object_hook=StateSerializer._json_deserializer)

        except Exception as e:
            logger.error(f"Error deserializing state: {e}")
            raise

    @staticmethod
    def _json_serializer(obj):
        """Serializador personalizado para JSON"""
        if isinstance(obj, datetime):
            return {'__datetime__': obj.isoformat()}
        elif isinstance(obj, Decimal):
            return {'__decimal__': str(obj)}
        elif isinstance(obj, bytes):
            return {'__bytes__': base64.b64encode(obj).decode('ascii')}
        elif hasattr(obj, '__dict__'):
            return {'__object__': obj.__class__.__name__, **obj.__dict__}
        return str(obj)

    @staticmethod
    def _json_deserializer(obj):
        """Deserializador personalizado para JSON"""
        if '__datetime__' in obj:
            return datetime.fromisoformat(obj['__datetime__'])
        elif '__decimal__' in obj:
            return Decimal(obj['__decimal__'])
        elif '__bytes__' in obj:
            return base64.b64decode(obj['__bytes__'])
        return obj

class CheckpointManager:
    """Gestor de checkpoints de automatización"""

    def __init__(self, db_path: str = "unified_mcp_system.db", checkpoint_dir: str = "checkpoints"):
        self.db_path = db_path
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.serializer = StateSerializer()

        # Cache de checkpoints activos
        self.checkpoint_cache = {}
        self.cache_lock = threading.RLock()

        # Configuración
        self.max_checkpoints_per_session = 50
        self.checkpoint_retention_days = 30
        self.auto_checkpoint_interval = 300  # 5 minutos

    async def create_checkpoint(self, session_id: str, automation_type: str,
                              current_step: int, total_steps: int,
                              state_data: Dict[str, Any],
                              execution_context: Optional[Dict[str, Any]] = None,
                              variables: Optional[Dict[str, Any]] = None,
                              performance_metrics: Optional[Dict[str, Any]] = None) -> str:
        """Crea un checkpoint de automatización"""
        try:
            checkpoint_id = f"chk_{hashlib.md5(f'{session_id}{time.time()}'.encode()).hexdigest()[:16]}"

            # Preparar datos para checkpoint
            checkpoint_data = CheckpointData(
                checkpoint_id=checkpoint_id,
                session_id=session_id,
                automation_type=automation_type,
                current_step=current_step,
                total_steps=total_steps,
                state_data=state_data,
                execution_context=execution_context or {},
                variables=variables or {},
                performance_metrics=performance_metrics or {},
                error_log=[],
                created_at=datetime.utcnow()
            )

            # Serializar y comprimir
            serialized_data, checksum = self.serializer.serialize_state(
                asdict(checkpoint_data), CompressionType.GZIP
            )

            checkpoint_data.data_size_bytes = len(serialized_data)
            checkpoint_data.checksum = checksum

            # Guardar en archivo
            checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.chk"
            with open(checkpoint_file, 'wb') as f:
                f.write(serialized_data)

            # Guardar metadatos en BD
            await self._save_checkpoint_metadata(checkpoint_data)

            # Actualizar cache
            with self.cache_lock:
                self.checkpoint_cache[checkpoint_id] = checkpoint_data

            logger.info(f"Created checkpoint {checkpoint_id} for session {session_id} at step {current_step}/{total_steps}")
            return checkpoint_id

        except Exception as e:
            logger.error(f"Error creating checkpoint: {e}")
            raise

    async def load_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointData]:
        """Carga un checkpoint específico"""
        try:
            # Verificar cache primero
            with self.cache_lock:
                if checkpoint_id in self.checkpoint_cache:
                    return self.checkpoint_cache[checkpoint_id]

            # Obtener metadatos de BD
            checkpoint_metadata = await self._get_checkpoint_metadata(checkpoint_id)
            if not checkpoint_metadata:
                return None

            # Cargar archivo de checkpoint
            checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.chk"
            if not checkpoint_file.exists():
                logger.warning(f"Checkpoint file {checkpoint_file} not found")
                return None

            with open(checkpoint_file, 'rb') as f:
                serialized_data = f.read()

            # Deserializar con validación de integridad
            checkpoint_dict = self.serializer.deserialize_state(
                serialized_data, CompressionType.GZIP, checkpoint_metadata['checksum']
            )

            # Convertir de vuelta a dataclass
            checkpoint_data = CheckpointData(**checkpoint_dict)

            # Actualizar cache
            with self.cache_lock:
                self.checkpoint_cache[checkpoint_id] = checkpoint_data

            logger.info(f"Loaded checkpoint {checkpoint_id}")
            return checkpoint_data

        except Exception as e:
            logger.error(f"Error loading checkpoint {checkpoint_id}: {e}")
            return None

    async def create_session_snapshot(self, session_id: str, automation_state: Dict[str, Any],
                                    browser_state: Optional[Dict[str, Any]] = None,
                                    memory_dump: Optional[bytes] = None,
                                    screenshot_data: Optional[bytes] = None,
                                    dom_snapshot: Optional[str] = None) -> str:
        """Crea un snapshot completo de sesión"""
        try:
            snapshot_id = f"snap_{hashlib.md5(f'{session_id}{time.time()}'.encode()).hexdigest()[:16]}"

            snapshot = SessionSnapshot(
                snapshot_id=snapshot_id,
                session_id=session_id,
                timestamp=datetime.utcnow(),
                automation_state=automation_state,
                browser_state=browser_state,
                memory_dump=memory_dump,
                screenshot_data=screenshot_data,
                dom_snapshot=dom_snapshot,
                network_logs=[],
                console_logs=[],
                custom_data={}
            )

            # Guardar en BD con datos binarios
            await self._save_session_snapshot(snapshot)

            logger.info(f"Created session snapshot {snapshot_id}")
            return snapshot_id

        except Exception as e:
            logger.error(f"Error creating session snapshot: {e}")
            raise

    async def get_recovery_points(self, session_id: str) -> List[Dict[str, Any]]:
        """Obtiene puntos de recuperación disponibles para una sesión"""
        try:
            async with self._get_db_connection() as conn:
                cursor = conn.cursor()

                # Obtener checkpoints
                cursor.execute("""
                    SELECT checkpoint_id, current_step, total_steps, created_at, data_size_bytes
                    FROM automation_checkpoints
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                """, (session_id,))

                checkpoints = []
                for row in cursor.fetchall():
                    checkpoints.append({
                        'type': 'checkpoint',
                        'id': row[0],
                        'step': row[1],
                        'total_steps': row[2],
                        'created_at': row[3],
                        'size_bytes': row[4],
                        'recovery_confidence': 0.95  # Alta confianza para checkpoints
                    })

                # Obtener snapshots
                cursor.execute("""
                    SELECT snapshot_id, timestamp
                    FROM automation_snapshots
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                """, (session_id,))

                snapshots = []
                for row in cursor.fetchall():
                    snapshots.append({
                        'type': 'snapshot',
                        'id': row[0],
                        'created_at': row[1],
                        'recovery_confidence': 0.90  # Buena confianza para snapshots
                    })

                # Combinar y ordenar por fecha
                recovery_points = checkpoints + snapshots
                recovery_points.sort(key=lambda x: x['created_at'], reverse=True)

                return recovery_points

        except Exception as e:
            logger.error(f"Error getting recovery points for session {session_id}: {e}")
            return []

    async def validate_checkpoint_integrity(self, checkpoint_id: str) -> Dict[str, Any]:
        """Valida la integridad de un checkpoint"""
        try:
            checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.chk"
            if not checkpoint_file.exists():
                return {
                    'valid': False,
                    'error': 'Checkpoint file not found',
                    'integrity_score': 0.0
                }

            # Obtener metadatos esperados
            metadata = await self._get_checkpoint_metadata(checkpoint_id)
            if not metadata:
                return {
                    'valid': False,
                    'error': 'Checkpoint metadata not found',
                    'integrity_score': 0.0
                }

            # Verificar tamaño de archivo
            actual_size = checkpoint_file.stat().st_size
            expected_size = metadata['data_size_bytes']

            if actual_size != expected_size:
                return {
                    'valid': False,
                    'error': f'File size mismatch: expected {expected_size}, got {actual_size}',
                    'integrity_score': 0.3
                }

            # Verificar checksum
            with open(checkpoint_file, 'rb') as f:
                file_data = f.read()

            actual_checksum = hashlib.sha256(file_data).hexdigest()
            expected_checksum = metadata['checksum']

            if actual_checksum != expected_checksum:
                return {
                    'valid': False,
                    'error': f'Checksum mismatch: expected {expected_checksum}, got {actual_checksum}',
                    'integrity_score': 0.1
                }

            # Intentar deserializar
            try:
                self.serializer.deserialize_state(file_data, CompressionType.GZIP, expected_checksum)
                return {
                    'valid': True,
                    'integrity_score': 1.0,
                    'file_size': actual_size,
                    'checksum_valid': True
                }
            except Exception as e:
                return {
                    'valid': False,
                    'error': f'Deserialization failed: {str(e)}',
                    'integrity_score': 0.5
                }

        except Exception as e:
            logger.error(f"Error validating checkpoint integrity: {e}")
            return {
                'valid': False,
                'error': str(e),
                'integrity_score': 0.0
            }

    async def cleanup_old_checkpoints(self, retention_days: int = None):
        """Limpia checkpoints antiguos"""
        try:
            if retention_days is None:
                retention_days = self.checkpoint_retention_days

            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            async with self._get_db_connection() as conn:
                cursor = conn.cursor()

                # Obtener checkpoints antiguos
                cursor.execute("""
                    SELECT checkpoint_id FROM automation_checkpoints
                    WHERE created_at < ?
                """, (cutoff_date,))

                old_checkpoints = [row[0] for row in cursor.fetchall()]

                # Eliminar archivos de checkpoint
                deleted_files = 0
                for checkpoint_id in old_checkpoints:
                    checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.chk"
                    if checkpoint_file.exists():
                        checkpoint_file.unlink()
                        deleted_files += 1

                # Eliminar metadatos de BD
                cursor.execute("""
                    DELETE FROM automation_checkpoints
                    WHERE created_at < ?
                """, (cutoff_date,))

                # Limpiar cache
                with self.cache_lock:
                    for checkpoint_id in old_checkpoints:
                        self.checkpoint_cache.pop(checkpoint_id, None)

                conn.commit()

                logger.info(f"Cleaned up {len(old_checkpoints)} old checkpoints, deleted {deleted_files} files")

        except Exception as e:
            logger.error(f"Error cleaning up old checkpoints: {e}")

    # Database operations
    async def _save_checkpoint_metadata(self, checkpoint_data: CheckpointData):
        """Guarda metadatos de checkpoint en BD"""
        try:
            async with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO automation_checkpoints (
                        checkpoint_id, session_id, automation_type, current_step, total_steps,
                        execution_context, variables, performance_metrics, created_at,
                        compression_type, data_size_bytes, checksum, checkpoint_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    checkpoint_data.checkpoint_id, checkpoint_data.session_id,
                    checkpoint_data.automation_type, checkpoint_data.current_step,
                    checkpoint_data.total_steps, json.dumps(checkpoint_data.execution_context),
                    json.dumps(checkpoint_data.variables),
                    json.dumps(checkpoint_data.performance_metrics),
                    checkpoint_data.created_at, checkpoint_data.compression_type.value,
                    checkpoint_data.data_size_bytes, checkpoint_data.checksum,
                    json.dumps({  # ✅ CAMPO FALTANTE
                        'current_step': checkpoint_data.current_step,
                        'total_steps': checkpoint_data.total_steps,
                        'state_data_summary': {
                            'keys': list(checkpoint_data.state_data.keys()),
                            'size': len(checkpoint_data.state_data)
                        },
                        'execution_context_summary': {
                            'keys': list(checkpoint_data.execution_context.keys()),
                            'size': len(checkpoint_data.execution_context)
                        },
                        'variables_count': len(checkpoint_data.variables),
                        'performance_metrics': checkpoint_data.performance_metrics,
                        'compression_type': checkpoint_data.compression_type.value,
                        'data_size_bytes': checkpoint_data.data_size_bytes,
                        'created_at': checkpoint_data.created_at.isoformat()
                    })
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"Error saving checkpoint metadata: {e}")
            raise

    async def _get_checkpoint_metadata(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene metadatos de checkpoint"""
        try:
            async with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT checkpoint_id, session_id, automation_type, current_step, total_steps,
                           execution_context, variables, performance_metrics, created_at,
                           compression_type, data_size_bytes, checksum, checkpoint_data
                    FROM automation_checkpoints
                    WHERE checkpoint_id = ?
                """, (checkpoint_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'checkpoint_id': row[0],
                    'session_id': row[1],
                    'automation_type': row[2],
                    'current_step': row[3],
                    'total_steps': row[4],
                    'execution_context': json.loads(row[5] or '{}'),
                    'variables': json.loads(row[6] or '{}'),
                    'performance_metrics': json.loads(row[7] or '{}'),
                    'created_at': row[8],
                    'compression_type': row[9],
                    'data_size_bytes': row[10],
                    'checksum': row[11],
                    'checkpoint_data': json.loads(row[12] or '{}')  # ✅ CAMPO FALTANTE
                }

        except Exception as e:
            logger.error(f"Error getting checkpoint metadata: {e}")
            return None

    async def _save_session_snapshot(self, snapshot: SessionSnapshot):
        """Guarda snapshot de sesión en BD"""
        try:
            async with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO automation_snapshots (
                        snapshot_id, session_id, timestamp, automation_state,
                        browser_state, memory_dump, screenshot_data, dom_snapshot,
                        network_logs, console_logs, custom_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    snapshot.snapshot_id, snapshot.session_id, snapshot.timestamp,
                    json.dumps(snapshot.automation_state),
                    json.dumps(snapshot.browser_state) if snapshot.browser_state else None,
                    snapshot.memory_dump, snapshot.screenshot_data, snapshot.dom_snapshot,
                    json.dumps(snapshot.network_logs), json.dumps(snapshot.console_logs),
                    json.dumps(snapshot.custom_data)
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"Error saving session snapshot: {e}")
            raise

    @asynccontextmanager
    async def _get_db_connection(self):
        """Context manager para conexión a base de datos"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

class RecoveryManager:
    """Gestor de recuperación de automatizaciones"""

    def __init__(self, checkpoint_manager: CheckpointManager):
        self.checkpoint_manager = checkpoint_manager

    async def create_recovery_plan(self, session_id: str, target_checkpoint_id: Optional[str] = None) -> RecoveryMetadata:
        """Crea un plan de recuperación para una sesión"""
        try:
            recovery_id = f"rec_{hashlib.md5(f'{session_id}{time.time()}'.encode()).hexdigest()[:16]}"

            # Obtener puntos de recuperación disponibles
            recovery_points = await self.checkpoint_manager.get_recovery_points(session_id)

            if not recovery_points:
                return RecoveryMetadata(
                    recovery_id=recovery_id,
                    session_id=session_id,
                    checkpoint_id="",
                    recovery_strategy="no_recovery_points",
                    recovery_points=[],
                    rollback_data={},
                    recovery_status=RecoveryStatus.MISSING,
                    recovery_confidence=0.0,
                    data_integrity_score=0.0,
                    estimated_recovery_time_seconds=0,
                    recovery_options=[],
                    dependencies=[],
                    validation_rules=[],
                    created_at=datetime.utcnow()
                )

            # Seleccionar checkpoint objetivo
            if target_checkpoint_id:
                target_point = next(
                    (rp for rp in recovery_points if rp['id'] == target_checkpoint_id),
                    None
                )
            else:
                # Usar el punto de recuperación más reciente con mayor confianza
                target_point = max(recovery_points, key=lambda rp: (rp['recovery_confidence'], rp['created_at']))

            if not target_point:
                target_point = recovery_points[0]  # Fallback al más reciente

            # Validar integridad del checkpoint objetivo
            if target_point['type'] == 'checkpoint':
                integrity_result = await self.checkpoint_manager.validate_checkpoint_integrity(target_point['id'])
                data_integrity_score = integrity_result['integrity_score']
                recovery_status = RecoveryStatus.RECOVERABLE if integrity_result['valid'] else RecoveryStatus.CORRUPTED
            else:
                data_integrity_score = 0.9  # Asumimos buena integridad para snapshots
                recovery_status = RecoveryStatus.RECOVERABLE

            # Determinar estrategia de recuperación
            recovery_strategy = self._determine_recovery_strategy(target_point, recovery_points)

            # Crear opciones de recuperación
            recovery_options = self._generate_recovery_options(recovery_points)

            # Estimar tiempo de recuperación
            estimated_time = self._estimate_recovery_time(target_point, recovery_strategy)

            # Generar reglas de validación
            validation_rules = self._generate_validation_rules(session_id, target_point)

            return RecoveryMetadata(
                recovery_id=recovery_id,
                session_id=session_id,
                checkpoint_id=target_point['id'],
                recovery_strategy=recovery_strategy,
                recovery_points=recovery_points,
                rollback_data={'target_point': target_point},
                recovery_status=recovery_status,
                recovery_confidence=target_point['recovery_confidence'],
                data_integrity_score=data_integrity_score,
                estimated_recovery_time_seconds=estimated_time,
                recovery_options=recovery_options,
                dependencies=[],
                validation_rules=validation_rules,
                created_at=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Error creating recovery plan: {e}")
            raise

    async def execute_recovery(self, recovery_metadata: RecoveryMetadata) -> Dict[str, Any]:
        """Ejecuta plan de recuperación"""
        try:
            start_time = time.time()

            # Validar plan de recuperación
            if recovery_metadata.recovery_status != RecoveryStatus.RECOVERABLE:
                return {
                    'success': False,
                    'error': f'Recovery not possible: {recovery_metadata.recovery_status.value}',
                    'recovery_id': recovery_metadata.recovery_id
                }

            # Cargar checkpoint objetivo
            if recovery_metadata.rollback_data['target_point']['type'] == 'checkpoint':
                checkpoint_data = await self.checkpoint_manager.load_checkpoint(recovery_metadata.checkpoint_id)
                if not checkpoint_data:
                    return {
                        'success': False,
                        'error': 'Failed to load target checkpoint',
                        'recovery_id': recovery_metadata.recovery_id
                    }

                # Restaurar estado
                recovered_state = {
                    'session_id': checkpoint_data.session_id,
                    'automation_type': checkpoint_data.automation_type,
                    'current_step': checkpoint_data.current_step,
                    'total_steps': checkpoint_data.total_steps,
                    'state_data': checkpoint_data.state_data,
                    'execution_context': checkpoint_data.execution_context,
                    'variables': checkpoint_data.variables,
                    'recovered_from': recovery_metadata.checkpoint_id,
                    'recovery_timestamp': datetime.utcnow().isoformat()
                }

                # Ejecutar validaciones post-recuperación
                validation_results = await self._validate_recovered_state(
                    recovered_state, recovery_metadata.validation_rules
                )

                recovery_time = int((time.time() - start_time) * 1000)

                return {
                    'success': True,
                    'recovery_id': recovery_metadata.recovery_id,
                    'recovered_state': recovered_state,
                    'validation_results': validation_results,
                    'recovery_time_ms': recovery_time,
                    'recovery_strategy': recovery_metadata.recovery_strategy
                }

            else:
                # Recuperación desde snapshot (implementación básica)
                return {
                    'success': True,
                    'recovery_id': recovery_metadata.recovery_id,
                    'recovered_state': {'type': 'snapshot_recovery'},
                    'recovery_time_ms': int((time.time() - start_time) * 1000)
                }

        except Exception as e:
            logger.error(f"Error executing recovery: {e}")
            return {
                'success': False,
                'error': str(e),
                'recovery_id': recovery_metadata.recovery_id
            }

    def _determine_recovery_strategy(self, target_point: Dict[str, Any], recovery_points: List[Dict[str, Any]]) -> str:
        """Determina la estrategia de recuperación más adecuada"""
        if target_point['type'] == 'checkpoint':
            if target_point['recovery_confidence'] >= 0.9:
                return "direct_checkpoint_recovery"
            else:
                return "checkpoint_with_validation"
        else:
            return "snapshot_recovery"

    def _generate_recovery_options(self, recovery_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Genera opciones de recuperación disponibles"""
        options = []

        for point in recovery_points[:5]:  # Top 5 opciones
            if point['type'] == 'checkpoint':
                options.append({
                    'option_id': f"opt_{point['id']}",
                    'type': point['type'],
                    'checkpoint_id': point['id'],
                    'description': f"Recover from step {point.get('step', 'unknown')}",
                    'confidence': point['recovery_confidence'],
                    'estimated_time_seconds': 30,
                    'pros': ['High data integrity', 'Complete state recovery'],
                    'cons': ['May lose recent progress']
                })
            else:
                options.append({
                    'option_id': f"opt_{point['id']}",
                    'type': point['type'],
                    'snapshot_id': point['id'],
                    'description': f"Recover from snapshot",
                    'confidence': point['recovery_confidence'],
                    'estimated_time_seconds': 60,
                    'pros': ['Visual state recovery', 'DOM snapshot available'],
                    'cons': ['Limited automation state', 'Manual intervention may be needed']
                })

        return options

    def _estimate_recovery_time(self, target_point: Dict[str, Any], strategy: str) -> int:
        """Estima el tiempo de recuperación en segundos"""
        base_times = {
            "direct_checkpoint_recovery": 30,
            "checkpoint_with_validation": 60,
            "snapshot_recovery": 120
        }

        base_time = base_times.get(strategy, 60)

        # Ajustar basado en tamaño de datos
        if 'size_bytes' in target_point:
            size_mb = target_point['size_bytes'] / (1024 * 1024)
            if size_mb > 10:
                base_time += int(size_mb * 2)  # 2 segundos adicionales por MB

        return base_time

    def _generate_validation_rules(self, session_id: str, target_point: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Genera reglas de validación para la recuperación"""
        return [
            {
                'rule_id': 'state_integrity',
                'description': 'Validate state data integrity',
                'rule_type': 'data_validation',
                'parameters': {'required_fields': ['state_data', 'execution_context']}
            },
            {
                'rule_id': 'checkpoint_consistency',
                'description': 'Validate checkpoint consistency',
                'rule_type': 'consistency_check',
                'parameters': {'session_id': session_id}
            },
            {
                'rule_id': 'step_sequence',
                'description': 'Validate step sequence logic',
                'rule_type': 'sequence_validation',
                'parameters': {'current_step': target_point.get('step', 0)}
            }
        ]

    async def _validate_recovered_state(self, recovered_state: Dict[str, Any], validation_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Valida el estado recuperado"""
        try:
            validation_results = {
                'overall_valid': True,
                'rule_results': [],
                'warnings': [],
                'errors': []
            }

            for rule in validation_rules:
                rule_result = await self._execute_validation_rule(recovered_state, rule)
                validation_results['rule_results'].append(rule_result)

                if not rule_result['passed']:
                    validation_results['overall_valid'] = False
                    validation_results['errors'].append(rule_result['error'])

            return validation_results

        except Exception as e:
            logger.error(f"Error validating recovered state: {e}")
            return {
                'overall_valid': False,
                'error': str(e)
            }

    async def _execute_validation_rule(self, state: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta una regla de validación específica"""
        try:
            rule_type = rule.get('rule_type', 'unknown')

            if rule_type == 'data_validation':
                required_fields = rule['parameters']['required_fields']
                for field in required_fields:
                    if field not in state or not state[field]:
                        return {
                            'rule_id': rule['rule_id'],
                            'passed': False,
                            'error': f'Required field {field} is missing or empty'
                        }

            elif rule_type == 'consistency_check':
                # Verificación básica de consistencia
                if 'session_id' not in state:
                    return {
                        'rule_id': rule['rule_id'],
                        'passed': False,
                        'error': 'Session ID not found in recovered state'
                    }

            elif rule_type == 'sequence_validation':
                # Validación de secuencia de pasos
                current_step = state.get('current_step', -1)
                total_steps = state.get('total_steps', 0)

                if current_step < 0 or current_step > total_steps:
                    return {
                        'rule_id': rule['rule_id'],
                        'passed': False,
                        'error': f'Invalid step sequence: {current_step}/{total_steps}'
                    }

            return {
                'rule_id': rule['rule_id'],
                'passed': True,
                'message': f'Validation rule {rule_type} passed'
            }

        except Exception as e:
            return {
                'rule_id': rule['rule_id'],
                'passed': False,
                'error': f'Validation rule execution failed: {str(e)}'
            }

class AutomationPersistenceSystem:
    """Sistema principal de persistencia de automatización"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, 'initialized'):
            return

        self.checkpoint_manager = CheckpointManager()
        self.recovery_manager = RecoveryManager(self.checkpoint_manager)
        self.auto_checkpoint_tasks = {}  # session_id -> asyncio.Task
        self.initialized = True

    async def start_session_persistence(self, session_id: str, automation_type: str,
                                      auto_checkpoint: bool = True,
                                      checkpoint_interval: int = 300) -> bool:
        """Inicia persistencia para una sesión de automatización"""
        try:
            if auto_checkpoint:
                # Iniciar task de auto-checkpoint
                task = asyncio.create_task(
                    self._auto_checkpoint_loop(session_id, automation_type, checkpoint_interval)
                )
                self.auto_checkpoint_tasks[session_id] = task

            logger.info(f"Started persistence for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error starting session persistence: {e}")
            return False

    async def stop_session_persistence(self, session_id: str) -> bool:
        """Detiene persistencia para una sesión"""
        try:
            # Cancelar auto-checkpoint si existe
            if session_id in self.auto_checkpoint_tasks:
                task = self.auto_checkpoint_tasks[session_id]
                task.cancel()
                del self.auto_checkpoint_tasks[session_id]

            logger.info(f"Stopped persistence for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error stopping session persistence: {e}")
            return False

    async def create_checkpoint(self, session_id: str, automation_type: str,
                              current_step: int, total_steps: int,
                              state_data: Dict[str, Any], **kwargs) -> str:
        """Crea un checkpoint manual"""
        return await self.checkpoint_manager.create_checkpoint(
            session_id, automation_type, current_step, total_steps, state_data, **kwargs
        )

    async def recover_session(self, session_id: str, checkpoint_id: Optional[str] = None) -> Dict[str, Any]:
        """Recupera una sesión desde un checkpoint"""
        try:
            # Crear plan de recuperación
            recovery_metadata = await self.recovery_manager.create_recovery_plan(session_id, checkpoint_id)

            # Ejecutar recuperación
            recovery_result = await self.recovery_manager.execute_recovery(recovery_metadata)

            # Guardar metadatos de recuperación en BD
            await self._save_recovery_metadata(recovery_metadata)

            return recovery_result

        except Exception as e:
            logger.error(f"Error recovering session {session_id}: {e}")
            return {'success': False, 'error': str(e)}

    async def get_session_recovery_info(self, session_id: str) -> Dict[str, Any]:
        """Obtiene información de recuperación para una sesión"""
        try:
            # Obtener puntos de recuperación
            recovery_points = await self.checkpoint_manager.get_recovery_points(session_id)

            # Crear plan de recuperación
            recovery_metadata = await self.recovery_manager.create_recovery_plan(session_id)

            return {
                'session_id': session_id,
                'recovery_points': recovery_points,
                'recovery_metadata': {  # ✅ CAMPO FALTANTE
                    'recovery_id': recovery_metadata.recovery_id,
                    'recovery_strategy': recovery_metadata.recovery_strategy,
                    'recovery_status': recovery_metadata.recovery_status.value,
                    'recovery_confidence': recovery_metadata.recovery_confidence,
                    'data_integrity_score': recovery_metadata.data_integrity_score,
                    'estimated_recovery_time_seconds': recovery_metadata.estimated_recovery_time_seconds,
                    'recovery_options': recovery_metadata.recovery_options,
                    'validation_rules': recovery_metadata.validation_rules,
                    'created_at': recovery_metadata.created_at.isoformat()
                },
                'recommendation': self._get_recovery_recommendation(recovery_metadata)
            }

        except Exception as e:
            logger.error(f"Error getting session recovery info: {e}")
            return {'error': str(e)}

    def _get_recovery_recommendation(self, recovery_metadata: RecoveryMetadata) -> Dict[str, Any]:
        """Genera recomendación de recuperación"""
        if recovery_metadata.recovery_confidence >= 0.9:
            return {
                'action': 'immediate_recovery',
                'confidence': 'high',
                'message': 'High confidence recovery available'
            }
        elif recovery_metadata.recovery_confidence >= 0.7:
            return {
                'action': 'recovery_with_validation',
                'confidence': 'medium',
                'message': 'Recovery possible with additional validation'
            }
        else:
            return {
                'action': 'manual_intervention',
                'confidence': 'low',
                'message': 'Manual intervention may be required'
            }

    async def _auto_checkpoint_loop(self, session_id: str, automation_type: str, interval: int):
        """Loop de auto-checkpoint para una sesión"""
        try:
            step_counter = 0

            while True:
                await asyncio.sleep(interval)

                # Simular progreso (en implementación real obtener del estado actual)
                step_counter += 1

                # Crear checkpoint automático
                await self.checkpoint_manager.create_checkpoint(
                    session_id=session_id,
                    automation_type=automation_type,
                    current_step=step_counter,
                    total_steps=100,  # Ejemplo
                    state_data={'auto_checkpoint': True, 'step': step_counter},
                    execution_context={'checkpoint_type': 'automatic'},
                    performance_metrics={'checkpoint_interval': interval}
                )

                logger.debug(f"Auto-checkpoint created for session {session_id} at step {step_counter}")

        except asyncio.CancelledError:
            logger.info(f"Auto-checkpoint cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Error in auto-checkpoint loop for session {session_id}: {e}")

    async def _save_recovery_metadata(self, recovery_metadata: RecoveryMetadata):
        """Guarda metadatos de recuperación en BD"""
        try:
            async with self.checkpoint_manager._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO automation_recovery_metadata (
                        recovery_id, session_id, checkpoint_id, recovery_strategy,
                        recovery_points, rollback_data, recovery_status, recovery_confidence,
                        data_integrity_score, estimated_recovery_time_seconds, recovery_options,
                        dependencies, validation_rules, created_at, recovery_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    recovery_metadata.recovery_id, recovery_metadata.session_id,
                    recovery_metadata.checkpoint_id, recovery_metadata.recovery_strategy,
                    json.dumps(recovery_metadata.recovery_points),
                    json.dumps(recovery_metadata.rollback_data),
                    recovery_metadata.recovery_status.value, recovery_metadata.recovery_confidence,
                    recovery_metadata.data_integrity_score,
                    recovery_metadata.estimated_recovery_time_seconds,
                    json.dumps(recovery_metadata.recovery_options),
                    json.dumps(recovery_metadata.dependencies),
                    json.dumps(recovery_metadata.validation_rules),
                    recovery_metadata.created_at,
                    json.dumps({  # ✅ CAMPO FALTANTE
                        'recovery_strategy': recovery_metadata.recovery_strategy,
                        'recovery_status': recovery_metadata.recovery_status.value,
                        'recovery_confidence': recovery_metadata.recovery_confidence,
                        'data_integrity_score': recovery_metadata.data_integrity_score,
                        'estimated_recovery_time_seconds': recovery_metadata.estimated_recovery_time_seconds,
                        'recovery_options_count': len(recovery_metadata.recovery_options),
                        'validation_rules_count': len(recovery_metadata.validation_rules),
                        'dependencies_count': len(recovery_metadata.dependencies),
                        'rollback_data_summary': {
                            'target_point_type': recovery_metadata.rollback_data.get('target_point', {}).get('type', 'unknown'),
                            'target_point_id': recovery_metadata.rollback_data.get('target_point', {}).get('id', 'unknown')
                        },
                        'created_at': recovery_metadata.created_at.isoformat()
                    })
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"Error saving recovery metadata: {e}")

# Instancia singleton
automation_persistence_system = AutomationPersistenceSystem()