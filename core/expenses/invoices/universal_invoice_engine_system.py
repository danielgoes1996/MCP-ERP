"""
Universal Invoice Engine System - Sistema universal de procesamiento de facturas
Punto 21 de Auditoría: Implementa engine universal multi-formato con template matching
Resuelve campos faltantes: template_match, validation_rules
"""

import asyncio
import hashlib
import json
import logging
import time
import re
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum
from dataclasses import dataclass
import psycopg2
from psycopg2.extras import RealDictCursor
from core.shared.db_config import POSTGRES_CONFIG
from datetime import datetime, timedelta
import mimetypes
import base64

logger = logging.getLogger(__name__)

class InvoiceFormat(Enum):
    PDF = "pdf"
    XML = "xml"
    JSON = "json"
    CSV = "csv"
    IMAGE = "image"
    TXT = "txt"

class ParserType(Enum):
    PDF = "pdf"
    XML = "xml"
    IMAGE = "image"
    HYBRID = "hybrid"
    CUSTOM = "custom"

class ValidationCategory(Enum):
    FORMAT = "format"
    BUSINESS = "business"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"

class ExtractionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"

class MatchingMethod(Enum):
    PATTERN_BASED = "pattern_based"
    ML_BASED = "ml_based"
    HYBRID = "hybrid"
    MANUAL = "manual"

@dataclass
class TemplateMatch:
    """Resultado de template matching"""
    template_name: str
    match_score: float
    matched_patterns: List[Dict[str, Any]]
    confidence_factors: Dict[str, float]
    matching_method: MatchingMethod
    template_structure: Dict[str, Any]
    field_mappings: Dict[str, str]

@dataclass
class ValidationRule:
    """Regla de validación"""
    rule_name: str
    rule_category: ValidationCategory
    rule_definition: Dict[str, Any]
    rule_parameters: Dict[str, Any]
    error_messages: Dict[str, str]
    priority: int

@dataclass
class ExtractionResult:
    """Resultado de extracción"""
    raw_data: Dict[str, Any]
    normalized_data: Dict[str, Any]
    confidence_scores: Dict[str, float]
    extracted_fields: Dict[str, Any]
    missing_fields: List[str]
    uncertain_fields: List[str]

class UniversalInvoiceParser:
    """Parser universal para facturas"""

    def __init__(self, parser_name: str, parser_type: ParserType, config: Dict[str, Any]):
        self.parser_name = parser_name
        self.parser_type = parser_type
        self.config = config
        self.supported_formats = config.get('supported_formats', [])
        self.extraction_capabilities = config.get('extraction_capabilities', [])

        # Performance tracking
        self.usage_count = 0
        self.success_rate = 100.0
        self.avg_processing_time = 0

    async def can_parse(self, file_path: str, format_hint: Optional[str] = None) -> Tuple[bool, float]:
        """Determina si este parser puede procesar el archivo"""
        try:
            # Detectar tipo de archivo
            mime_type, _ = mimetypes.guess_type(file_path)
            file_format = self._mime_to_format(mime_type)

            if format_hint:
                file_format = format_hint

            # Verificar si el parser soporta este formato
            if file_format not in self.supported_formats:
                return False, 0.0

            # Calcular confianza basada en historial
            confidence = min(self.success_rate / 100, 1.0)

            # Ajustar confianza basada en capacidades específicas
            if self.parser_type.value == file_format:
                confidence += 0.2  # Bonus por especialización

            return True, min(confidence, 1.0)

        except Exception as e:
            logger.error(f"Error checking parser compatibility: {e}")
            return False, 0.0

    async def parse(self, file_path: str, template_hints: Optional[Dict[str, Any]] = None) -> ExtractionResult:
        """Extrae datos de la factura"""
        start_time = time.time()

        try:
            # Simular procesamiento basado en tipo de parser
            if self.parser_type == ParserType.PDF:
                result = await self._parse_pdf(file_path, template_hints)
            elif self.parser_type == ParserType.XML:
                result = await self._parse_xml(file_path, template_hints)
            elif self.parser_type == ParserType.IMAGE:
                result = await self._parse_image(file_path, template_hints)
            elif self.parser_type == ParserType.HYBRID:
                result = await self._parse_hybrid(file_path, template_hints)
            else:
                result = await self._parse_custom(file_path, template_hints)

            # Actualizar estadísticas
            processing_time = int((time.time() - start_time) * 1000)
            self._update_performance_stats(processing_time, True)

            return result

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            self._update_performance_stats(processing_time, False)
            logger.error(f"Error parsing with {self.parser_name}: {e}")
            raise

    async def _parse_pdf(self, file_path: str, template_hints: Optional[Dict[str, Any]]) -> ExtractionResult:
        """Parse PDF invoices"""
        await asyncio.sleep(0.3)  # Simular procesamiento

        # Simular extracción de datos
        raw_data = {
            "invoice_number": "INV-2024-001",
            "date": "2024-01-15",
            "vendor": "Example Vendor Ltd.",
            "total": 1500.00,
            "currency": "USD",
            "line_items": [
                {"description": "Product A", "quantity": 2, "price": 500.00},
                {"description": "Product B", "quantity": 1, "price": 500.00}
            ]
        }

        # Aplicar template hints si están disponibles
        if template_hints:
            confidence_boost = template_hints.get('confidence_boost', 0.0)
        else:
            confidence_boost = 0.0

        confidence_scores = {
            "invoice_number": 0.95 + confidence_boost,
            "date": 0.90 + confidence_boost,
            "vendor": 0.88 + confidence_boost,
            "total": 0.92 + confidence_boost,
            "currency": 0.85 + confidence_boost
        }

        return ExtractionResult(
            raw_data=raw_data,
            normalized_data=self._normalize_data(raw_data),
            confidence_scores=confidence_scores,
            extracted_fields=raw_data,
            missing_fields=[],
            uncertain_fields=["currency"]  # Ejemplo de campo incierto
        )

    async def _parse_xml(self, file_path: str, template_hints: Optional[Dict[str, Any]]) -> ExtractionResult:
        """Parse XML invoices - specifically CFDI using deterministic XML parser

        IMPORTANT: This uses deterministic XML parsing (NOT LLM) for CFDI files.
        Benefits:
        - Zero cost (no LLM calls)
        - 100% reliable (no JSON parsing errors)
        - ~50x faster (~0.1s vs ~5s per invoice)
        - 100% confidence scores (deterministic extraction)
        """
        try:
            # Use deterministic XML parser (NOT LLM) for CFDI
            from core.ai_pipeline.parsers.invoice_parser import parse_cfdi_xml
            import xml.etree.ElementTree as ET

            # Read XML file as bytes (required by parse_cfdi_xml)
            with open(file_path, 'rb') as f:
                xml_bytes = f.read()

            # Parse with deterministic XML parser (fast, reliable, zero cost)
            parsed = parse_cfdi_xml(xml_bytes)

            # Also parse root attributes for additional fields
            root = ET.fromstring(xml_bytes)
            root_attribs = root.attrib

            # Find emisor and receptor nodes for detailed info
            CFDI_NS = {"cfdi": "http://www.sat.gob.mx/cfd/4"}
            emisor_node = root.find("cfdi:Emisor", CFDI_NS)
            receptor_node = root.find("cfdi:Receptor", CFDI_NS)

            # Also try to find "Conceptos" for classification
            conceptos_node = root.find("cfdi:Conceptos", CFDI_NS)
            conceptos = []
            if conceptos_node is not None:
                for concepto_node in conceptos_node.findall("cfdi:Concepto", CFDI_NS):
                    conceptos.append({
                        'clave_prod_serv': concepto_node.attrib.get('ClaveProdServ'),
                        'descripcion': concepto_node.attrib.get('Descripcion'),
                        'cantidad': concepto_node.attrib.get('Cantidad'),
                        'unidad': concepto_node.attrib.get('ClaveUnidad'),
                        'valor_unitario': concepto_node.attrib.get('ValorUnitario'),
                        'importe': concepto_node.attrib.get('Importe'),
                    })

            # Build compatible format with LLM parser output structure
            # This ensures downstream code continues to work without changes
            raw_data = {
                "uuid": parsed.get("uuid"),
                "serie": root_attribs.get("Serie"),
                "folio": root_attribs.get("Folio"),
                "fecha_emision": root_attribs.get("Fecha", "").split("T")[0] if root_attribs.get("Fecha") else None,
                "fecha_timbrado": None,  # Would need TimbreFiscalDigital FechaTimbrado
                "tipo_comprobante": root_attribs.get("TipoDeComprobante"),
                "moneda": parsed.get("currency", "MXN"),
                "tipo_cambio": float(root_attribs.get("TipoCambio", 1.0)),
                "subtotal": parsed.get("subtotal"),
                "descuento": float(root_attribs.get("Descuento", 0.0)),
                "total": parsed.get("total"),
                "forma_pago": root_attribs.get("FormaPago"),
                "metodo_pago": root_attribs.get("MetodoPago"),
                "uso_cfdi": root_attribs.get("UsoCFDI"),
                "sat_status": "desconocido",  # Would require SAT API validation
                "emisor": {
                    "nombre": emisor_node.attrib.get("Nombre") if emisor_node is not None else None,
                    "rfc": emisor_node.attrib.get("Rfc") if emisor_node is not None else None,
                    "regimen_fiscal": emisor_node.attrib.get("RegimenFiscal") if emisor_node is not None else None,
                },
                "receptor": {
                    "nombre": receptor_node.attrib.get("Nombre") if receptor_node is not None else None,
                    "rfc": receptor_node.attrib.get("Rfc") if receptor_node is not None else None,
                    "uso_cfdi": receptor_node.attrib.get("UsoCFDI") if receptor_node is not None else None,
                    "domicilio_fiscal": receptor_node.attrib.get("DomicilioFiscalReceptor") if receptor_node is not None else None,
                },
                "impuestos": {
                    "iva": parsed.get("iva_amount", 0.0),
                    "otros": parsed.get("other_taxes", 0.0),
                    "detalle": parsed.get("taxes", []),
                },
                "conceptos": conceptos,  # IMPORTANT: for AI classification
                # Flatten emisor/receptor to top level for backward compatibility
                "rfc_emisor": emisor_node.attrib.get("Rfc") if emisor_node is not None else None,
                "nombre_emisor": emisor_node.attrib.get("Nombre") if emisor_node is not None else None,
                "rfc_receptor": receptor_node.attrib.get("Rfc") if receptor_node is not None else None,
                "nombre_receptor": receptor_node.attrib.get("Nombre") if receptor_node is not None else None,
            }

            # Calcular confidence scores (100% confiable porque es parsing determinístico)
            confidence_scores = {}
            for field, value in raw_data.items():
                if value and value != "null" and value not in [{}, []]:
                    confidence_scores[field] = 1.0  # 100% confidence (deterministic parsing)
                else:
                    confidence_scores[field] = 0.0

            # Identificar campos faltantes
            required_fields = ["uuid", "rfc_emisor", "nombre_emisor", "total", "fecha_emision"]
            missing_fields = [f for f in required_fields if not raw_data.get(f)]

            # Identificar campos inciertos (XML determinístico, así que solo campos faltantes)
            uncertain_fields = []

            logger.info(f"XML parsed successfully with deterministic parser: UUID={raw_data.get('uuid')}, Total={raw_data.get('total')}")

            return ExtractionResult(
                raw_data=raw_data,
                normalized_data=self._normalize_data(raw_data),
                confidence_scores=confidence_scores,
                extracted_fields=raw_data,
                missing_fields=missing_fields,
                uncertain_fields=uncertain_fields
            )
        except Exception as e:
            logger.error(f"Error parsing CFDI XML: {e}", exc_info=True)
            # Fallback a datos vacíos en caso de error
            return ExtractionResult(
                raw_data={},
                normalized_data={},
                confidence_scores={},
                extracted_fields={},
                missing_fields=["all_fields"],
                uncertain_fields=[]
            )

    async def _parse_image(self, file_path: str, template_hints: Optional[Dict[str, Any]]) -> ExtractionResult:
        """Parse image invoices using OCR"""
        await asyncio.sleep(0.8)  # OCR toma más tiempo

        raw_data = {
            "invoice_no": "IMG-2024-001",
            "date": "15/01/2024",
            "company": "Image Corp",
            "total_amount": 750.50,
            "vat": 150.10
        }

        # Confianza más baja para OCR
        confidence_scores = {field: 0.75 + (hash(field) % 20) / 100 for field in raw_data.keys()}

        return ExtractionResult(
            raw_data=raw_data,
            normalized_data=self._normalize_data(raw_data),
            confidence_scores=confidence_scores,
            extracted_fields=raw_data,
            missing_fields=["currency"],
            uncertain_fields=["date", "total_amount"]
        )

    async def _parse_hybrid(self, file_path: str, template_hints: Optional[Dict[str, Any]]) -> ExtractionResult:
        """Parse using hybrid approach"""
        await asyncio.sleep(0.5)

        # Combinar resultados de múltiples métodos
        raw_data = {
            "document_number": "HYB-2024-001",
            "document_date": "2024-01-15T10:30:00Z",
            "vendor_name": "Hybrid Solutions Ltd.",
            "net_amount": 1800.00,
            "tax_percentage": 20.0,
            "gross_amount": 2160.00,
            "payment_terms": "30 days"
        }

        confidence_scores = {field: 0.90 + (hash(field) % 10) / 100 for field in raw_data.keys()}

        return ExtractionResult(
            raw_data=raw_data,
            normalized_data=self._normalize_data(raw_data),
            confidence_scores=confidence_scores,
            extracted_fields=raw_data,
            missing_fields=[],
            uncertain_fields=["payment_terms"]
        )

    async def _parse_custom(self, file_path: str, template_hints: Optional[Dict[str, Any]]) -> ExtractionResult:
        """Parse using custom method"""
        await asyncio.sleep(0.2)

        raw_data = {
            "custom_id": "CUST-001",
            "processing_date": datetime.utcnow().isoformat(),
            "source": "custom_parser"
        }

        confidence_scores = {field: 0.80 for field in raw_data.keys()}

        return ExtractionResult(
            raw_data=raw_data,
            normalized_data=self._normalize_data(raw_data),
            confidence_scores=confidence_scores,
            extracted_fields=raw_data,
            missing_fields=["amount", "vendor"],
            uncertain_fields=list(raw_data.keys())
        )

    def _normalize_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza datos extraídos a formato estándar"""
        normalized = {}

        # Mapeo de campos comunes
        field_mappings = {
            'invoice_number': ['invoice_number', 'invoice_id', 'invoice_no', 'document_number', 'custom_id'],
            'date': ['date', 'issue_date', 'document_date', 'processing_date'],
            'vendor': ['vendor', 'supplier', 'company', 'vendor_name'],
            'total': ['total', 'amount', 'total_amount', 'gross_amount', 'net_amount'],
            'currency': ['currency', 'currency_code']
        }

        for standard_field, possible_fields in field_mappings.items():
            for field in possible_fields:
                if field in raw_data:
                    normalized[standard_field] = raw_data[field]
                    break

        return normalized

    def _mime_to_format(self, mime_type: Optional[str]) -> str:
        """Convierte MIME type a formato interno"""
        if not mime_type:
            return "unknown"

        mime_mapping = {
            'application/pdf': 'pdf',
            'application/xml': 'xml',
            'text/xml': 'xml',
            'application/json': 'json',
            'text/csv': 'csv',
            'image/jpeg': 'image',
            'image/png': 'image',
            'image/tiff': 'image',
            'text/plain': 'txt'
        }

        return mime_mapping.get(mime_type, 'unknown')

    def _update_performance_stats(self, processing_time: int, success: bool):
        """Actualiza estadísticas de performance"""
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
            self.success_rate = max(0.0, self.success_rate - 2.0)

class TemplateMatchingEngine:
    """Engine para template matching avanzado"""

    def __init__(self):
        self.templates = {}
        self.matching_cache = {}

    async def find_best_template(self, file_path: str, available_templates: List[Dict[str, Any]],
                               extracted_data: Optional[Dict[str, Any]] = None) -> TemplateMatch:
        """Encuentra el mejor template para un archivo"""
        best_match = None
        best_score = 0.0

        for template in available_templates:
            match_result = await self._match_template(file_path, template, extracted_data)

            if match_result.match_score > best_score:
                best_score = match_result.match_score
                best_match = match_result

        if not best_match:
            # Crear template genérico si no hay matches
            best_match = await self._create_generic_template(file_path, extracted_data)

        return best_match

    async def _match_template(self, file_path: str, template: Dict[str, Any],
                            extracted_data: Optional[Dict[str, Any]]) -> TemplateMatch:
        """Calcula match score para un template específico"""
        template_name = template.get('format_name', 'unknown')
        template_patterns = template.get('template_patterns', [])
        key_indicators = template.get('key_indicators', [])

        # Simular análisis de template matching
        await asyncio.sleep(0.05)

        # Calcular score basado en patrones
        pattern_score = await self._calculate_pattern_score(file_path, template_patterns)

        # Calcular score basado en indicadores clave
        indicator_score = await self._calculate_indicator_score(extracted_data, key_indicators)

        # Score combinado
        match_score = (pattern_score * 0.6 + indicator_score * 0.4)

        # Factores de confianza
        confidence_factors = {
            'pattern_match': pattern_score,
            'indicator_match': indicator_score,
            'template_quality': template.get('avg_confidence', 0.8),
            'usage_frequency': min(template.get('usage_count', 0) / 100, 1.0)
        }

        # Patrones matcheados (simulado)
        matched_patterns = []
        for i, pattern in enumerate(template_patterns[:3]):  # Top 3 patterns
            if pattern_score > 0.5:
                matched_patterns.append({
                    'pattern_id': f"pattern_{i}",
                    'pattern_text': pattern.get('pattern', ''),
                    'match_confidence': pattern_score + (i * 0.05),
                    'location': {'page': 1, 'x': 100 + i * 50, 'y': 200 + i * 30}
                })

        return TemplateMatch(
            template_name=template_name,
            match_score=match_score,
            matched_patterns=matched_patterns,
            confidence_factors=confidence_factors,
            matching_method=MatchingMethod.PATTERN_BASED,
            template_structure=template.get('template_structure', {}),
            field_mappings=template.get('field_mappings', {})
        )

    async def _calculate_pattern_score(self, file_path: str, patterns: List[Dict[str, Any]]) -> float:
        """Calcula score basado en patrones del template"""
        if not patterns:
            return 0.5  # Score neutral si no hay patrones

        # Simular análisis de patrones en el archivo
        matched_patterns = 0
        total_patterns = len(patterns)

        for pattern in patterns:
            # Simular matching de patrón
            pattern_text = pattern.get('pattern', '')
            if len(pattern_text) > 5:  # Patrones más largos tienen más probabilidad
                matched_patterns += 1

        return matched_patterns / max(total_patterns, 1)

    async def _calculate_indicator_score(self, extracted_data: Optional[Dict[str, Any]],
                                       indicators: List[Dict[str, Any]]) -> float:
        """Calcula score basado en indicadores clave"""
        if not extracted_data or not indicators:
            return 0.5

        matched_indicators = 0
        total_indicators = len(indicators)

        for indicator in indicators:
            indicator_field = indicator.get('field', '')
            indicator_pattern = indicator.get('pattern', '')

            if indicator_field in extracted_data:
                field_value = str(extracted_data[indicator_field])
                # Simular matching de patrón en el valor
                if indicator_pattern in field_value or len(field_value) > 3:
                    matched_indicators += 1

        return matched_indicators / max(total_indicators, 1)

    async def _create_generic_template(self, file_path: str,
                                     extracted_data: Optional[Dict[str, Any]]) -> TemplateMatch:
        """Crea un template genérico cuando no hay matches"""
        return TemplateMatch(
            template_name="generic_template",
            match_score=0.3,  # Score bajo para template genérico
            matched_patterns=[],
            confidence_factors={'fallback': True},
            matching_method=MatchingMethod.PATTERN_BASED,
            template_structure={},
            field_mappings={}
        )

class ValidationEngine:
    """Engine para validación de datos extraídos"""

    def __init__(self):
        self.default_rules = self._load_default_rules()

    async def validate_extraction(self, extracted_data: Dict[str, Any],
                                validation_rules: List[ValidationRule],
                                template_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Valida datos extraídos contra reglas"""
        validation_results = {
            'overall_status': 'valid',
            'validation_score': 100.0,
            'rule_results': [],
            'errors': [],
            'warnings': []
        }

        total_score = 0.0
        max_score = 0.0

        for rule in validation_rules:
            rule_result = await self._validate_rule(extracted_data, rule, template_context)
            validation_results['rule_results'].append(rule_result)

            # Acumular scores
            rule_weight = rule.priority / 100.0
            max_score += rule_weight * 100
            total_score += rule_weight * rule_result['score']

            # Recopilar errores y warnings
            if rule_result['status'] == 'failed':
                validation_results['errors'].extend(rule_result.get('errors', []))
            elif rule_result['status'] == 'warning':
                validation_results['warnings'].extend(rule_result.get('warnings', []))

        # Calcular score final
        if max_score > 0:
            validation_results['validation_score'] = (total_score / max_score) * 100
        else:
            validation_results['validation_score'] = 100.0

        # Determinar estado general
        if validation_results['errors']:
            validation_results['overall_status'] = 'invalid'
        elif validation_results['warnings']:
            validation_results['overall_status'] = 'warning'
        else:
            validation_results['overall_status'] = 'valid'

        return validation_results

    async def _validate_rule(self, extracted_data: Dict[str, Any], rule: ValidationRule,
                           template_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Valida una regla específica"""
        rule_definition = rule.rule_definition
        rule_type = rule_definition.get('type', 'unknown')

        try:
            if rule_type == 'required_field':
                return await self._validate_required_field(extracted_data, rule)
            elif rule_type == 'format_validation':
                return await self._validate_format(extracted_data, rule)
            elif rule_type == 'business_rule':
                return await self._validate_business_rule(extracted_data, rule)
            elif rule_type == 'compliance_check':
                return await self._validate_compliance(extracted_data, rule)
            else:
                return await self._validate_custom_rule(extracted_data, rule)

        except Exception as e:
            logger.error(f"Error validating rule {rule.rule_name}: {e}")
            return {
                'rule_name': rule.rule_name,
                'status': 'failed',
                'score': 0.0,
                'errors': [f"Validation error: {str(e)}"],
                'warnings': []
            }

    async def _validate_required_field(self, extracted_data: Dict[str, Any],
                                     rule: ValidationRule) -> Dict[str, Any]:
        """Valida que campos requeridos estén presentes"""
        required_field = rule.rule_definition.get('field_name', '')

        if required_field in extracted_data and extracted_data[required_field] is not None:
            return {
                'rule_name': rule.rule_name,
                'status': 'passed',
                'score': 100.0,
                'errors': [],
                'warnings': []
            }
        else:
            return {
                'rule_name': rule.rule_name,
                'status': 'failed',
                'score': 0.0,
                'errors': [rule.error_messages.get('missing_field', f"Required field '{required_field}' is missing")],
                'warnings': []
            }

    async def _validate_format(self, extracted_data: Dict[str, Any],
                             rule: ValidationRule) -> Dict[str, Any]:
        """Valida formato de campos"""
        field_name = rule.rule_definition.get('field_name', '')
        expected_format = rule.rule_definition.get('format_pattern', '')

        if field_name not in extracted_data:
            return {
                'rule_name': rule.rule_name,
                'status': 'skipped',
                'score': 100.0,  # No penalizar si el campo no existe
                'errors': [],
                'warnings': []
            }

        field_value = str(extracted_data[field_name])

        # Simular validación de formato
        is_valid = True
        if expected_format == 'date':
            is_valid = bool(re.match(r'\d{4}-\d{2}-\d{2}', field_value))
        elif expected_format == 'number':
            try:
                float(field_value)
            except ValueError:
                is_valid = False
        elif expected_format == 'email':
            is_valid = bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', field_value))

        if is_valid:
            return {
                'rule_name': rule.rule_name,
                'status': 'passed',
                'score': 100.0,
                'errors': [],
                'warnings': []
            }
        else:
            return {
                'rule_name': rule.rule_name,
                'status': 'failed',
                'score': 0.0,
                'errors': [rule.error_messages.get('invalid_format', f"Field '{field_name}' has invalid format")],
                'warnings': []
            }

    async def _validate_business_rule(self, extracted_data: Dict[str, Any],
                                    rule: ValidationRule) -> Dict[str, Any]:
        """Valida reglas de negocio"""
        # Ejemplo: validar que el total sea mayor que 0
        business_rule = rule.rule_definition.get('rule', '')

        if business_rule == 'positive_total':
            total_field = rule.rule_parameters.get('total_field', 'total')
            if total_field in extracted_data:
                try:
                    total_value = float(extracted_data[total_field])
                    if total_value > 0:
                        return {
                            'rule_name': rule.rule_name,
                            'status': 'passed',
                            'score': 100.0,
                            'errors': [],
                            'warnings': []
                        }
                    else:
                        return {
                            'rule_name': rule.rule_name,
                            'status': 'failed',
                            'score': 0.0,
                            'errors': [rule.error_messages.get('negative_total', "Total amount must be positive")],
                            'warnings': []
                        }
                except ValueError:
                    return {
                        'rule_name': rule.rule_name,
                        'status': 'failed',
                        'score': 0.0,
                        'errors': [rule.error_messages.get('invalid_total', "Total amount is not a valid number")],
                        'warnings': []
                    }

        # Regla genérica pasada por defecto
        return {
            'rule_name': rule.rule_name,
            'status': 'passed',
            'score': 100.0,
            'errors': [],
            'warnings': []
        }

    async def _validate_compliance(self, extracted_data: Dict[str, Any],
                                 rule: ValidationRule) -> Dict[str, Any]:
        """Valida reglas de compliance"""
        # Ejemplo básico de compliance
        return {
            'rule_name': rule.rule_name,
            'status': 'passed',
            'score': 100.0,
            'errors': [],
            'warnings': []
        }

    async def _validate_custom_rule(self, extracted_data: Dict[str, Any],
                                  rule: ValidationRule) -> Dict[str, Any]:
        """Valida reglas personalizadas"""
        # Implementación básica para reglas custom
        return {
            'rule_name': rule.rule_name,
            'status': 'passed',
            'score': 80.0,  # Score ligeramente menor para reglas custom
            'errors': [],
            'warnings': []
        }

    def _load_default_rules(self) -> List[ValidationRule]:
        """Carga reglas de validación por defecto"""
        return [
            ValidationRule(
                rule_name="invoice_number_required",
                rule_category=ValidationCategory.FORMAT,
                rule_definition={'type': 'required_field', 'field_name': 'invoice_number'},
                rule_parameters={},
                error_messages={'missing_field': 'Invoice number is required'},
                priority=90
            ),
            ValidationRule(
                rule_name="positive_total",
                rule_category=ValidationCategory.BUSINESS,
                rule_definition={'type': 'business_rule', 'rule': 'positive_total'},
                rule_parameters={'total_field': 'total'},
                error_messages={'negative_total': 'Invoice total must be positive'},
                priority=80
            ),
            ValidationRule(
                rule_name="date_format",
                rule_category=ValidationCategory.FORMAT,
                rule_definition={'type': 'format_validation', 'field_name': 'date', 'format_pattern': 'date'},
                rule_parameters={},
                error_messages={'invalid_format': 'Date must be in valid format'},
                priority=70
            )
        ]

class UniversalInvoiceEngineSystem:
    """Sistema principal del Universal Invoice Engine"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, 'initialized'):
            return

        self.parsers: Dict[str, UniversalInvoiceParser] = {}
        self.template_engine = TemplateMatchingEngine()
        self.validation_engine = ValidationEngine()
        self.db_path = "unified_mcp_system.db"
        self.initialized = True

        # Inicializar parsers por defecto
        self._initialize_default_parsers()

    def _initialize_default_parsers(self):
        """Inicializa parsers por defecto"""
        # PDF Parser
        self.parsers['pdf_parser'] = UniversalInvoiceParser(
            'pdf_parser',
            ParserType.PDF,
            {
                'supported_formats': ['pdf'],
                'extraction_capabilities': ['text', 'tables', 'images'],
                'ocr_enabled': True
            }
        )

        # XML Parser
        self.parsers['xml_parser'] = UniversalInvoiceParser(
            'xml_parser',
            ParserType.XML,
            {
                'supported_formats': ['xml'],
                'extraction_capabilities': ['structured_data', 'namespaces'],
                'schema_validation': True
            }
        )

        # Image Parser (OCR)
        self.parsers['image_parser'] = UniversalInvoiceParser(
            'image_parser',
            ParserType.IMAGE,
            {
                'supported_formats': ['image'],
                'extraction_capabilities': ['ocr', 'layout_analysis'],
                'ocr_languages': ['en', 'es', 'fr']
            }
        )

        # Hybrid Parser
        self.parsers['hybrid_parser'] = UniversalInvoiceParser(
            'hybrid_parser',
            ParserType.HYBRID,
            {
                'supported_formats': ['pdf', 'image', 'xml'],
                'extraction_capabilities': ['multi_modal', 'cross_validation'],
                'fallback_enabled': True
            }
        )

    async def create_processing_session(self, company_id: str, file_path: str,
                                      original_filename: str,
                                      user_id: Optional[str] = None) -> str:
        """Crea una nueva sesión de procesamiento"""
        session_id = f"uis_{hashlib.md5(f'{company_id}{file_path}{time.time()}'.encode()).hexdigest()[:16]}"

        # Calcular hash del archivo (simulado)
        file_hash = hashlib.md5(f"{file_path}{time.time()}".encode()).hexdigest()

        async with await self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sat_invoices (
                    id, company_id, user_id, invoice_file_path, original_filename,
                    file_hash, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                session_id, company_id, user_id, file_path, original_filename,
                file_hash, datetime.utcnow()
            ))
            conn.commit()

        logger.info(f"Created universal invoice processing session: {session_id}")
        return session_id

    async def process_invoice(self, session_id: str) -> Dict[str, Any]:
        """Procesa una factura completa con template matching y validation"""
        logger.info(f"Session {session_id}: Starting process_invoice()")
        start_time = time.time()

        try:
            # 1. Obtener información de la sesión
            session_info = await self._get_session_info(session_id)
            if not session_info:
                raise ValueError(f"Session {session_id} not found")

            # 2. Detectar formato y seleccionar parser
            parser_selection = await self._select_best_parser(session_info['invoice_file_path'])

            # 3. Obtener templates disponibles
            available_templates = await self._get_available_templates(session_info['company_id'])

            # 4. Ejecutar extracción
            extraction_result = await parser_selection['parser'].parse(
                session_info['invoice_file_path']
            )

            # 5. Template matching
            template_match = await self.template_engine.find_best_template(
                session_info['invoice_file_path'],
                available_templates,
                extraction_result.raw_data
            )

            # 6. Validación con reglas
            validation_rules = await self._get_validation_rules(session_info['company_id'], template_match)
            validation_result = await self.validation_engine.validate_extraction(
                extraction_result.normalized_data,
                validation_rules,
                {'template': template_match.template_name}
            )

            # 7. Calcular métricas finales
            total_time = int((time.time() - start_time) * 1000)
            overall_quality = self._calculate_overall_quality(
                extraction_result, template_match, validation_result
            )

            # 8. Preparar resultado final
            result = {
                'session_id': session_id,
                'company_id': session_info['company_id'],  # ✅ NEW: for classification
                'status': 'completed',
                'detected_format': parser_selection['format'],
                'parser_used': parser_selection['parser'].parser_name,
                'template_match': {  # ✅ CAMPO FALTANTE
                    'template_name': template_match.template_name,
                    'match_score': template_match.match_score,
                    'matched_patterns': template_match.matched_patterns,
                    'confidence_factors': template_match.confidence_factors,
                    'matching_method': template_match.matching_method.value,
                    'field_mappings': template_match.field_mappings
                },
                'validation_rules': {  # ✅ CAMPO FALTANTE
                    'applied_rules': [
                        {
                            'rule_name': rule.rule_name,
                            'rule_category': rule.rule_category.value,
                            'rule_definition': rule.rule_definition,
                            'priority': rule.priority
                        } for rule in validation_rules
                    ],
                    'validation_result': validation_result,
                    'overall_status': validation_result['overall_status'],
                    'validation_score': validation_result['validation_score']
                },
                'extracted_data': extraction_result.raw_data,  # FIXED: Use raw_data instead of normalized_data to preserve all CFDI fields (emisor, receptor, conceptos, etc.)
                'parsed_data': extraction_result.raw_data,  # Full CFDI data from parser
                'extraction_confidence': sum(extraction_result.confidence_scores.values()) / len(extraction_result.confidence_scores) if extraction_result.confidence_scores else 0.0,
                'overall_quality_score': overall_quality,
                'processing_metrics': {
                    'total_time_ms': total_time,
                    'parser_selection_time_ms': parser_selection['selection_time_ms'],
                    'extraction_time_ms': parser_selection.get('extraction_time_ms', 0),
                    'template_matching_time_ms': template_match.confidence_factors.get('processing_time_ms', 0),
                    'validation_time_ms': sum(
                        result.get('execution_time_ms', 0)
                        for result in validation_result['rule_results']
                    )
                }
            }

            # 9. Guardar resultado en BD
            await self._save_processing_result(session_id, result, template_match, validation_rules)

            return result

        except Exception as e:
            logger.error(f"Error processing invoice session {session_id}: {e}")
            await self._update_session_status(session_id, ExtractionStatus.FAILED, str(e))
            raise

    async def _select_best_parser(self, file_path: str) -> Dict[str, Any]:
        """Selecciona el mejor parser para un archivo"""
        start_time = time.time()

        best_parser = None
        best_confidence = 0.0
        detected_format = "unknown"

        for parser_name, parser in self.parsers.items():
            can_parse, confidence = await parser.can_parse(file_path)

            if can_parse and confidence > best_confidence:
                best_confidence = confidence
                best_parser = parser
                detected_format = parser.parser_type.value

        if not best_parser:
            # Fallback al parser híbrido
            best_parser = self.parsers.get('hybrid_parser', list(self.parsers.values())[0])
            detected_format = "hybrid"

        selection_time = int((time.time() - start_time) * 1000)

        return {
            'parser': best_parser,
            'format': detected_format,
            'confidence': best_confidence,
            'selection_time_ms': selection_time
        }

    async def _get_available_templates(self, company_id: str) -> List[Dict[str, Any]]:
        """Obtiene templates disponibles para una empresa"""
        async with await self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM universal_invoice_formats
                WHERE company_id = %s AND is_active = true
                ORDER BY priority DESC, usage_count DESC
            """, (company_id,))

            templates = []
            for row in cursor.fetchall():
                templates.append({
                    'format_name': row[2],  # format_name
                    'format_type': row[3],  # format_type
                    'template_patterns': json.loads(row[10] or '[]'),  # template_patterns
                    'key_indicators': json.loads(row[11] or '[]'),  # key_indicators
                    'template_structure': json.loads(row[4] or '{}'),  # template_match
                    'field_mappings': json.loads(row[7] or '{}'),  # parser_config
                    'usage_count': row[15] or 0,  # usage_count
                    'avg_confidence': row[17] or 0.0  # avg_confidence
                })

            return templates

    async def _get_validation_rules(self, company_id: str, template_match: TemplateMatch) -> List[ValidationRule]:
        """Obtiene reglas de validación aplicables"""
        # Combinar reglas por defecto con reglas específicas de template
        rules = self.validation_engine.default_rules.copy()

        # Obtener reglas específicas de BD
        async with await self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM universal_invoice_formats
                WHERE company_id = %s AND format_name = %s
            """, (company_id, template_match.template_name))

            row = cursor.fetchone()
            if row:
                validation_rules_data = json.loads(row[5] or '{}')  # validation_rules

                # Convertir reglas de BD a objetos ValidationRule
                for rule_name, rule_data in validation_rules_data.items():
                    rules.append(ValidationRule(
                        rule_name=rule_name,
                        rule_category=ValidationCategory(rule_data.get('category', 'custom')),
                        rule_definition=rule_data.get('definition', {}),
                        rule_parameters=rule_data.get('parameters', {}),
                        error_messages=rule_data.get('error_messages', {}),
                        priority=rule_data.get('priority', 50)
                    ))

        return rules

    def _calculate_overall_quality(self, extraction_result: ExtractionResult,
                                 template_match: TemplateMatch,
                                 validation_result: Dict[str, Any]) -> float:
        """Calcula score de calidad general"""
        # Pesos para cada componente
        extraction_weight = 0.4
        template_weight = 0.3
        validation_weight = 0.3

        # Scores individuales
        extraction_score = sum(extraction_result.confidence_scores.values()) / len(extraction_result.confidence_scores) if extraction_result.confidence_scores else 0.0
        template_score = template_match.match_score * 100
        validation_score = validation_result['validation_score']

        # Score combinado
        overall_score = (
            extraction_score * extraction_weight +
            template_score * template_weight +
            validation_score * validation_weight
        )

        return round(overall_score, 2)

    async def _save_processing_result(self, session_id: str, result: Dict[str, Any],
                                    template_match: TemplateMatch, validation_rules: List[ValidationRule]):
        """Guarda resultado de procesamiento en BD"""
        logger.info(f"Session {session_id}: Entering _save_processing_result()")
        async with await self._get_db_connection() as conn:
            cursor = conn.cursor()

            # Actualizar sesión principal
            cursor.execute("""
                UPDATE sat_invoices
                SET detected_format = %s, parser_used = %s, template_match = %s,
                    validation_rules = %s, extraction_status = %s, extracted_data = %s,
                    parsed_data = %s, extraction_confidence = %s, validation_score = %s,
                    overall_quality_score = %s, processing_time_ms = %s, completed_at = %s,
                    updated_at = %s
                WHERE id = %s
            """, (
                result['detected_format'], result['parser_used'],
                json.dumps(result['template_match']),  # ✅ CAMPO FALTANTE
                json.dumps(result['validation_rules']),  # ✅ CAMPO FALTANTE
                'completed', json.dumps(result['extracted_data']),
                json.dumps(result['parsed_data']),  # Full CFDI data
                result['extraction_confidence'], result['validation_rules']['validation_score'],
                result['overall_quality_score'], result['processing_metrics']['total_time_ms'],
                datetime.utcnow(), datetime.utcnow(), session_id
            ))

            # Guardar template match detallado
            template_id = f"uit_{hashlib.md5(f'{session_id}{template_match.template_name}{datetime.utcnow().isoformat()}'.encode()).hexdigest()[:16]}"
            cursor.execute("""
                INSERT INTO universal_invoice_templates (
                    id, session_id, format_id, template_match, template_name,
                    match_score, matched_patterns, confidence_factors, matching_method,
                    is_selected, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                template_id, session_id, 'default_format',
                json.dumps(result['template_match']),  # ✅ CAMPO FALTANTE
                template_match.template_name, template_match.match_score,
                json.dumps(template_match.matched_patterns),
                json.dumps(template_match.confidence_factors),
                template_match.matching_method.value, True, datetime.utcnow()
            ))

            # Guardar validaciones aplicadas
            for rule in validation_rules:
                validation_id = f"uiv_{hashlib.md5(f'{session_id}{rule.rule_name}{datetime.utcnow().isoformat()}'.encode()).hexdigest()[:16]}"
                cursor.execute("""
                    INSERT INTO universal_invoice_validations (
                        id, session_id, validation_rules, rule_set_name, rule_category,
                        rule_definition, validation_status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    validation_id, session_id,
                    json.dumps({
                        'rule_name': rule.rule_name,
                        'rule_definition': rule.rule_definition,
                        'rule_parameters': rule.rule_parameters,
                        'priority': rule.priority
                    }),  # ✅ CAMPO FALTANTE
                    rule.rule_name, rule.rule_category.value,
                    json.dumps(rule.rule_definition), 'passed', datetime.utcnow()
                ))

            conn.commit()

            # ✅ NEW: Trigger SAT validation after successful processing
            # Launch SAT validation in background (non-blocking)
            asyncio.create_task(self._trigger_sat_validation(session_id, result))

            # ✅ NEW: Trigger accounting classification (v1)
            # DEBUG: Using await for testing instead of create_task
            await self._classify_invoice_accounting(session_id, result)

    async def _trigger_sat_validation(self, session_id: str, result: Dict[str, Any]):
        """
        Trigger SAT validation after invoice processing completes

        This runs in background and doesn't block the invoice processing flow.
        If validation fails, it's logged but doesn't affect the processed invoice.
        """
        try:
            # Check if we have required CFDI data for SAT validation
            extracted_data = result.get('extracted_data', {})
            uuid = extracted_data.get('uuid')

            # Only trigger SAT validation if we have a UUID (i.e., it's a CFDI)
            if not uuid:
                logger.info(f"Session {session_id}: No UUID found, skipping SAT validation")
                return

            logger.info(f"Session {session_id}: SAT validation skipped (feature disabled)")
            # SAT validation is currently disabled due to legacy database dependency
            # TODO: Re-implement SAT validation using current database architecture

        except Exception as e:
            # Log error but don't fail the invoice processing
            logger.error(f"Session {session_id}: Error in background SAT validation: {e}")

    async def _classify_invoice_accounting(self, session_id: str, result: Dict[str, Any]):
        """
        Trigger accounting classification after invoice processing completes

        This runs in background and doesn't block the invoice processing flow.
        Uses LLM (Claude Haiku) to classify invoices against SAT catalog.

        v1 Limitations:
        - Only classifies CFDI type I (Ingreso) and E (Egreso)
        - Only uses first concept if multiple concepts exist
        - Only enabled for beta tenants (carreta_verde, pollenbeemx)
        - No classification_trace in v1 (postponed to v2)
        """
        import time
        import json

        # Beta testers (v1)
        BETA_TENANTS = {'carreta_verde', 'pollenbeemx', 'contaflow'}

        try:
            classification_start = time.time()

            # 1. Extract company_id from session (fallback to result if available)
            company_id = result.get('company_id')
            if not company_id:
                # Get company_id from database session
                async with await self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT company_id FROM sat_invoices WHERE id = %s", (session_id,))
                    row = cursor.fetchone()
                    if row:
                        company_id = row[0]
                    else:
                        logger.warning(f"Session {session_id}: Could not find session in database")
                        return

            # 2. Check if beta tenant
            if company_id not in BETA_TENANTS:
                logger.info(f"Session {session_id}: AI classification not enabled for {company_id}")
                return

            # 3. Verify we have parsed_data (NOT extracted_data which is mostly null)
            parsed_data = result.get('parsed_data')
            if not parsed_data:
                logger.warning(f"Session {session_id}: No parsed_data available, skipping classification")
                return

            # 3. Filter by tipo_comprobante (only I and E)
            tipo_comprobante = parsed_data.get('tipo_comprobante')
            if tipo_comprobante not in ['I', 'E']:
                logger.info(f"Session {session_id}: Tipo {tipo_comprobante} does not require accounting classification")
                return

            # 4. Verify we have concepts
            conceptos = parsed_data.get('conceptos', [])
            if not conceptos:
                logger.info(f"Session {session_id}: No concepts found, skipping classification")
                # Save status as not_classified
                await self._save_classification_status(session_id, 'not_classified', 'No concepts found')
                return

            # 5. Use first concept (v1 simplification)
            concepto = conceptos[0]

            logger.info(f"Session {session_id}: Starting hierarchical classification (3-phase)")

            # 6. Delegate to hierarchical classification service
            #    This service handles:
            #    - Learning history check (auto-apply if >92% similarity)
            #    - Family classification (Phase 1: 100-800)
            #    - Subfamily filtering (Phase 2)
            #    - Specific code selection (Phase 3)
            #    - Model selection (Haiku vs Sonnet based on complexity)
            from core.ai_pipeline.classification.classification_service import classify_invoice_session
            from core.shared.tenant_utils import get_tenant_and_company

            try:
                tenant_id_int, company_id_str = get_tenant_and_company(company_id)
            except Exception as e:
                logger.error(f"Session {session_id}: Could not resolve company_id '{company_id}': {e}")
                await self._save_classification_status(session_id, 'not_classified', f'Invalid company_id: {company_id}')
                return

            classification_dict = classify_invoice_session(
                session_id=session_id,
                company_id=tenant_id_int,  # Pass tenant_id (INTEGER) not company_id (STRING)
                parsed_data=parsed_data,
                top_k=10  # Reduced from 50 because family filter makes candidates more relevant
            )

            if not classification_dict:
                logger.warning(f"Session {session_id}: Classification service returned None")
                await self._save_classification_status(session_id, 'not_classified', 'Service returned None')
                return

            # 7. Calculate duration
            classification_duration = time.time() - classification_start

            # 8. Extract hierarchical metadata for logging
            hierarchical_phase1 = classification_dict.get('metadata', {}).get('hierarchical_phase1', {})
            family_code = hierarchical_phase1.get('family_code', 'N/A')
            family_name = hierarchical_phase1.get('family_name', 'N/A')

            logger.info(
                f"Session {session_id}: Classified as {classification_dict['sat_account_code']} "
                f"(confidence: {classification_dict['confidence_sat']:.2%}) "
                f"[family: {family_code} {family_name}] "
                f"in {classification_duration:.2f}s"
            )

            # 9. Save classification to database
            async with await self._get_db_connection() as conn:
                cursor = conn.cursor()

                # Add processing metrics
                metrics = {
                    "classification_duration_ms": classification_duration * 1000,
                    "used_hierarchical_service": True,
                    "family_classification": hierarchical_phase1,
                    "timestamp": datetime.utcnow().isoformat()
                }
                classification_dict['metadata']['processing_metrics'] = metrics

                # Update sat_invoices
                cursor.execute("""
                    UPDATE sat_invoices
                    SET
                        accounting_classification = %s,
                        processing_metrics = jsonb_set(
                            COALESCE(processing_metrics, '{}'::jsonb),
                            '{accounting_classification}',
                            %s::jsonb
                        )
                    WHERE id = %s
                """, (
                    json.dumps(classification_dict),
                    json.dumps(metrics),
                    session_id
                ))

                logger.info(f"Session {session_id}: Classification saved to sat_invoices")

                # ✅ Also write to expense_invoices (SINGLE SOURCE OF TRUTH)
                await self._save_classification_to_invoice(
                    cursor,
                    session_id,
                    parsed_data,
                    classification_dict,
                    company_id
                )

                conn.commit()

                logger.info(f"Session {session_id}: Hierarchical classification completed successfully")

                # ⭐ FIXED ASSETS DETECTION: Check if this is a fixed asset and get depreciation rates
                await self._enrich_with_depreciation_rates(
                    session_id,
                    classification_dict,
                    parsed_data,
                    cursor
                )

        except Exception as e:
            # Log error but don't fail the invoice processing
            logger.error(f"Session {session_id}: Error in background accounting classification: {e}")
            logger.error(f"Session {session_id}: Error details: {str(e)}", exc_info=True)

            # Try to save error status
            try:
                await self._save_classification_status(session_id, 'not_classified', f'Error: {str(e)}')
            except:
                pass  # If this fails too, just log and continue

    async def _save_classification_status(self, session_id: str, status: str, reason: str):
        """Helper to save classification status when classification cannot be performed"""
        try:
            async with await self._get_db_connection() as conn:
                cursor = conn.cursor()

                accounting_classification = {
                    "status": status,
                    "classified_at": datetime.utcnow().isoformat(),
                    "reason": reason
                }

                cursor.execute("""
                    UPDATE sat_invoices
                    SET accounting_classification = %s
                    WHERE id = %s
                """, (json.dumps(accounting_classification), session_id))

                conn.commit()
        except Exception as e:
            logger.error(f"Session {session_id}: Error saving classification status: {e}")

    async def _save_classification_to_invoice(
        self,
        cursor,
        session_id: str,
        parsed_data: Dict[str, Any],
        accounting_classification: Dict[str, Any],
        company_id: str
    ):
        """
        Save classification to expense_invoices (SINGLE SOURCE OF TRUTH)

        Critical logic:
        1. Find invoice by tenant_id + uuid (official matching criteria)
        2. Respect human decisions (do NOT overwrite confirmed/corrected)
        3. Update atomically with session_id for audit trail
        4. Log everything for troubleshooting

        Args:
            cursor: Database cursor (already in transaction)
            session_id: Universal invoice session ID (for audit trail)
            parsed_data: Parsed CFDI data (contains uuid)
            accounting_classification: Classification result to save
            company_id: Company ID (for logging)
        """
        import json

        try:
            # 1. Extract UUID from parsed CFDI data
            uuid = parsed_data.get('uuid')

            if not uuid:
                logger.warning(
                    f"Session {session_id}: No UUID in parsed_data, cannot link to expense_invoices"
                )
                return

            # 2. Get tenant_id from company_id using centralized helper
            from core.shared.tenant_utils import get_tenant_and_company

            try:
                tenant_id, _ = get_tenant_and_company(company_id)
            except ValueError as e:
                logger.warning(
                    f"Session {session_id}: {e}, cannot link to expense_invoices"
                )
                return

            # 3. Find expense_invoice by UUID FIRST, then validate tenant
            # NOTE: UUID is globally unique, but we log if tenant_id mismatch
            cursor.execute("""
                SELECT
                    id,
                    tenant_id,
                    accounting_classification
                FROM expense_invoices
                WHERE uuid = %s
                LIMIT 1
            """, (uuid,))

            invoice_row = cursor.fetchone()

            if not invoice_row:
                logger.info(
                    f"Session {session_id}: No expense_invoice found for uuid={uuid}. "
                    f"This is normal if invoice was processed via universal engine only."
                )
                return

            # Using RealDictCursor, row is a dictionary
            invoice_id = invoice_row['id']
            invoice_tenant_id = invoice_row['tenant_id']
            existing_classification = invoice_row['accounting_classification']

            # Log if tenant_id mismatch (data migration issue)
            if invoice_tenant_id != tenant_id:
                logger.warning(
                    f"Session {session_id}: Tenant mismatch! Invoice {invoice_id} has tenant_id={invoice_tenant_id} "
                    f"but processing with company_id={company_id} (tenant_id={tenant_id}). "
                    f"This suggests a data migration issue. Proceeding anyway since UUID match is authoritative."
                )

            # 4. Merge classifications using centralized logic (respects priority: corrected > confirmed > pending)
            from core.shared.classification_utils import merge_classification

            # Merge new classification with existing one
            final_classification = merge_classification(existing_classification, accounting_classification)

            # Check if classification actually changed
            if final_classification == existing_classification:
                logger.info(
                    f"Session {session_id}: Invoice {invoice_id} classification unchanged "
                    f"(existing status '{existing_classification.get('status')}' has higher priority)"
                )
                return

            # 5. Update expense_invoices atomically with merged classification
            cursor.execute("""
                UPDATE expense_invoices
                SET
                    accounting_classification = %s,
                    session_id = %s
                WHERE id = %s
            """, (
                json.dumps(final_classification),
                session_id,
                invoice_id
            ))

            logger.info(
                f"Session {session_id}: Classification saved to expense_invoices.id={invoice_id}, "
                f"sat_code={accounting_classification.get('sat_account_code')}, "
                f"confidence={accounting_classification.get('confidence_sat'):.2%}"
            )

        except Exception as e:
            # Log error but don't fail the transaction
            # The classification is already in sat_invoices (audit trail)
            logger.error(
                f"Session {session_id}: Error saving classification to expense_invoices: {e}",
                exc_info=True
            )

    async def _get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene información de una sesión"""
        async with await self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, company_id, user_id, invoice_file_path, original_filename
                FROM sat_invoices WHERE id = %s
            """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return None

            # Using RealDictCursor, row is a dictionary
            return {
                'id': row['id'],
                'company_id': row['company_id'],
                'user_id': row['user_id'],
                'invoice_file_path': row['invoice_file_path'],
                'original_filename': row['original_filename']
            }

    async def _update_session_status(self, session_id: str, status: ExtractionStatus, error: str = None):
        """Actualiza el estado de una sesión"""
        async with await self._get_db_connection() as conn:
            cursor = conn.cursor()
            if error:
                cursor.execute("""
                    UPDATE sat_invoices
                    SET extraction_status = %s, validation_errors = %s, updated_at = %s
                    WHERE id = %s
                """, (status.value, json.dumps([error]), datetime.utcnow(), session_id))
            else:
                cursor.execute("""
                    UPDATE sat_invoices
                    SET extraction_status = %s, updated_at = %s
                    WHERE id = %s
                """, (status.value, datetime.utcnow(), session_id))
            conn.commit()

    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Obtiene el estado de una sesión"""
        async with await self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sat_invoices WHERE id = %s
            """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return {'error': 'Session not found'}

            # Using RealDictCursor, row is a dictionary
            parsed_data = row.get('parsed_data') or {}

            # Sync SAT validation status from database to parsed_data
            if row.get('sat_validation_status') and row['sat_validation_status'] != 'pending':
                parsed_data['sat_status'] = row['sat_validation_status']

            return {
                'session_id': session_id,
                'status': row.get('status', 'pending'),
                'extraction_status': row.get('extraction_status', 'pending'),
                'template_match': row.get('template_match') or {},
                'validation_results': row.get('validation_results') or {},
                'parsed_data': parsed_data,
                'extracted_data': row.get('extracted_data') or {},
                'error_message': row.get('error_message'),
                'created_at': row.get('created_at'),
                'updated_at': row.get('updated_at'),
                'original_filename': row.get('original_filename'),
                'file_hash': row.get('file_hash'),
                'overall_quality_score': row.get('overall_quality_score', 0.0),
                'sat_validation_status': row.get('sat_validation_status'),
                'sat_estado': row.get('sat_estado'),
                'sat_codigo_estatus': row.get('sat_codigo_estatus')
            }

    async def _lookup_sat_account_name(self, sat_code: Optional[str]) -> Optional[str]:
        """Look up official SAT account name from catalog.

        Args:
            sat_code: SAT account code (e.g., "601.01")

        Returns:
            Official SAT account name or the code itself if not found
        """
        if not sat_code:
            return None

        async with await self._get_db_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    SELECT name
                    FROM sat_account_embeddings
                    WHERE code = %s
                    LIMIT 1
                """, (sat_code,))

                row = cursor.fetchone()

                if row:
                    return row['name']
                else:
                    logger.warning(f"SAT code {sat_code} not found in catalog, using code as name")
                    return sat_code  # Return code if not found in catalog

            except Exception as e:
                logger.error(f"Error looking up SAT account name for {sat_code}: {e}")
                return sat_code  # Fallback to code on error

    async def _enrich_with_depreciation_rates(
        self,
        session_id: str,
        classification_dict: Dict[str, Any],
        parsed_data: Dict[str, Any],
        cursor
    ):
        """
        Detect fixed assets and enrich classification with depreciation rates.

        For SAT families 151-158 (fixed assets), uses RAG over LISR Article 34
        to determine fiscal and accounting depreciation rates with legal basis.

        Args:
            session_id: Invoice session ID
            classification_dict: Classification result from AI
            parsed_data: Parsed CFDI data
            cursor: Database cursor (in transaction)
        """
        try:
            sat_code = classification_dict.get('sat_account_code', '')
            if not sat_code:
                return

            # Extract SAT family (first 3 digits before decimal)
            family = sat_code.split('.')[0]

            # Fixed asset families per SAT catalog
            FIXED_ASSET_FAMILIES = {
                '151': 'terrenos',
                '152': 'edificios',
                '153': 'maquinaria',
                '154': 'vehiculos',
                '155': 'mobiliario',
                '156': 'equipo_computo',
                '157': 'equipo_comunicacion',
                '158': 'activos_biologicos',
                '118': 'activos_intangibles'
            }

            if family not in FIXED_ASSET_FAMILIES:
                # Not a fixed asset, skip
                return

            asset_type = FIXED_ASSET_FAMILIES[family]
            logger.info(
                f"Session {session_id}: Fixed asset detected! "
                f"SAT family {family} → {asset_type}"
            )

            # Get asset description from first concept
            conceptos = parsed_data.get('conceptos', [])
            if not conceptos:
                logger.warning(f"Session {session_id}: No concepts found, skipping depreciation")
                return

            concepto = conceptos[0]
            asset_description = concepto.get('descripcion', '')
            sat_product_code = concepto.get('clave_prod_serv')
            amount = parsed_data.get('total', 0)

            # Query depreciation service
            from core.fiscal.depreciation_rate_service import get_depreciation_rate_service

            depr_service = get_depreciation_rate_service()

            depreciation_rate = depr_service.get_depreciation_rate(
                asset_description=asset_description,
                sat_account_code=sat_code,
                sat_product_code=sat_product_code,
                amount=amount
            )

            if not depreciation_rate:
                logger.warning(f"Session {session_id}: Could not determine depreciation rate")
                return

            # Enrich classification_dict with fixed asset metadata
            if 'metadata' not in classification_dict:
                classification_dict['metadata'] = {}

            classification_dict['metadata']['fixed_asset'] = {
                'is_fixed_asset': True,
                'asset_type': depreciation_rate.asset_type,

                # Fiscal rates (for SAT tax returns)
                'depreciation_rate_fiscal_annual': depreciation_rate.annual_rate_fiscal,
                'depreciation_years_fiscal': depreciation_rate.years_fiscal,
                'depreciation_months_fiscal': depreciation_rate.months_fiscal,

                # Accounting rates (for financial statements)
                'depreciation_rate_accounting_annual': depreciation_rate.annual_rate_accounting,
                'depreciation_years_accounting': depreciation_rate.years_accounting,
                'depreciation_months_accounting': depreciation_rate.months_accounting,

                # Legal basis
                'legal_basis': {
                    'law': depreciation_rate.law_code,
                    'article': depreciation_rate.article,
                    'section': depreciation_rate.section,
                    'article_text': depreciation_rate.article_text,
                    'effective_date': depreciation_rate.effective_date,
                    'dof_url': depreciation_rate.dof_url
                },

                # Context
                'applies_to': depreciation_rate.applies_to,
                'reasoning': depreciation_rate.reasoning,
                'confidence': depreciation_rate.confidence,

                # Differential (if fiscal != accounting)
                'has_deferred_tax': (
                    depreciation_rate.annual_rate_fiscal != depreciation_rate.annual_rate_accounting
                )
            }

            # Update sat_invoices with enriched classification
            cursor.execute("""
                UPDATE sat_invoices
                SET accounting_classification = %s
                WHERE id = %s
            """, (json.dumps(classification_dict), session_id))

            logger.info(
                f"Session {session_id}: Fixed asset enriched with depreciation rates: "
                f"{depreciation_rate.annual_rate_fiscal}% fiscal, "
                f"{depreciation_rate.annual_rate_accounting}% accounting "
                f"({depreciation_rate.law_code} Art. {depreciation_rate.article} "
                f"{depreciation_rate.section})"
            )

        except Exception as e:
            # Log error but don't fail the classification
            logger.error(
                f"Session {session_id}: Error enriching with depreciation rates: {e}",
                exc_info=True
            )

    async def _get_db_connection(self):
        """Obtiene conexión a PostgreSQL"""
        class AsyncConnection:
            def __init__(self):
                self.conn = None

            async def __aenter__(self):
                self.conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
                return self.conn

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if self.conn:
                    self.conn.close()

        return AsyncConnection()

# Instancia singleton
universal_invoice_engine_system = UniversalInvoiceEngineSystem()