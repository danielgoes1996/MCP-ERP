#!/usr/bin/env python3
"""
Sistema de patrones universales para parsing de estados de cuenta bancarios
Soporta múltiples formatos y variaciones de bancos mexicanos
"""
import re
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class UniversalBankPatterns:
    """Patrones universales que se adaptan a diferentes formatos bancarios"""

    def __init__(self):
        # Meses en español (múltiples formatos)
        self.months_patterns = {
            'ENE': ['ENE', 'ENERO', 'JAN'],
            'FEB': ['FEB', 'FEBRERO', 'FEB'],
            'MAR': ['MAR', 'MARZO', 'MAR'],
            'ABR': ['ABR', 'ABRIL', 'APR'],
            'MAY': ['MAY', 'MAYO', 'MAY'],
            'JUN': ['JUN', 'JUNIO', 'JUN'],
            'JUL': ['JUL', 'JULIO', 'JUL'],
            'AGO': ['AGO', 'AGOSTO', 'AUG'],
            'SEP': ['SEP', 'SEPTIEMBRE', 'SEP'],
            'OCT': ['OCT', 'OCTUBRE', 'OCT'],
            'NOV': ['NOV', 'NOVIEMBRE', 'NOV'],
            'DIC': ['DIC', 'DICIEMBRE', 'DEC']
        }

        # Patrones base flexibles
        self.base_patterns = self._create_flexible_patterns()

    def _create_flexible_patterns(self) -> Dict[str, List[str]]:
        """Crea patrones flexibles que manejan variaciones"""

        # Todos los meses con variaciones
        all_months = []
        for month_variants in self.months_patterns.values():
            all_months.extend(month_variants)
        month_regex = '|'.join(all_months)

        patterns = {
            # Patrones de fecha flexibles
            'date_patterns': [
                # Formato: MAR 11, JUL. 01, DIC. 02
                rf'({month_regex})\.?\s+(\d{{1,2}})',
                # Formato: 11 MAR, 01 JUL., 02 DIC.
                rf'(\d{{1,2}})\s+({month_regex})\.?',
                # Formato: 11-MAR-2024, 01/JUL/2025
                rf'(\d{{1,2}})[-/]({month_regex})[-/](\d{{4}})',
                # Formato: MAR-11-2024, JUL/01/2025
                rf'({month_regex})[-/](\d{{1,2}})[-/](\d{{4}})'
            ],

            # Patrones de transacción Inbursa (múltiples formatos)
            'inbursa_transaction_patterns': [
                # Formato: DIC. 01 3218488397 HOME DEPOT MX 224.00 78,388.80
                rf'({month_regex})\.?\s+(\d{{1,2}})\s+(\d{{8,12}})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)$',
                # Formato: MAR 11 2914060253 GPDC EJERCITO MX 700.00 16,739.10
                rf'({month_regex})\s+(\d{{1,2}})\s+(\d{{8,12}})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)$',
                # Formato con día+referencia pegados: MAR 042906826222 WM EXPRESS PAB CAMPSTR MX 322.02 19,917.83
                rf'({month_regex})\s+(\d{{2}})(\d{{10}})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)$',
                # Formato balance: DIC. 01 BALANCE INICIAL 78,612.80
                rf'({month_regex})\.?\s+(\d{{1,2}})\s+(BALANCE\s+INICIAL|SALDO\s+ANTERIOR)\s+([\d,]+\.?\d*)$',
                # Formato sin referencia: MAR 15 DEPOSITO SPEI 1,260.00 21,365.09
                rf'({month_regex})\.?\s+(\d{{1,2}})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)$'
            ],

            # Patrones de balance/saldo
            'balance_patterns': [
                r'SALDO\s+(ANTERIOR|INICIAL)\s+([\d,]+\.?\d*)',
                r'BALANCE\s+(INICIAL|ANTERIOR)\s+([\d,]+\.?\d*)',
                r'SALDO\s+(ACTUAL|FINAL)\s+([\d,]+\.?\d*)',
                r'BALANCE\s+(ACTUAL|FINAL)\s+([\d,]+\.?\d*)'
            ],

            # Patrones de montos (más flexibles)
            'amount_patterns': [
                r'[\d,]+\.\d{2}',  # 1,234.56
                r'\d+\.\d{2}',     # 234.56
                r'[\d,]+\d',       # 1,234 o 1234
                r'\d+',            # 123
            ]
        }

        return patterns

    def extract_transactions_flexible(self, text: str, bank_type: str = 'inbursa') -> List[Dict[str, Any]]:
        """Extrae transacciones usando patrones flexibles"""
        transactions = []
        lines = text.split('\n')

        logger.info(f"🔍 Iniciando extracción flexible para {bank_type}")

        for line_num, line in enumerate(lines, 1):
            line_clean = line.strip()
            if not line_clean:
                continue

            # Probar cada patrón de transacción
            for pattern_name, patterns in self.base_patterns.items():
                if pattern_name.endswith('_transaction_patterns'):
                    for pattern in patterns:
                        try:
                            match = re.match(pattern, line_clean, re.IGNORECASE)
                            if match:
                                transaction = self._parse_transaction_match(match, pattern, line_clean, line_num)
                                if transaction:
                                    transactions.append(transaction)
                                    logger.debug(f"✅ Línea {line_num}: {pattern_name} → {transaction}")
                                    break
                        except Exception as e:
                            logger.debug(f"⚠️ Error en patrón {pattern}: {e}")
                            continue
                    else:
                        continue
                    break  # Si encontró match, no probar más patrones

        logger.info(f"📊 Extraídas {len(transactions)} transacciones con patrones flexibles")
        return transactions

    def _parse_transaction_match(self, match: re.Match, pattern: str, line: str, line_num: int) -> Optional[Dict[str, Any]]:
        """Parsea un match de transacción y devuelve diccionario estructurado"""
        try:
            groups = match.groups()

            # Determinar el formato basado en los grupos
            if len(groups) >= 6:  # Transacción completa con referencia
                month, day, reference, description, amount, balance = groups[:6]
                # Verificar si es formato pegado (día+referencia en un solo grupo)
                if len(reference) == 10 and reference.isdigit():
                    # Formato pegado: MAR 042906826222
                    actual_day = day  # Ya extraído como día de 2 dígitos
                    actual_reference = reference  # Ya extraído como referencia de 10 dígitos
                else:
                    actual_day = day
                    actual_reference = reference

                return {
                    'line_number': line_num,
                    'raw_line': line,
                    'month': month.upper(),
                    'day': int(actual_day),
                    'reference': actual_reference,
                    'description': description.strip(),
                    'amount': self._parse_amount(amount),
                    'balance': self._parse_amount(balance),
                    'pattern_used': 'complete_transaction',
                    'confidence': 0.9
                }
            elif len(groups) >= 5:  # Transacción sin referencia o balance
                month, day, description, amount, balance = groups[:5]
                return {
                    'line_number': line_num,
                    'raw_line': line,
                    'month': month.upper(),
                    'day': int(day),
                    'reference': None,
                    'description': description.strip(),
                    'amount': self._parse_amount(amount),
                    'balance': self._parse_amount(balance),
                    'pattern_used': 'simple_transaction',
                    'confidence': 0.8
                }
            elif len(groups) >= 3:  # Balance inicial
                month, day, amount = groups[:3]
                return {
                    'line_number': line_num,
                    'raw_line': line,
                    'month': month.upper(),
                    'day': int(day),
                    'reference': None,
                    'description': 'BALANCE INICIAL',
                    'amount': 0.0,
                    'balance': self._parse_amount(amount),
                    'pattern_used': 'balance_inicial',
                    'confidence': 0.95
                }

        except Exception as e:
            logger.debug(f"Error parseando match en línea {line_num}: {e}")
            return None

        return None

    def _parse_amount(self, amount_str: str) -> float:
        """Parsea string de monto a float"""
        try:
            # Remover comas y espacios
            clean_amount = re.sub(r'[,\s]', '', amount_str.strip())
            return float(clean_amount)
        except (ValueError, AttributeError):
            return 0.0

    def detect_date_format(self, text: str) -> Dict[str, Any]:
        """Detecta el formato de fecha usado en el texto"""
        formats_found = {}

        for pattern in self.base_patterns['date_patterns']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                formats_found[pattern] = len(matches)

        # Determinar formato predominante
        if formats_found:
            main_format = max(formats_found, key=formats_found.get)
            return {
                'main_format': main_format,
                'all_formats': formats_found,
                'confidence': 'high' if formats_found[main_format] > 5 else 'medium'
            }

        return {'main_format': None, 'all_formats': {}, 'confidence': 'low'}

    def normalize_month(self, month_str: str) -> str:
        """Normaliza mes a formato estándar (3 letras)"""
        month_upper = month_str.upper().strip('.')

        for standard, variants in self.months_patterns.items():
            if month_upper in variants:
                return standard

        return month_str.upper()

    def create_adaptive_pattern(self, sample_transactions: List[str]) -> str:
        """Crea un patrón adaptativo basado en transacciones de muestra"""
        logger.info(f"🔧 Creando patrón adaptativo basado en {len(sample_transactions)} muestras")

        # Analizar las muestras para determinar el formato
        format_analysis = {}

        for sample in sample_transactions:
            # Detectar elementos comunes
            parts = sample.split()
            if len(parts) >= 4:
                # Posible formato: MONTH DAY REF DESC AMOUNT BALANCE
                month_candidate = parts[0]
                if self.normalize_month(month_candidate) in self.months_patterns:
                    format_key = f"month_day_{len(parts)}_parts"
                    format_analysis[format_key] = format_analysis.get(format_key, 0) + 1

        # Generar patrón optimizado
        if format_analysis:
            best_format = max(format_analysis, key=format_analysis.get)
            logger.info(f"✅ Formato detectado: {best_format}")

            # Crear patrón específico para el formato detectado
            month_regex = '|'.join(sum(self.months_patterns.values(), []))
            if 'month_day' in best_format:
                return rf'({month_regex})\.?\s+(\d{{1,2}})\s+(\d{{8,12}})?\s*(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)$'

        # Fallback: patrón general
        month_regex = '|'.join(sum(self.months_patterns.values(), []))
        return rf'({month_regex})\.?\s+(\d{{1,2}})\s+(.+?)\s+([\d,]+\.?\d*)$'


# Instancia global
universal_patterns = UniversalBankPatterns()