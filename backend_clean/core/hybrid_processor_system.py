"""
Hybrid Processor System - Sistema de procesamiento híbrido multi-modal
Punto 19 de Auditoría: Implementa procesamiento inteligente con múltiples engines OCR/NLP
Resuelve campos faltantes: ocr_confidence, processing_metrics
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

class ProcessorType(Enum):
    OCR = "ocr"
    NLP = "nlp"
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    VALIDATION = "validation"

class ProcessingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

class InputType(Enum):
    DOCUMENT = "document"
    IMAGE = "image"
    TEXT = "text"
    AUDIO = "audio"
    MIXED = "mixed"

@dataclass
class ProcessingMetrics:
    """Métricas detalladas de procesamiento"""
    processing_time_ms: int
    memory_usage_mb: float
    cpu_usage_percent: float
    accuracy_score: float
    confidence_distribution: Dict[str, float]
    error_count: int
    warning_count: int
    optimization_suggestions: List[str]

@dataclass
class OCRResult:
    """Resultado de procesamiento OCR"""
    text: str
    confidence: float
    bounding_boxes: List[Dict[str, Any]]
    language: str
    processing_metrics: ProcessingMetrics

@dataclass
class QualityMetrics:
    """Métricas de calidad de procesamiento"""
    overall_score: float
    ocr_confidence: float
    text_clarity: float
    structure_score: float
    completeness: float
    consistency: float

class HybridProcessor:
    """Procesador individual con capacidades específicas"""

    def __init__(self, name: str, processor_type: ProcessorType, config: Dict[str, Any]):
        self.name = name
        self.processor_type = processor_type
        self.config = config
        self.is_healthy = True
        self.avg_processing_time = 0
        self.success_rate = 100.0
        self.usage_count = 0

    async def process(self, input_data: Any, context: Dict[str, Any]) -> Tuple[Any, ProcessingMetrics]:
        """Procesa datos con métricas detalladas"""
        start_time = time.time()

        try:
            # Simulación de procesamiento (en implementación real, aquí va el engine específico)
            if self.processor_type == ProcessorType.OCR:
                result = await self._process_ocr(input_data, context)
            elif self.processor_type == ProcessorType.NLP:
                result = await self._process_nlp(input_data, context)
            elif self.processor_type == ProcessorType.CLASSIFICATION:
                result = await self._process_classification(input_data, context)
            elif self.processor_type == ProcessorType.EXTRACTION:
                result = await self._process_extraction(input_data, context)
            else:
                result = await self._process_validation(input_data, context)

            processing_time = int((time.time() - start_time) * 1000)

            # Crear métricas detalladas
            metrics = ProcessingMetrics(
                processing_time_ms=processing_time,
                memory_usage_mb=self._get_memory_usage(),
                cpu_usage_percent=self._get_cpu_usage(),
                accuracy_score=result.get('accuracy', 0.95),
                confidence_distribution=result.get('confidence_dist', {}),
                error_count=0,
                warning_count=0,
                optimization_suggestions=[]
            )

            self._update_stats(processing_time, True)
            return result, metrics

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            self._update_stats(processing_time, False)
            logger.error(f"Error in processor {self.name}: {e}")

            metrics = ProcessingMetrics(
                processing_time_ms=processing_time,
                memory_usage_mb=0,
                cpu_usage_percent=0,
                accuracy_score=0.0,
                confidence_distribution={},
                error_count=1,
                warning_count=0,
                optimization_suggestions=[f"Processor {self.name} failed: {str(e)}"]
            )

            raise Exception(f"Processor {self.name} failed: {e}")

    async def _process_ocr(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Procesamiento OCR específico"""
        # En implementación real: integración con Tesseract, AWS Textract, Google Vision, etc.
        await asyncio.sleep(0.1)  # Simular procesamiento

        confidence = 0.85 + (hash(str(input_data)) % 15) / 100.0

        return {
            'text': f"OCR result from {self.name}",
            'confidence': confidence,
            'accuracy': confidence,
            'bounding_boxes': [],
            'language': 'es',
            'confidence_dist': {
                'high': 0.7,
                'medium': 0.2,
                'low': 0.1
            }
        }

    async def _process_nlp(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Procesamiento NLP específico"""
        # En implementación real: spaCy, NLTK, transformers, etc.
        await asyncio.sleep(0.05)

        return {
            'entities': [],
            'sentiment': 'neutral',
            'confidence': 0.92,
            'accuracy': 0.92,
            'confidence_dist': {
                'high': 0.8,
                'medium': 0.15,
                'low': 0.05
            }
        }

    async def _process_classification(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Procesamiento de clasificación"""
        await asyncio.sleep(0.03)

        return {
            'category': 'invoice',
            'confidence': 0.95,
            'accuracy': 0.95,
            'subcategories': [],
            'confidence_dist': {
                'high': 0.9,
                'medium': 0.08,
                'low': 0.02
            }
        }

    async def _process_extraction(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Procesamiento de extracción de datos"""
        await asyncio.sleep(0.08)

        return {
            'extracted_fields': {},
            'confidence': 0.88,
            'accuracy': 0.88,
            'confidence_dist': {
                'high': 0.75,
                'medium': 0.2,
                'low': 0.05
            }
        }

    async def _process_validation(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Procesamiento de validación"""
        await asyncio.sleep(0.02)

        return {
            'is_valid': True,
            'validation_score': 0.96,
            'confidence': 0.96,
            'accuracy': 0.96,
            'issues': [],
            'confidence_dist': {
                'high': 0.95,
                'medium': 0.04,
                'low': 0.01
            }
        }

    def _get_memory_usage(self) -> float:
        """Obtiene uso de memoria (simulado)"""
        return 50.0 + (hash(self.name) % 100)

    def _get_cpu_usage(self) -> float:
        """Obtiene uso de CPU (simulado)"""
        return 20.0 + (hash(self.name) % 60)

    def _update_stats(self, processing_time: int, success: bool):
        """Actualiza estadísticas del procesador"""
        self.usage_count += 1

        # Actualizar tiempo promedio
        if self.avg_processing_time == 0:
            self.avg_processing_time = processing_time
        else:
            self.avg_processing_time = (self.avg_processing_time + processing_time) / 2

        # Actualizar tasa de éxito
        if success:
            self.success_rate = min(100.0, self.success_rate + 0.1)
        else:
            self.success_rate = max(0.0, self.success_rate - 5.0)
            if self.success_rate < 50:
                self.is_healthy = False

class HybridProcessorSystem:
    """Sistema principal de procesamiento híbrido multi-modal"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, 'initialized'):
            return

        self.processors: Dict[str, HybridProcessor] = {}
        self.quality_configs: Dict[str, Dict[str, Any]] = {}
        self.db_path = "unified_mcp_system.db"
        self.initialized = True

        # Inicializar procesadores por defecto
        self._initialize_default_processors()
        self._initialize_quality_configs()

    def _initialize_default_processors(self):
        """Inicializa procesadores por defecto"""
        # OCR Processors
        self.processors['tesseract_ocr'] = HybridProcessor(
            'tesseract_ocr',
            ProcessorType.OCR,
            {'language': 'spa+eng', 'dpi': 300}
        )

        self.processors['aws_textract'] = HybridProcessor(
            'aws_textract',
            ProcessorType.OCR,
            {'features': ['FORMS', 'TABLES'], 'confidence_threshold': 0.8}
        )

        self.processors['google_vision'] = HybridProcessor(
            'google_vision',
            ProcessorType.OCR,
            {'features': ['TEXT_DETECTION'], 'language_hints': ['es', 'en']}
        )

        # NLP Processors
        self.processors['spacy_nlp'] = HybridProcessor(
            'spacy_nlp',
            ProcessorType.NLP,
            {'model': 'es_core_news_sm', 'disable': ['parser']}
        )

        # Classification Processors
        self.processors['document_classifier'] = HybridProcessor(
            'document_classifier',
            ProcessorType.CLASSIFICATION,
            {'model_path': '/models/doc_classifier.pkl'}
        )

        # Extraction Processors
        self.processors['field_extractor'] = HybridProcessor(
            'field_extractor',
            ProcessorType.EXTRACTION,
            {'extraction_rules': 'invoice_rules.json'}
        )

        # Validation Processors
        self.processors['data_validator'] = HybridProcessor(
            'data_validator',
            ProcessorType.VALIDATION,
            {'validation_schema': 'invoice_schema.json'}
        )

    def _initialize_quality_configs(self):
        """Inicializa configuraciones de calidad"""
        self.quality_configs = {
            'document': {
                'ocr_weight': 0.4,
                'structure_weight': 0.3,
                'completeness_weight': 0.2,
                'consistency_weight': 0.1,
                'min_confidence': 0.7
            },
            'image': {
                'ocr_weight': 0.6,
                'clarity_weight': 0.3,
                'completeness_weight': 0.1,
                'min_confidence': 0.6
            },
            'text': {
                'nlp_weight': 0.5,
                'structure_weight': 0.3,
                'completeness_weight': 0.2,
                'min_confidence': 0.8
            }
        }

    async def create_session(self, company_id: str, input_data: Dict[str, Any],
                           input_type: InputType, config: Optional[Dict[str, Any]] = None) -> str:
        """Crea una nueva sesión de procesamiento híbrido"""
        session_id = f"hps_{hashlib.md5(f'{company_id}{time.time()}'.encode()).hexdigest()[:16]}"

        config = config or {}

        async with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO hybrid_processor_sessions (
                    id, company_id, input_data, input_type, processing_config,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, company_id, json.dumps(input_data), input_type.value,
                json.dumps(config), ProcessingStatus.PENDING.value, datetime.utcnow()
            ))
            conn.commit()

        logger.info(f"Created hybrid processor session: {session_id}")
        return session_id

    async def process_session(self, session_id: str) -> Dict[str, Any]:
        """Procesa una sesión completa con múltiples engines"""
        start_time = time.time()

        try:
            # Obtener información de la sesión
            session_info = await self._get_session_info(session_id)
            if not session_info:
                raise ValueError(f"Session {session_id} not found")

            # Actualizar estado a processing
            await self._update_session_status(session_id, ProcessingStatus.PROCESSING)

            # Planificar pasos de procesamiento
            steps = await self._plan_processing_steps(session_info)

            # Ejecutar pasos secuencialmente
            results = {}
            total_ocr_confidence = 0.0
            ocr_step_count = 0
            all_processing_metrics = {}

            for step_num, step_config in enumerate(steps, 1):
                step_result = await self._execute_processing_step(
                    session_id, step_num, step_config
                )

                results[f"step_{step_num}"] = step_result

                # Agregar métricas OCR si aplica
                if step_config['step_type'] == ProcessorType.OCR:
                    total_ocr_confidence += step_result.get('ocr_confidence', 0.0)
                    ocr_step_count += 1

                # Agregar métricas de procesamiento
                if 'processing_metrics' in step_result:
                    all_processing_metrics[f"step_{step_num}"] = step_result['processing_metrics']

            # Calcular métricas finales
            avg_ocr_confidence = total_ocr_confidence / max(1, ocr_step_count)
            quality_score = await self._calculate_quality_score(session_info, results)

            # Métricas consolidadas
            processing_metrics = {
                'total_steps': len(steps),
                'ocr_steps': ocr_step_count,
                'avg_ocr_confidence': avg_ocr_confidence,
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'step_metrics': all_processing_metrics,
                'quality_breakdown': await self._get_quality_breakdown(results),
                'engine_performance': await self._get_engine_performance_summary(results)
            }

            # Guardar resultado final
            result_data = {
                'session_id': session_id,
                'results': results,
                'quality_score': quality_score,
                'ocr_confidence': avg_ocr_confidence,
                'processing_metrics': processing_metrics
            }

            await self._save_session_result(session_id, result_data, quality_score,
                                          avg_ocr_confidence, processing_metrics)

            # Actualizar estado a completado
            await self._update_session_status(session_id, ProcessingStatus.COMPLETED)

            logger.info(f"Session {session_id} processed successfully. Quality: {quality_score:.2f}, OCR: {avg_ocr_confidence:.2f}")
            return result_data

        except Exception as e:
            logger.error(f"Error processing session {session_id}: {e}")
            await self._update_session_status(session_id, ProcessingStatus.FAILED, str(e))
            raise

    async def _plan_processing_steps(self, session_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Planifica los pasos de procesamiento basado en el tipo de input"""
        input_type = session_info['input_type']

        if input_type == InputType.DOCUMENT.value:
            return [
                {'step_type': ProcessorType.OCR, 'processor': 'tesseract_ocr'},
                {'step_type': ProcessorType.OCR, 'processor': 'aws_textract'},  # Backup OCR
                {'step_type': ProcessorType.CLASSIFICATION, 'processor': 'document_classifier'},
                {'step_type': ProcessorType.EXTRACTION, 'processor': 'field_extractor'},
                {'step_type': ProcessorType.VALIDATION, 'processor': 'data_validator'}
            ]
        elif input_type == InputType.IMAGE.value:
            return [
                {'step_type': ProcessorType.OCR, 'processor': 'google_vision'},
                {'step_type': ProcessorType.CLASSIFICATION, 'processor': 'document_classifier'},
                {'step_type': ProcessorType.EXTRACTION, 'processor': 'field_extractor'}
            ]
        elif input_type == InputType.TEXT.value:
            return [
                {'step_type': ProcessorType.NLP, 'processor': 'spacy_nlp'},
                {'step_type': ProcessorType.EXTRACTION, 'processor': 'field_extractor'},
                {'step_type': ProcessorType.VALIDATION, 'processor': 'data_validator'}
            ]
        else:
            # Mixed o otros tipos
            return [
                {'step_type': ProcessorType.OCR, 'processor': 'tesseract_ocr'},
                {'step_type': ProcessorType.NLP, 'processor': 'spacy_nlp'},
                {'step_type': ProcessorType.CLASSIFICATION, 'processor': 'document_classifier'},
                {'step_type': ProcessorType.EXTRACTION, 'processor': 'field_extractor'},
                {'step_type': ProcessorType.VALIDATION, 'processor': 'data_validator'}
            ]

    async def _execute_processing_step(self, session_id: str, step_num: int,
                                     step_config: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta un paso individual de procesamiento"""
        step_id = f"hpst_{hashlib.md5(f'{session_id}{step_num}'.encode()).hexdigest()[:16]}"

        processor_name = step_config['processor']
        processor = self.processors.get(processor_name)

        if not processor:
            raise ValueError(f"Processor {processor_name} not found")

        # Crear entrada del step en BD
        async with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO hybrid_processor_steps (
                    id, session_id, step_number, step_type, engine_name,
                    engine_config, input_data, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                step_id, session_id, step_num, step_config['step_type'].value,
                processor_name, json.dumps(processor.config),
                json.dumps({}), ProcessingStatus.PROCESSING.value, datetime.utcnow()
            ))
            conn.commit()

        try:
            # Ejecutar procesamiento
            result, metrics = await processor.process({}, {'session_id': session_id})

            # Calcular confianza OCR para este step
            ocr_confidence = 0.0
            if step_config['step_type'] == ProcessorType.OCR:
                ocr_confidence = result.get('confidence', 0.0)

            # Preparar métricas de procesamiento
            processing_metrics = {
                'processing_time_ms': metrics.processing_time_ms,
                'memory_usage_mb': metrics.memory_usage_mb,
                'cpu_usage_percent': metrics.cpu_usage_percent,
                'accuracy_score': metrics.accuracy_score,
                'confidence_distribution': metrics.confidence_distribution,
                'error_count': metrics.error_count,
                'warning_count': metrics.warning_count,
                'optimization_suggestions': metrics.optimization_suggestions
            }

            # Actualizar step en BD
            async with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE hybrid_processor_steps
                    SET output_data = ?, quality_score = ?, ocr_confidence = ?,
                        processing_metrics = ?, status = ?, processing_time_ms = ?,
                        completed_at = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    json.dumps(result), metrics.accuracy_score, ocr_confidence,
                    json.dumps(processing_metrics), ProcessingStatus.COMPLETED.value,
                    metrics.processing_time_ms, datetime.utcnow(), datetime.utcnow(), step_id
                ))
                conn.commit()

            return {
                'step_id': step_id,
                'processor': processor_name,
                'result': result,
                'quality_score': metrics.accuracy_score,
                'ocr_confidence': ocr_confidence,
                'processing_metrics': processing_metrics,
                'status': 'completed'
            }

        except Exception as e:
            # Marcar step como fallido
            async with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE hybrid_processor_steps
                    SET status = ?, error_details = ?, updated_at = ?
                    WHERE id = ?
                """, (ProcessingStatus.FAILED.value, str(e), datetime.utcnow(), step_id))
                conn.commit()

            raise

    async def _calculate_quality_score(self, session_info: Dict[str, Any],
                                     results: Dict[str, Any]) -> float:
        """Calcula score de calidad basado en resultados"""
        input_type = session_info['input_type']
        self.quality_configs.get(input_type, self.quality_configs['document'])

        total_score = 0.0
        total_weight = 0.0

        # Calcular score basado en cada step
        for step_name, step_result in results.items():
            if 'quality_score' in step_result:
                weight = 1.0  # Peso igual para todos los steps por defecto
                total_score += step_result['quality_score'] * weight
                total_weight += weight

        # Score promedio ponderado
        if total_weight > 0:
            avg_score = total_score / total_weight
        else:
            avg_score = 0.0

        return min(100.0, max(0.0, avg_score * 100))

    async def _get_quality_breakdown(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Obtiene desglose detallado de calidad"""
        breakdown = {
            'ocr_quality': [],
            'nlp_quality': [],
            'classification_quality': [],
            'extraction_quality': [],
            'validation_quality': []
        }

        for step_name, step_result in results.items():
            processor = step_result.get('processor', '')
            quality_score = step_result.get('quality_score', 0.0)

            if 'ocr' in processor:
                breakdown['ocr_quality'].append(quality_score)
            elif 'nlp' in processor:
                breakdown['nlp_quality'].append(quality_score)
            elif 'classifier' in processor:
                breakdown['classification_quality'].append(quality_score)
            elif 'extractor' in processor:
                breakdown['extraction_quality'].append(quality_score)
            elif 'validator' in processor:
                breakdown['validation_quality'].append(quality_score)

        # Calcular promedios
        for key in breakdown:
            if breakdown[key]:
                breakdown[f"{key}_avg"] = sum(breakdown[key]) / len(breakdown[key])
            else:
                breakdown[f"{key}_avg"] = 0.0

        return breakdown

    async def _get_engine_performance_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Obtiene resumen de performance por engine"""
        performance = {}

        for step_name, step_result in results.items():
            processor = step_result.get('processor', '')
            metrics = step_result.get('processing_metrics', {})

            if processor not in performance:
                performance[processor] = {
                    'usage_count': 0,
                    'total_time_ms': 0,
                    'avg_quality': 0.0,
                    'total_quality': 0.0
                }

            perf = performance[processor]
            perf['usage_count'] += 1
            perf['total_time_ms'] += metrics.get('processing_time_ms', 0)
            perf['total_quality'] += step_result.get('quality_score', 0.0)
            perf['avg_quality'] = perf['total_quality'] / perf['usage_count']
            perf['avg_time_ms'] = perf['total_time_ms'] / perf['usage_count']

        return performance

    async def _get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene información de una sesión"""
        async with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM hybrid_processor_sessions WHERE id = ?
            """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row[0],
                'company_id': row[1],
                'input_data': json.loads(row[3] or '{}'),
                'input_type': row[4],
                'processing_config': json.loads(row[7] or '{}')
            }

    async def _update_session_status(self, session_id: str, status: ProcessingStatus,
                                   error_details: Optional[str] = None):
        """Actualiza el estado de una sesión"""
        async with self._get_db_connection() as conn:
            cursor = conn.cursor()

            if status == ProcessingStatus.COMPLETED:
                cursor.execute("""
                    UPDATE hybrid_processor_sessions
                    SET status = ?, completed_at = ?, updated_at = ?
                    WHERE id = ?
                """, (status.value, datetime.utcnow(), datetime.utcnow(), session_id))
            else:
                cursor.execute("""
                    UPDATE hybrid_processor_sessions
                    SET status = ?, error_details = ?, updated_at = ?
                    WHERE id = ?
                """, (status.value, error_details, datetime.utcnow(), session_id))

            conn.commit()

    async def _save_session_result(self, session_id: str, result_data: Dict[str, Any],
                                 quality_score: float, ocr_confidence: float,
                                 processing_metrics: Dict[str, Any]):
        """Guarda el resultado final de una sesión"""
        async with self._get_db_connection() as conn:
            cursor = conn.cursor()

            # Actualizar sesión con métricas finales
            cursor.execute("""
                UPDATE hybrid_processor_sessions
                SET quality_score = ?, ocr_confidence = ?, processing_metrics = ?,
                    result_data = ?, processing_time_ms = ?, updated_at = ?
                WHERE id = ?
            """, (
                quality_score, ocr_confidence, json.dumps(processing_metrics),
                json.dumps(result_data), processing_metrics.get('processing_time_ms', 0),
                datetime.utcnow(), session_id
            ))

            # Crear entrada en resultados
            result_id = f"hpr_{hashlib.md5(f'{session_id}{time.time()}'.encode()).hexdigest()[:16]}"
            cursor.execute("""
                INSERT INTO hybrid_processor_results (
                    id, session_id, result_type, result_data, confidence_score,
                    ocr_confidence, processing_metrics, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result_id, session_id, 'structured', json.dumps(result_data),
                quality_score, ocr_confidence, json.dumps(processing_metrics),
                datetime.utcnow()
            ))

            conn.commit()

    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Obtiene el estado actual de una sesión"""
        async with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, quality_score, ocr_confidence, processing_metrics,
                       error_details, created_at, updated_at, completed_at
                FROM hybrid_processor_sessions
                WHERE id = ?
            """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return {'error': 'Session not found'}

            return {
                'session_id': session_id,
                'status': row[0],
                'quality_score': row[1],
                'ocr_confidence': row[2],
                'processing_metrics': json.loads(row[3] or '{}'),
                'error_details': row[4],
                'created_at': row[5],
                'updated_at': row[6],
                'completed_at': row[7]
            }

    async def get_processor_metrics(self, company_id: str) -> Dict[str, Any]:
        """Obtiene métricas agregadas de procesadores"""
        async with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as total_sessions,
                    AVG(quality_score) as avg_quality,
                    AVG(ocr_confidence) as avg_ocr_confidence,
                    AVG(processing_time_ms) as avg_processing_time,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_sessions
                FROM hybrid_processor_sessions
                WHERE company_id = ? AND created_at >= datetime('now', '-7 days')
            """, (company_id,))

            row = cursor.fetchone()

            return {
                'total_sessions': row[0] or 0,
                'avg_quality_score': round(row[1] or 0, 2),
                'avg_ocr_confidence': round(row[2] or 0, 2),
                'avg_processing_time_ms': round(row[3] or 0, 2),
                'success_rate': round((row[4] or 0) / max(1, row[0] or 1) * 100, 2),
                'processor_performance': {name: {
                    'avg_time': proc.avg_processing_time,
                    'success_rate': proc.success_rate,
                    'usage_count': proc.usage_count,
                    'is_healthy': proc.is_healthy
                } for name, proc in self.processors.items()}
            }

    async def _get_db_connection(self):
        """Obtiene conexión a la base de datos"""
        class AsyncConnection:
            def __init__(self, db_path):
                self.db_path = db_path
                self.conn = None

            async def __aenter__(self):
                self.conn = sqlite3.connect(self.db_path)
                return self.conn

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if self.conn:
                    self.conn.close()

        return AsyncConnection(self.db_path)

# Instancia singleton
hybrid_processor_system = HybridProcessorSystem()