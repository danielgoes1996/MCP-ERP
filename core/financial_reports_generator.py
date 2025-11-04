"""
Sistema de generación automática de reportes fiscales.
Incluye: IVA, pólizas electrónicas (Anexo 24), gastos en revisión.
"""

import logging
import json
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from enum import Enum
from collections import defaultdict

from core.internal_db import get_sqlite_connection
from core.sat_catalog_seed import CATEGORY_SAT_MAPPING

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Tipos de reportes fiscales disponibles."""
    IVA_REPORT = "iva_report"
    POLIZA_ELECTRONICA = "poliza_electronica"
    GASTOS_REVISION = "gastos_revision"
    RESUMEN_FISCAL = "resumen_fiscal"


class IVACategory(Enum):
    """Categorías de IVA para reporteo."""
    ACREDITABLE_16 = "acreditable_16"
    ACREDITABLE_8 = "acreditable_8"
    NO_ACREDITABLE = "no_acreditable"
    EXENTO = "exento"
    TASA_0 = "tasa_0"


def calculate_iva_from_amount(
    total: Decimal,
    tasa_iva: Optional[Decimal] = None
) -> Tuple[Decimal, Decimal]:
    """
    Calcula el IVA y subtotal desde un monto total.

    Args:
        total: Monto total con IVA
        tasa_iva: Tasa de IVA (0.16, 0.08, 0.0, None para exento)

    Returns:
        Tuple (subtotal, iva)
    """
    if tasa_iva is None or tasa_iva == 0:
        return (total, Decimal(0))

    subtotal = total / (1 + tasa_iva)
    iva = total - subtotal
    return (subtotal.quantize(Decimal('0.01')), iva.quantize(Decimal('0.01')))


class FinancialReportsGenerator:
    """Generador principal de reportes fiscales."""

    def __init__(self, tenant_id: str, tax_source: Optional[str] = None):
        self.tenant_id = tenant_id
        normalized = (tax_source or "").lower() if tax_source else None
        if normalized in {"all", "todos", "todo", "default", ""}:
            normalized = None
        self.tax_source_filter = normalized

    def _should_include_tax_source(self, source: Optional[str]) -> bool:
        if not self.tax_source_filter:
            return True
        return (source or 'unknown').lower() == self.tax_source_filter

    def _normalize_expense_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(row)
        metadata_raw = record.get('metadata')
        metadata: Dict[str, Any] = {}
        if metadata_raw:
            try:
                metadata = json.loads(metadata_raw)
            except (TypeError, json.JSONDecodeError):
                metadata = {}
        record['metadata_dict'] = metadata

        total_amount = Decimal(str(record.get('amount') or 0))
        subtotal = record.get('subtotal')
        if subtotal is not None:
            subtotal = Decimal(str(subtotal))
        iva_16 = Decimal(str(record.get('iva_16') or 0))
        iva_8 = Decimal(str(record.get('iva_8') or 0))
        iva_0 = Decimal(str(record.get('iva_0') or 0))
        iva_total = iva_16 + iva_8 + iva_0
        if subtotal is None:
            subtotal = total_amount - iva_total

        record['total'] = total_amount
        record['subtotal'] = subtotal
        record['iva'] = iva_total
        record['iva_16'] = iva_16
        record['iva_8'] = iva_8
        record['iva_0'] = iva_0
        record['tax_source'] = (record.get('tax_source') or metadata.get('tax_source') or 'unknown').lower()
        confianza = record.get('categoria_confianza')
        needs_review_meta = metadata.get('categoria_needs_review')
        if needs_review_meta is None and confianza is not None:
            try:
                needs_review_meta = float(confianza) < 0.6
            except (TypeError, ValueError):
                needs_review_meta = False
        record['needs_review'] = bool(needs_review_meta)
        record['fecha_gasto'] = record.get('date') or record.get('expense_date')
        record['merchant_name'] = record.get('merchant_name') or record.get('proveedor')
        record['description'] = record.get('description') or record.get('descripcion')
        record['metadata'] = metadata
        return record

    def _fetch_expenses(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        with get_sqlite_connection() as conn:
            query = """
                SELECT *
                  FROM expense_records
                 WHERE tenant_id = ?
                   AND date >= ?
                   AND date <= ?
                   AND (status IS NULL OR status != 'cancelled')
                ORDER BY date, id
            """
            cursor = conn.execute(query, (self.tenant_id, start_date, end_date))
            expenses: List[Dict[str, Any]] = []
            for row in cursor:
                normalized = self._normalize_expense_row(row)
                if not self._should_include_tax_source(normalized.get('tax_source')):
                    continue
                expenses.append(normalized)
            return expenses

    def _get_fiscal_period_dates(
        self,
        year: int,
        month: int
    ) -> Tuple[date, date]:
        """Obtiene fechas de inicio y fin del periodo fiscal."""
        start_date = date(year, month, 1)

        # Último día del mes
        if month == 12:
            end_date = date(year, month, 31)
        else:
            next_month = date(year, month + 1, 1)
            from datetime import timedelta
            end_date = next_month - timedelta(days=1)

        return start_date, end_date

    def generate_iva_report(
        self,
        year: int,
        month: int,
        detailed: bool = True
    ) -> Dict[str, Any]:
        """
        Genera reporte de IVA acreditable y no acreditable.

        Args:
            year: Año del reporte
            month: Mes del reporte
            detailed: Si incluir detalle por gasto

        Returns:
            Dict con resumen y detalle de IVA
        """
        start_date, end_date = self._get_fiscal_period_dates(year, month)
        expenses = self._fetch_expenses(start_date, end_date)

        for expense in expenses:
            expense['iva_category'] = self._classify_iva({
                'categoria_slug': expense.get('categoria_slug'),
                'iva': expense.get('iva'),
                'subtotal': expense.get('subtotal'),
                'cfdi_uuid': expense.get('cfdi_uuid'),
            })

        summary = self._generate_iva_summary(expenses)

        report = {
            'periodo': {
                'año': year,
                'mes': month,
                'fecha_inicio': start_date.isoformat(),
                'fecha_fin': end_date.isoformat()
            },
            'resumen': summary,
            'tax_sources': summary.get('tax_sources', {}),
            'generado_en': datetime.now().isoformat(),
            'tenant_id': self.tenant_id
        }

        if detailed:
            detalle = []
            for expense in expenses:
                detalle.append({
                    'id': expense.get('id'),
                    'proveedor': expense.get('merchant_name') or expense.get('proveedor'),
                    'descripcion': expense.get('description') or expense.get('descripcion'),
                    'total': float(expense['total']),
                    'subtotal': float(expense['subtotal']),
                    'iva': float(expense['iva']),
                    'categoria_slug': expense.get('categoria_slug'),
                    'sat_account_code': expense.get('sat_account_code'),
                    'sat_product_service_code': expense.get('sat_product_service_code'),
                    'iva_category': expense.get('iva_category'),
                    'tax_source': expense.get('tax_source'),
                    'cfdi_uuid': expense.get('cfdi_uuid'),
                    'fecha_gasto': expense.get('fecha_gasto'),
                })
            report['detalle'] = detalle

        return report

    def _classify_iva(self, expense: Dict) -> str:
        """Clasifica el IVA según las reglas fiscales."""
        categoria_info = CATEGORY_SAT_MAPPING.get(expense['categoria_slug'], {})

        # Gastos no deducibles = IVA no acreditable
        if categoria_info.get('sat_product_service_code') == '99999998':
            return IVACategory.NO_ACREDITABLE.value

        # Gastos de representación = IVA no acreditable generalmente
        if expense['categoria_slug'] in ['gastos_representacion', 'entretenimiento']:
            return IVACategory.NO_ACREDITABLE.value

        # Por defecto, IVA es acreditable
        if expense['iva'] and expense['iva'] > 0:
            # Determinar tasa
            if expense['subtotal'] and expense['subtotal'] > 0:
                tasa = expense['iva'] / expense['subtotal']
                if tasa >= 0.15:  # ~16%
                    return IVACategory.ACREDITABLE_16.value
                elif tasa >= 0.07:  # ~8%
                    return IVACategory.ACREDITABLE_8.value

        if expense['iva'] == 0:
            return IVACategory.TASA_0.value

        return IVACategory.EXENTO.value

    def _generate_iva_summary(self, expenses: List[Dict]) -> Dict:
        """Genera resumen de IVA por categorías."""
        summary = {
            'total_gastos': 0.0,
            'total_subtotal': 0.0,
            'total_iva': 0.0,
            'iva_acreditable_16': 0.0,
            'iva_acreditable_8': 0.0,
            'iva_no_acreditable': 0.0,
            'iva_tasa_0': 0.0,
            'gastos_exentos': 0.0,
            'gastos_revision': 0,
            'gastos_con_cfdi': 0,
            'gastos_sin_cfdi': 0,
            'tax_sources': {}
        }

        tax_counts = defaultdict(lambda: {'cantidad': 0, 'total': 0.0})

        for expense in expenses:
            total = float(expense['total'])
            subtotal = float(expense['subtotal']) if expense['subtotal'] is not None else total
            iva_value = float(expense['iva'])

            summary['total_gastos'] += total
            summary['total_subtotal'] += subtotal
            summary['total_iva'] += iva_value

            if expense.get('cfdi_uuid'):
                summary['gastos_con_cfdi'] += 1
            else:
                summary['gastos_sin_cfdi'] += 1

            if expense.get('needs_review'):
                summary['gastos_revision'] += 1

            source = (expense.get('tax_source') or 'unknown').lower()
            tax_counts[source]['cantidad'] += 1
            tax_counts[source]['total'] += total

            iva_cat = expense.get('iva_category')
            if iva_cat == IVACategory.ACREDITABLE_16.value:
                summary['iva_acreditable_16'] += iva_value
            elif iva_cat == IVACategory.ACREDITABLE_8.value:
                summary['iva_acreditable_8'] += iva_value
            elif iva_cat == IVACategory.NO_ACREDITABLE.value:
                summary['iva_no_acreditable'] += iva_value
            elif iva_cat == IVACategory.TASA_0.value:
                summary['iva_tasa_0'] += total
            elif iva_cat == IVACategory.EXENTO.value:
                summary['gastos_exentos'] += total

        summary['total_iva_acreditable'] = summary['iva_acreditable_16'] + summary['iva_acreditable_8']

        total_amount = sum(entry['total'] for entry in tax_counts.values())
        total_count = sum(entry['cantidad'] for entry in tax_counts.values())
        tax_sources_summary = {}
        for key, data in tax_counts.items():
            porcentaje_total = (data['total'] / total_amount * 100) if total_amount else 0.0
            porcentaje_count = (data['cantidad'] / total_count * 100) if total_count else 0.0
            tax_sources_summary[key] = {
                'cantidad': data['cantidad'],
                'total': round(data['total'], 2),
                'porcentaje_total': round(porcentaje_total, 2),
                'porcentaje_cantidad': round(porcentaje_count, 2),
            }

        summary['tax_sources'] = tax_sources_summary
        summary['total_gastos'] = round(summary['total_gastos'], 2)
        summary['total_subtotal'] = round(summary['total_subtotal'], 2)
        summary['total_iva'] = round(summary['total_iva'], 2)
        summary['iva_acreditable_16'] = round(summary['iva_acreditable_16'], 2)
        summary['iva_acreditable_8'] = round(summary['iva_acreditable_8'], 2)
        summary['iva_no_acreditable'] = round(summary['iva_no_acreditable'], 2)
        summary['iva_tasa_0'] = round(summary['iva_tasa_0'], 2)
        summary['gastos_exentos'] = round(summary['gastos_exentos'], 2)
        summary['total_iva_acreditable'] = round(summary['total_iva_acreditable'], 2)

        return summary

    def generate_poliza_electronica(
        self,
        year: int,
        month: int,
        tipo_poliza: str = "Dr"  # Dr = Diario, Ig = Ingresos, Eg = Egresos
    ) -> Dict[str, Any]:
        """
        Genera póliza electrónica en formato Anexo 24 del SAT.

        Args:
            year: Año de la póliza
            month: Mes de la póliza
            tipo_poliza: Tipo de póliza (Dr, Ig, Eg)

        Returns:
            Dict con estructura de póliza electrónica
        """
        start_date, end_date = self._get_fiscal_period_dates(year, month)
        expenses = self._fetch_expenses(start_date, end_date)

        polizas = []
        numero_poliza = 1

        for expense in expenses:
            monto = float(expense['total'])
            subtotal = float(expense['subtotal']) if expense['subtotal'] is not None else monto
            iva = float(expense['iva'])
            categoria = expense.get('categoria_slug')
            cuenta_sat = expense.get('sat_account_code') or "5000"
            proveedor = expense.get('merchant_name') or expense.get('description') or 'Proveedor'
            descripcion = expense.get('description') or ''
            uuid = expense.get('cfdi_uuid')
            metadata = expense.get('metadata', {})
            rfc_emisor = metadata.get('rfc') or expense.get('rfc_proveedor') or 'XAXX010101000'
            numero_cuenta = expense.get('payment_account_id')
            fecha = (expense.get('fecha_gasto') or datetime.now().date()).split('T')[0] if isinstance(expense.get('fecha_gasto'), str) else expense.get('fecha_gasto')

            transaccion = {
                'NumUnIdenPol': f"{tipo_poliza}-{numero_poliza:04d}",
                'Fecha': fecha,
                'Concepto': f"{proveedor} - {descripcion}"[:300],
                'Transaccion': [
                    {
                        'NumCta': cuenta_sat,
                        'DesCta': CATEGORY_SAT_MAPPING.get(categoria, {}).get('nombre', 'Gasto'),
                        'Concepto': descripcion[:200],
                        'Debe': round(subtotal, 2),
                        'Haber': 0
                    }
                ]
            }

            if iva > 0:
                transaccion['Transaccion'].append({
                    'NumCta': "1190",
                    'DesCta': "IVA acreditable",
                    'Concepto': f"IVA {proveedor}",
                    'Debe': round(iva, 2),
                    'Haber': 0
                })

            cuenta_banco = "1020" if numero_cuenta else "1010"
            transaccion['Transaccion'].append({
                'NumCta': cuenta_banco,
                'DesCta': "Bancos" if numero_cuenta else "Caja",
                'Concepto': f"Pago a {proveedor}",
                'Debe': 0,
                'Haber': round(monto, 2)
            })

            if uuid:
                for trans in transaccion['Transaccion']:
                    if trans['Debe'] > 0:
                        trans['CompNal'] = {
                            'UUID_CFDI': uuid,
                            'RFC': rfc_emisor,
                            'MontoTotal': round(monto, 2)
                        }

            if not polizas or polizas[-1]['Fecha'] != fecha:
                polizas.append({
                    'NumUnIdenPol': f"{tipo_poliza}-{numero_poliza:04d}",
                    'Fecha': fecha,
                    'Concepto': f"Gastos del día {fecha}",
                    'Transacciones': []
                })
                numero_poliza += 1

            polizas[-1]['Transacciones'].append(transaccion)

        # Estructura del Anexo 24
        poliza_electronica = {
            'Version': '1.3',
            'RFC': self._get_company_rfc(),
            'Mes': str(month).zfill(2),
            'Anio': year,
            'TipoSolicitud': 'AF',  # Acto de Fiscalización
            'NumOrden': '',
            'NumTramite': '',
            'Sello': '',  # Se genera al firmar
            'noCertificado': '',
            'Certificado': '',
            'Polizas': {
                'Poliza': polizas
            }
        }

        return poliza_electronica

    def generate_gastos_revision_report(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Genera reporte de gastos marcados para revisión.

        Args:
            year: Año (opcional, None = todos)
            month: Mes (opcional, None = todos)

        Returns:
            Dict con gastos que requieren revisión
        """
        if year and month:
            start_date, end_date = self._get_fiscal_period_dates(year, month)
        else:
            start_date = date(2000, 1, 1)
            end_date = datetime.now().date()

        expenses = self._fetch_expenses(start_date, end_date)

        gastos_revision: List[Dict[str, Any]] = []
        razones_revision: Dict[str, int] = defaultdict(int)
        monto_total_revision = 0.0

        for expense in expenses:
            if not expense.get('needs_review'):
                continue

            categoria = expense.get('categoria_slug')
            categoria_info = CATEGORY_SAT_MAPPING.get(categoria, {})
            razones: List[str] = []

            if categoria_info.get('needs_review'):
                razones.append("Categoría marcada como genérica o ambigua")

            regimen = expense.get('metadata', {}).get('fiscal_regime') or expense.get('metadata_dict', {}).get('fiscal_regime')
            if regimen:
                allowed = categoria_info.get('allowed_regimes', [])
                disallowed = categoria_info.get('disallowed_regimes', [])
                if allowed and regimen not in allowed:
                    razones.append(f"Categoría no permitida para régimen {regimen}")
                if disallowed and regimen in disallowed:
                    razones.append(f"Categoría restringida para régimen {regimen}")

            if not expense.get('cfdi_uuid') and float(expense['total']) > 2000:
                razones.append("Monto significativo sin CFDI")

            if (expense.get('tax_source') or 'unknown') == 'llm':
                razones.append("Clasificación IA pendiente de confirmación")

            if not razones:
                razones.append("Revisión manual sugerida")

            for razon in razones:
                razones_revision[razon] += 1

            gastos_revision.append({
                'id': expense.get('id'),
                'fecha': expense.get('fecha_gasto'),
                'proveedor': expense.get('merchant_name'),
                'descripcion': expense.get('description'),
                'monto': round(float(expense['total']), 2),
                'categoria': categoria,
                'tiene_cfdi': bool(expense.get('cfdi_uuid')),
                'tax_source': expense.get('tax_source'),
                'razones_revision': razones,
            })

            monto_total_revision += float(expense['total'])

        return {
            'periodo': {
                'año': year,
                'mes': month
            } if year else {'completo': True},
            'total_gastos_revision': len(gastos_revision),
            'monto_total_revision': round(monto_total_revision, 2),
            'razones_frecuentes': dict(razones_revision),
            'gastos': gastos_revision,
            'generado_en': datetime.now().isoformat()
        }

    def generate_resumen_fiscal(
        self,
        year: int,
        month: int
    ) -> Dict[str, Any]:
        """
        Genera resumen fiscal completo del periodo.

        Incluye:
        - Totales de gastos por categoría SAT
        - IVA acreditable vs no acreditable
        - Gastos con y sin CFDI
        - Alertas y recomendaciones
        """
        iva_report = self.generate_iva_report(year, month, detailed=False)
        revision_report = self.generate_gastos_revision_report(year, month)

        start_date, end_date = self._get_fiscal_period_dates(year, month)
        expenses = self._fetch_expenses(start_date, end_date)

        categorias_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'cantidad': 0,
            'total': 0.0,
            'con_cfdi': 0
        })

        for expense in expenses:
            slug = expense.get('categoria_slug') or 'sin_categoria'
            categoria = categorias_map[slug]
            categoria['cantidad'] += 1
            categoria['total'] += float(expense['total'])
            if expense.get('cfdi_uuid'):
                categoria['con_cfdi'] += 1
            categoria['codigo_sat'] = expense.get('sat_account_code')

        categorias = []
        total_general = sum(item['total'] for item in categorias_map.values())
        for slug, data in categorias_map.items():
            categoria_info = CATEGORY_SAT_MAPPING.get(slug, {})
            porcentaje_total = (data['total'] / total_general * 100) if total_general else 0.0
            porcentaje_cfdi = (data['con_cfdi'] / data['cantidad'] * 100) if data['cantidad'] else 0.0
            categorias.append({
                'slug': slug,
                'nombre': categoria_info.get('nombre', slug),
                'codigo_sat': data.get('codigo_sat'),
                'cantidad': data['cantidad'],
                'total': round(data['total'], 2),
                'porcentaje_total': round(porcentaje_total, 2),
                'porcentaje_cfdi': round(porcentaje_cfdi, 2),
            })

        categorias.sort(key=lambda item: item['total'], reverse=True)

        # Generar alertas
        alertas = []

        if revision_report['total_gastos_revision'] > 0:
            alertas.append({
                'tipo': 'warning',
                'mensaje': f"Hay {revision_report['total_gastos_revision']} gastos que requieren revisión",
                'monto': revision_report['monto_total_revision']
            })

        if iva_report['resumen']['gastos_sin_cfdi'] > 0:
            alertas.append({
                'tipo': 'info',
                'mensaje': f"{iva_report['resumen']['gastos_sin_cfdi']} gastos sin CFDI",
                'recomendacion': 'Solicitar facturas para deducibilidad fiscal'
            })

        iva_no_acreditable = iva_report['resumen'].get('iva_no_acreditable', 0)
        if iva_no_acreditable > 0:
            alertas.append({
                'tipo': 'info',
                'mensaje': f"IVA no acreditable: ${iva_no_acreditable:,.2f}",
                'recomendacion': 'Revisar gastos de representación y no deducibles'
            })

        return {
            'periodo': {
                'año': year,
                'mes': month
            },
            'totales': {
                'gastos_total': iva_report['resumen']['total_gastos'],
                'subtotal': iva_report['resumen']['total_subtotal'],
                'iva_total': iva_report['resumen']['total_iva'],
                'iva_acreditable': iva_report['resumen']['total_iva_acreditable'],
                'iva_no_acreditable': iva_no_acreditable
            },
            'cfdi': {
                'con_cfdi': iva_report['resumen']['gastos_con_cfdi'],
                'sin_cfdi': iva_report['resumen']['gastos_sin_cfdi'],
                'porcentaje_cfdi': (
                    iva_report['resumen']['gastos_con_cfdi'] /
                    (iva_report['resumen']['gastos_con_cfdi'] + iva_report['resumen']['gastos_sin_cfdi']) * 100
                ) if (iva_report['resumen']['gastos_con_cfdi'] + iva_report['resumen']['gastos_sin_cfdi']) > 0 else 0
            },
            'categorias': categorias[:10],  # Top 10 categorías
            'revision': {
                'total': revision_report['total_gastos_revision'],
                'monto': revision_report['monto_total_revision'],
                'razones': revision_report['razones_frecuentes']
            },
            'alertas': alertas,
            'tax_sources': iva_report.get('tax_sources', {}),
            'generado_en': datetime.now().isoformat()
        }

    def _get_company_rfc(self) -> str:
        """Obtiene el RFC de la empresa del tenant."""
        with get_sqlite_connection() as conn:
            result = conn.execute(
                "SELECT rfc FROM companies WHERE tenant_id = ?",
                (self.tenant_id,)
            ).fetchone()

            return result['rfc'] if result else 'XAXX010101000'


def export_report_to_excel(report: Dict, filename: str):
    """
    Exporta reporte a Excel (requiere openpyxl).

    Esta función es un placeholder - implementar cuando se requiera.
    """
    logger.info(f"Exportación a Excel pendiente de implementación: {filename}")
    # TODO: Implementar con openpyxl cuando se requiera


def export_poliza_to_xml(poliza: Dict, filename: str):
    """
    Exporta póliza electrónica a XML según especificación SAT.

    Esta función es un placeholder - implementar cuando se requiera.
    """
    logger.info(f"Exportación a XML pendiente de implementación: {filename}")
    # TODO: Implementar generación XML con lxml cuando se requiera
