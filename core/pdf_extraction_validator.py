#!/usr/bin/env python3
"""
Sistema de validación para extracción de PDFs bancarios
Asegura que no se pierda ninguna transacción durante el proceso de extracción
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from decimal import Decimal, ROUND_HALF_UP
import json
from datetime import datetime

class PDFExtractionValidator:
    """Validador de extracción de PDFs bancarios para prevenir pérdida de transacciones"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.validation_results = {}

    def extract_raw_transactions_from_text(self, pdf_text: str) -> List[Dict]:
        """
        Extrae todas las transacciones del texto del PDF usando múltiples patrones
        para asegurar que no se pierda ninguna
        """
        transactions = []

        # Patrón principal para transacciones mexicanas
        # Formato: DD MMM YYYY Descripción MONTO o JUL. DD NNNNNN DESCRIPCION MONTO
        pattern_main = r'(\d{1,2}\s+(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?\s*\d{4})\s+(.+?)\s+([\d,]+\.?\d{0,2})'

        # Patrón específico para formato Inbursa: JUL. 01 12345678 DESCRIPCION MONTO
        pattern_inbursa = r'((?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?\s+\d{1,2})\s+\d+\s+(.+?)\s+([\d,]+\.?\d{0,2})'

        # Patrón alternativo para fechas en formato DD/MM/YYYY
        pattern_alt1 = r'(\d{1,2}/\d{1,2}/\d{4})\s+(.+?)\s+([\d,]+\.?\d{0,2})'

        # Patrón para SPEI y transferencias
        pattern_spei = r'(SPEI|TRANSFERENCIA|CARGO|ABONO|DEPOSITO).+?(\d{1,2}\s+(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?\s*\d{4})\s+(.+?)\s+([\d,]+\.?\d{0,2})'

        # Patrón simple para cualquier línea con monto
        pattern_simple = r'(.+?)\s+([\d,]+\.?\d{2})(?:\s|$)'

        patterns = [
            ("main", pattern_main),
            ("inbursa", pattern_inbursa),
            ("alt1", pattern_alt1),
            ("spei", pattern_spei),
            ("simple", pattern_simple)
        ]

        lines = pdf_text.split('\n')

        for pattern_name, pattern in patterns:
            matches = re.findall(pattern, pdf_text, re.IGNORECASE | re.MULTILINE)

            for match in matches:
                try:
                    if pattern_name == "spei":
                        trans_type, date_str, description, amount_str = match
                        description = f"{trans_type} {description}"
                    elif pattern_name == "simple":
                        description, amount_str = match
                        date_str = "unknown"  # No date in simple pattern
                    elif pattern_name == "inbursa":
                        date_str, description, amount_str = match
                    else:
                        date_str, description, amount_str = match

                    # Limpiar y procesar monto
                    amount_clean = amount_str.replace(',', '').replace(' ', '')
                    if '.' not in amount_clean and len(amount_clean) > 2:
                        # Assume last 2 digits are cents if no decimal point
                        amount = float(amount_clean[:-2] + '.' + amount_clean[-2:])
                    else:
                        amount = float(amount_clean)

                    # Skip very small amounts (likely not real transactions)
                    if amount < 0.01:
                        continue

                    transaction = {
                        'raw_date': date_str.strip(),
                        'raw_description': description.strip(),
                        'raw_amount': amount,
                        'extraction_pattern': pattern_name,
                        'source_line': self._find_source_line(lines, description.strip())
                    }

                    transactions.append(transaction)

                except (ValueError, IndexError) as e:
                    # Skip malformed matches
                    continue

        # Eliminar duplicados
        unique_transactions = self._remove_duplicates(transactions)

        self.logger.info(f"Extraídas {len(unique_transactions)} transacciones únicas del PDF")
        return unique_transactions

    def validate_extraction_completeness(self,
                                       pdf_text: str,
                                       extracted_transactions: List[Dict],
                                       expected_balance_initial: Optional[float] = None,
                                       expected_balance_final: Optional[float] = None) -> Dict:
        """
        Valida que la extracción esté completa comparando múltiples fuentes
        """
        validation_result = {
            'is_complete': True,
            'issues': [],
            'recommendations': [],
            'raw_transaction_count': 0,
            'extracted_transaction_count': len(extracted_transactions),
            'missing_transactions': [],
            'balance_validation': {},
            'timestamp': datetime.now().isoformat()
        }

        # 1. Extraer transacciones directamente del texto
        raw_transactions = self.extract_raw_transactions_from_text(pdf_text)
        validation_result['raw_transaction_count'] = len(raw_transactions)

        # 2. Comparar conteos
        if len(raw_transactions) != len(extracted_transactions):
            validation_result['is_complete'] = False
            validation_result['issues'].append({
                'type': 'transaction_count_mismatch',
                'message': f"Conteo no coincide: {len(raw_transactions)} en PDF vs {len(extracted_transactions)} extraídas",
                'severity': 'critical'
            })

        # 3. Buscar transacciones faltantes
        missing = self._find_missing_transactions(raw_transactions, extracted_transactions)
        if missing:
            validation_result['is_complete'] = False
            validation_result['missing_transactions'] = missing
            validation_result['issues'].append({
                'type': 'missing_transactions',
                'message': f"Se encontraron {len(missing)} transacciones faltantes",
                'severity': 'critical',
                'details': missing
            })

        # 4. Validar balances si se proporcionan
        if expected_balance_initial is not None or expected_balance_final is not None:
            balance_validation = self._validate_balances(
                extracted_transactions,
                expected_balance_initial,
                expected_balance_final
            )
            validation_result['balance_validation'] = balance_validation

            if not balance_validation['is_valid']:
                validation_result['is_complete'] = False
                validation_result['issues'].append({
                    'type': 'balance_mismatch',
                    'message': 'Los balances no coinciden con los esperados',
                    'severity': 'critical',
                    'details': balance_validation
                })

        # 5. Verificar patrones sospechosos
        suspicious_patterns = self._detect_suspicious_patterns(pdf_text, extracted_transactions)
        if suspicious_patterns:
            validation_result['issues'].extend(suspicious_patterns)

        # 6. Generar recomendaciones
        validation_result['recommendations'] = self._generate_recommendations(validation_result)

        return validation_result

    def _find_source_line(self, lines: List[str], description: str) -> Optional[str]:
        """Encuentra la línea original en el PDF que contiene la descripción"""
        description_clean = description.strip().lower()
        for line in lines:
            if description_clean in line.lower():
                return line.strip()
        return None

    def _remove_duplicates(self, transactions: List[Dict]) -> List[Dict]:
        """Elimina transacciones duplicadas basándose en fecha, descripción y monto"""
        seen = set()
        unique = []

        for txn in transactions:
            key = (
                txn['raw_date'],
                txn['raw_description'][:50],  # Primeros 50 caracteres
                txn['raw_amount']
            )

            if key not in seen:
                seen.add(key)
                unique.append(txn)

        return unique

    def _find_missing_transactions(self, raw_transactions: List[Dict], extracted_transactions: List[Dict]) -> List[Dict]:
        """Identifica transacciones que están en el PDF pero no en la extracción"""
        missing = []

        # Crear conjunto de transacciones extraídas para comparación rápida
        extracted_set = set()
        for txn in extracted_transactions:
            key = (
                str(txn.get('date', '')),
                str(txn.get('description', ''))[:50],
                float(txn.get('amount', 0))
            )
            extracted_set.add(key)

        # Buscar transacciones raw que no están en extracted
        for raw_txn in raw_transactions:
            key = (
                raw_txn['raw_date'],
                raw_txn['raw_description'][:50],
                raw_txn['raw_amount']
            )

            if key not in extracted_set:
                missing.append({
                    'raw_transaction': raw_txn,
                    'possible_reasons': self._analyze_missing_reason(raw_txn)
                })

        return missing

    def _analyze_missing_reason(self, missing_txn: Dict) -> List[str]:
        """Analiza posibles razones por las que una transacción no fue extraída"""
        reasons = []

        desc = missing_txn['raw_description']

        if len(desc) < 5:
            reasons.append("Descripción muy corta")

        if any(char in desc for char in ['*', '/', '#', '@']):
            reasons.append("Caracteres especiales en descripción")

        if missing_txn['raw_amount'] < 1:
            reasons.append("Monto muy pequeño")

        if 'BALANCE' in desc.upper():
            reasons.append("Podría ser balance inicial/final")

        if not reasons:
            reasons.append("Patrón de extracción no reconoció formato")

        return reasons

    def _validate_balances(self, transactions: List[Dict], initial_balance: Optional[float], final_balance: Optional[float]) -> Dict:
        """Valida que los balances iniciales y finales coincidan"""
        validation = {
            'is_valid': True,
            'initial_balance_check': {},
            'final_balance_check': {},
            'calculated_final': None
        }

        if not transactions:
            return validation

        # Calcular balance final basado en transacciones
        if initial_balance is not None:
            calculated_final = initial_balance
            for txn in transactions:
                calculated_final += txn.get('amount', 0)

            validation['calculated_final'] = calculated_final

            if final_balance is not None:
                diff = abs(calculated_final - final_balance)
                validation['final_balance_check'] = {
                    'expected': final_balance,
                    'calculated': calculated_final,
                    'difference': diff,
                    'is_valid': diff < 0.01  # Tolerancia de 1 centavo
                }

                if diff >= 0.01:
                    validation['is_valid'] = False

        return validation

    def _detect_suspicious_patterns(self, pdf_text: str, extracted_transactions: List[Dict]) -> List[Dict]:
        """Detecta patrones sospechosos que podrían indicar transacciones perdidas"""
        issues = []

        # Buscar números que parecen montos pero no fueron extraídos
        amount_pattern = r'\b\d{1,3}(?:,\d{3})*\.\d{2}\b'
        potential_amounts = re.findall(amount_pattern, pdf_text)

        extracted_amounts = [str(txn.get('amount', 0)) for txn in extracted_transactions]

        unmatched_amounts = []
        for amount_str in potential_amounts:
            amount_float = float(amount_str.replace(',', ''))
            if amount_float > 10 and amount_str not in extracted_amounts:  # Ignorar montos muy pequeños
                unmatched_amounts.append(amount_str)

        if len(unmatched_amounts) > 2:  # Más de 2 montos sin extraer es sospechoso
            issues.append({
                'type': 'unmatched_amounts',
                'message': f'Se encontraron {len(unmatched_amounts)} montos potenciales no extraídos',
                'severity': 'warning',
                'details': unmatched_amounts[:5]  # Mostrar solo los primeros 5
            })

        return issues

    def _generate_recommendations(self, validation_result: Dict) -> List[str]:
        """Genera recomendaciones basadas en los resultados de validación"""
        recommendations = []

        if not validation_result['is_complete']:
            recommendations.append("Revisar manualmente el PDF original contra las transacciones extraídas")

        if validation_result['missing_transactions']:
            recommendations.append("Implementar patrones de extracción adicionales para capturar transacciones faltantes")

        if validation_result.get('balance_validation', {}).get('is_valid') == False:
            recommendations.append("Verificar cálculos de balance y buscar transacciones adicionales")

        for issue in validation_result.get('issues', []):
            if issue['type'] == 'unmatched_amounts':
                recommendations.append("Revisar montos no extraídos para identificar posibles transacciones perdidas")

        if not recommendations:
            recommendations.append("La extracción parece completa, proceder con confianza")

        return recommendations

    def generate_validation_report(self, validation_result: Dict) -> str:
        """Genera un reporte legible de la validación"""
        report = []
        report.append("=" * 60)
        report.append("🔍 REPORTE DE VALIDACIÓN DE EXTRACCIÓN PDF")
        report.append("=" * 60)

        # Estado general
        status = "✅ COMPLETA" if validation_result['is_complete'] else "❌ INCOMPLETA"
        report.append(f"\n📊 Estado: {status}")
        report.append(f"📈 Transacciones en PDF: {validation_result['raw_transaction_count']}")
        report.append(f"📤 Transacciones extraídas: {validation_result['extracted_transaction_count']}")

        # Problemas encontrados
        if validation_result['issues']:
            report.append(f"\n⚠️  PROBLEMAS ENCONTRADOS ({len(validation_result['issues'])}):")
            for i, issue in enumerate(validation_result['issues'], 1):
                report.append(f"  {i}. [{issue['severity'].upper()}] {issue['message']}")

        # Transacciones faltantes
        if validation_result['missing_transactions']:
            report.append(f"\n🚨 TRANSACCIONES FALTANTES ({len(validation_result['missing_transactions'])}):")
            for i, missing in enumerate(validation_result['missing_transactions'], 1):
                raw = missing['raw_transaction']
                report.append(f"  {i}. {raw['raw_date']} | {raw['raw_description'][:50]} | ${raw['raw_amount']}")
                if missing['possible_reasons']:
                    report.append(f"     Posibles razones: {', '.join(missing['possible_reasons'])}")

        # Validación de balances
        if validation_result.get('balance_validation'):
            bal_val = validation_result['balance_validation']
            if 'final_balance_check' in bal_val and bal_val['final_balance_check']:
                check = bal_val['final_balance_check']
                status = "✅" if check.get('is_valid', False) else "❌"
                report.append(f"\n💰 VALIDACIÓN DE BALANCE: {status}")
                if 'expected' in check:
                    report.append(f"  Esperado: ${check['expected']:,.2f}")
                if 'calculated' in check:
                    report.append(f"  Calculado: ${check['calculated']:,.2f}")
                if 'difference' in check:
                    report.append(f"  Diferencia: ${check['difference']:,.2f}")

        # Recomendaciones
        if validation_result['recommendations']:
            report.append(f"\n💡 RECOMENDACIONES:")
            for i, rec in enumerate(validation_result['recommendations'], 1):
                report.append(f"  {i}. {rec}")

        report.append(f"\n🕐 Timestamp: {validation_result['timestamp']}")
        report.append("=" * 60)

        return "\n".join(report)

def validate_pdf_extraction(pdf_text: str,
                          extracted_transactions: List[Dict],
                          initial_balance: Optional[float] = None,
                          final_balance: Optional[float] = None) -> Dict:
    """
    Función helper para validar una extracción de PDF
    """
    validator = PDFExtractionValidator()
    result = validator.validate_extraction_completeness(
        pdf_text,
        extracted_transactions,
        initial_balance,
        final_balance
    )

    # Log del reporte
    report = validator.generate_validation_report(result)
    logging.info("\n" + report)

    return result

if __name__ == "__main__":
    # Test básico
    print("🔍 PDF Extraction Validator - Sistema de validación para extracción de PDFs")
    print("Este módulo previene la pérdida de transacciones durante la extracción de PDFs bancarios")