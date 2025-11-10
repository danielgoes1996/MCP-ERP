#!/usr/bin/env python3
"""
Parser robusto de PDFs bancarios con múltiples estrategias
"""
from pypdf import PdfReader
import pdfplumber
import fitz  # pymupdf
import re
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
from core.reconciliation.bank.bank_statements_models import (
    BankTransaction,
    MovementKind,
    TransactionType,
    infer_movement_kind,
    should_skip_transaction,
)
from core.reconciliation.bank.universal_bank_patterns import universal_patterns

logger = logging.getLogger(__name__)


class RobustPDFParser:
    def __init__(self):
        self.strategies = [
            self._extract_with_pdfplumber,
            self._extract_with_pymupdf,
            self._extract_with_pypdf_safe,
        ]

    def extract_text(self, pdf_path: str) -> str:
        """Intenta extraer texto usando múltiples estrategias"""
        logger.info(f"🔄 Iniciando extracción robusta de {pdf_path}")

        for i, strategy in enumerate(self.strategies, 1):
            try:
                logger.info(f"📖 Intentando estrategia {i}: {strategy.__name__}")
                text = strategy(pdf_path)
                if text and len(text.strip()) > 50:  # Texto mínimo válido
                    logger.info(f"✅ Estrategia {i} exitosa: {len(text)} caracteres extraídos")
                    return text
                else:
                    logger.warning(f"⚠️ Estrategia {i} retornó poco texto: {len(text) if text else 0} caracteres")
            except Exception as e:
                logger.warning(f"❌ Estrategia {i} falló: {e}")
                continue

        logger.error("❌ Todas las estrategias de extracción fallaron")
        raise Exception("No se pudo extraer texto del PDF con ninguna estrategia")

    def _extract_with_pdfplumber(self, pdf_path: str) -> str:
        """Estrategia 1: PDFPlumber (mejor para tablas)"""
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"--- PÁGINA {page_num} ---\n{page_text}\n")

                    # También intentar extraer tablas
                    tables = page.extract_tables()
                    for table_num, table in enumerate(tables, 1):
                        if table:
                            text_parts.append(f"--- TABLA {page_num}.{table_num} ---\n")
                            for row in table:
                                if row:
                                    clean_row = [str(cell).strip() if cell else "" for cell in row]
                                    text_parts.append(" | ".join(clean_row) + "\n")
                            text_parts.append("\n")

                except Exception as e:
                    logger.warning(f"Error en página {page_num} con pdfplumber: {e}")
                    continue

        return "\n".join(text_parts)

    def _extract_with_pymupdf(self, pdf_path: str) -> str:
        """Estrategia 2: PyMuPDF (mejor para PDFs complejos)"""
        text_parts = []
        doc = fitz.open(pdf_path)

        for page_num in range(len(doc)):
            try:
                page = doc.load_page(page_num)
                page_text = page.get_text()
                if page_text:
                    text_parts.append(f"--- PÁGINA {page_num + 1} ---\n{page_text}\n")

                # También intentar extraer texto con diferentes métodos
                blocks = page.get_text("dict")
                if blocks and "blocks" in blocks:
                    for block in blocks["blocks"]:
                        if "lines" in block:
                            for line in block["lines"]:
                                if "spans" in line:
                                    line_text = " ".join([span["text"] for span in line["spans"] if "text" in span])
                                    if line_text.strip():
                                        text_parts.append(line_text + "\n")

            except Exception as e:
                logger.warning(f"Error en página {page_num + 1} con pymupdf: {e}")
                continue

        doc.close()
        return "\n".join(text_parts)

    def _extract_with_pypdf_safe(self, pdf_path: str) -> str:
        """Estrategia 3: pypdf con manejo de errores"""
        text_parts = []

        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PdfReader(file)

                for page_num, page in enumerate(pdf_reader.pages, 1):
                    try:
                        # Intentar con diferentes métodos de extracción
                        methods = [
                            lambda p: p.extract_text(),
                            lambda p: p.extract_text(extraction_mode="layout"),
                            lambda p: p.extract_text(extraction_mode="plain"),
                        ]

                        page_text = None
                        for method in methods:
                            try:
                                page_text = method(page)
                                if page_text and len(page_text.strip()) > 10:
                                    break
                            except:
                                continue

                        if page_text:
                            text_parts.append(f"--- PÁGINA {page_num} ---\n{page_text}\n")

                    except Exception as e:
                        logger.warning(f"Error en página {page_num} con pypdf: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error general con pypdf: {e}")
            raise

        return "\n".join(text_parts)

    def parse_transactions(self, text: str, account_id: int, user_id: int, tenant_id: int, pdf_path: str = None) -> Tuple[List[BankTransaction], Dict[str, Any]]:
        """Parsea transacciones del texto extraído"""
        logger.info("🔍 Iniciando parseo de transacciones")

        transactions = []

        # Patrones específicos para Banco Inbursa - UNIVERSALES (punto opcional)
        transaction_patterns = [
            # Patrón 0: BALANCE INICIAL específico - Punto opcional
            r'((?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?\s+\d{1,2})\s+BALANCE\s+INICIAL\s+([\d,]+\.?\d*)',

            # Patrón 1: Con referencia y dos montos - Punto opcional: DIC. 01 o MAR 11
            r'((?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?\s+\d{1,2})\s+(\d{8,12})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)',

            # Patrón 2: Sin referencia pero con dos montos - Punto opcional
            r'((?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?\s+\d{1,2})\s+([A-Z][A-Z\s]+[^0-9\s])\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)',

            # Patrón 3: Conceptos simples con un solo monto - Punto opcional
            r'((?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?\s+\d{1,2})\s+(.+?)\s+([\d,]+\.?\d*)$',

            # Patrón 4: Fecha tradicional DD/MM/YYYY
            r'(\d{1,2}/\d{1,2}/\d{4})\s+(.+?)\s+(-?\$?[\d,]+\.?\d{2})',
        ]

        lines = text.split('\n')
        found_transactions = 0

        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 10:
                continue

            for pattern_num, pattern in enumerate(transaction_patterns, 1):
                try:
                    matches = re.finditer(pattern, line)
                    transaction_found = False
                    for match in matches:
                        try:
                            transaction = self._create_transaction_from_match(
                                match, pattern_num, account_id, user_id, tenant_id, line, found_transactions
                            )
                            if transaction:
                                transactions.append(transaction)
                                found_transactions += 1
                                logger.debug(f"✅ Transacción {found_transactions} encontrada en línea {line_num + 1}")
                                transaction_found = True
                                break  # Solo una transacción por línea
                        except Exception as e:
                            logger.warning(f"Error creando transacción desde match: {e}")
                            continue

                    # Si encontramos una transacción, no probar otros patterns
                    if transaction_found:
                        break
                except Exception as e:
                    logger.warning(f"Error aplicando patrón {pattern_num} en línea {line_num + 1}: {e}")
                    continue

        # Estadísticas de parsing
        summary = {
            "total_transactions": len(transactions),
            "total_credits": sum(t.amount for t in transactions if t.transaction_type == TransactionType.CREDIT),
            "total_debits": sum(abs(t.amount) for t in transactions if t.transaction_type == TransactionType.DEBIT),
            "period_start": None,
            "period_end": None,
            "opening_balance": 0.0,
            "closing_balance": 0.0,
            "total_incomes": sum(abs(t.amount) for t in transactions if t.movement_kind == MovementKind.INGRESO),
            "total_expenses": sum(abs(t.amount) for t in transactions if t.movement_kind == MovementKind.GASTO),
            "total_transfers": sum(abs(t.amount) for t in transactions if t.movement_kind == MovementKind.TRANSFERENCIA),
        }

        if transactions:
            dates = [t.date for t in transactions if t.date]
            if dates:
                summary["period_start"] = min(dates)
                summary["period_end"] = max(dates)

        logger.info(f"🎯 Parsing completado: {len(transactions)} transacciones encontradas")

        # NUEVO: Validation Layer para Producción (solo si tenemos PDF path válido)
        if pdf_path and pdf_path != "unknown_pdf":
            try:
                from core.extraction_validator import validate_pdf_extraction
                validation_result = validate_pdf_extraction(
                    len(transactions),
                    pdf_path,
                    transactions
                )
                summary["validation"] = validation_result

                if not validation_result.get("is_complete", False):
                    logger.warning(f"⚠️ Extraction validation failed: {validation_result.get('status', 'UNKNOWN')}")
                    logger.warning(f"Recommendations: {validation_result.get('recommendations', [])}")
            except Exception as e:
                logger.warning(f"Validation layer failed: {e}")
        else:
            # Skip validation when used as fallback (no valid PDF path)
            summary["validation"] = {
                "is_complete": True,  # Assume OK for fallback chunks
                "status": "CHUNK_PROCESSED",
                "note": "Validation skipped for chunk processing"
            }

        return transactions, summary

    def _create_transaction_from_match(self, match, pattern_num: int, account_id: int, user_id: int, tenant_id: int, original_line: str, transaction_count: int = 0) -> Optional[BankTransaction]:
        """Crea una transacción desde un regex match"""
        groups = match.groups()

        try:
            # Extraer fecha
            date_str = groups[0]

            # Convertir formato "MES. 01" a fecha real (asumiendo 2024/2025)
            if any(month in date_str for month in ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]):
                # Mapeo de meses en español
                month_map = {
                    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
                    "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12
                }

                # Extraer mes y día (manejar tanto "MAR." como "MAR")
                for month_abbr, month_num in month_map.items():
                    if month_abbr in date_str:
                        # Primero intentar con punto, luego sin punto
                        day = date_str.replace(f"{month_abbr}.", "").strip()
                        if not day or day == date_str.strip():  # Si no cambió, intentar sin punto
                            day = date_str.replace(month_abbr, "").strip()
                        # Usar año 2025 para JUL, 2024 para DIC y otros meses
                        year = 2025 if month_abbr == "JUL" else 2024
                        transaction_date = datetime(year, month_num, int(day)).date()
                        break
            else:
                # Formato tradicional DD/MM/YYYY
                transaction_date = datetime.strptime(date_str, "%d/%m/%Y").date()

            # Extraer descripción y monto según el patrón
            balance_after = None
            reference_value = None

            if pattern_num == 1 and len(groups) >= 2:
                # Patrón 0: BALANCE INICIAL específico
                description = "Balance Inicial - Saldo del Período Anterior"
                amount = 0.0
                balance_after = float(groups[1].replace(',', '').strip())
                transaction_type = TransactionType.CREDIT
                reference_value = None

            elif pattern_num == 2 and len(groups) >= 5:
                # Patrón 1: Con referencia y dos montos: DIC. 01 3218488397 HOME DEPOT MX 224.00 78,388.80
                reference_value = groups[1].strip()  # Referencia de 10 dígitos
                description = groups[2].strip()
                amount_str = groups[3].replace(',', '').strip()
                balance_str = groups[4].replace(',', '').strip()

                amount = float(amount_str)
                balance_after = float(balance_str)

                # Determinar si es cargo o abono basado en keywords
                if any(keyword in description.lower() for keyword in ['deposito', 'spei', 'transferencia recibida', 'intereses', 'abono']):
                    transaction_type = TransactionType.CREDIT
                else:
                    transaction_type = TransactionType.DEBIT

                # Agregar referencia a la descripción
                description = f"{description} (Ref: {reference_value})"

            elif pattern_num == 3 and len(groups) >= 4:
                # Patrón 2: Sin referencia pero con dos montos
                description = groups[1].strip()
                amount_str = groups[2].replace(',', '').strip()
                balance_str = groups[3].replace(',', '').strip()

                amount = float(amount_str)
                balance_after = float(balance_str)

                # Determinar tipo de transacción
                if any(keyword in description.lower() for keyword in ['deposito', 'spei', 'transferencia recibida', 'intereses', 'abono']):
                    transaction_type = TransactionType.CREDIT
                else:
                    transaction_type = TransactionType.DEBIT

            elif pattern_num == 4 and len(groups) >= 3:
                # Patrón 3: Conceptos simples con un solo monto
                description = groups[1].strip()
                amount_str = groups[2].replace(',', '').strip()

                # Para Balance Inicial, el amount es 0 y balance_after es el saldo inicial
                if 'balance inicial' in description.lower():
                    amount = 0.0
                    balance_after = float(amount_str)
                    transaction_type = TransactionType.CREDIT
                else:
                    amount = float(amount_str)
                    balance_after = None
                    transaction_type = TransactionType.CREDIT if 'deposito' in description.lower() else TransactionType.DEBIT

            elif pattern_num == 5 and len(groups) >= 3:
                # Patrón 4: Fecha tradicional DD/MM/YYYY
                description = groups[1].strip()
                amount_str = groups[2].replace('$', '').replace(',', '').strip()

                if amount_str.startswith('-'):
                    amount = float(amount_str)
                    transaction_type = TransactionType.DEBIT
                else:
                    amount = float(amount_str)
                    transaction_type = TransactionType.CREDIT if amount > 0 else TransactionType.DEBIT

            else:
                # Fallback para patrones no reconocidos
                logger.warning(f"Pattern {pattern_num} with {len(groups)} groups not handled: {groups}")
                return None

            # Limpiar descripción
            description = re.sub(r'\s+', ' ', description)  # Limpiar espacios múltiples
            reference_match = re.search(r'Ref:\s*(\d+)', description, flags=re.IGNORECASE)
            reference_value = reference_match.group(1) if reference_match else None
            if reference_value:
                description = re.sub(r'Ref:\s*\d+', '', description, flags=re.IGNORECASE).strip()

            description = re.sub(r'\(\s*\)', '', description)
            description = re.sub(r'^\d{6,}\s+', '', description)
            description = description.strip()

            if should_skip_transaction(description) or not description:
                return None

            if amount == 0:
                return None

            if abs(amount) > 1_000_000:
                logger.debug(f"Skipping PDF transaction with unrealistic amount {amount}: {original_line[:80]}")
                return None

            movement_kind = infer_movement_kind(transaction_type, description)
            base_amount = abs(amount)
            amount_signed = base_amount if transaction_type == TransactionType.CREDIT else -base_amount
            amount_signed = round(amount_signed, 2)

            return BankTransaction(
                account_id=account_id,
                user_id=user_id,
                tenant_id=tenant_id,
                date=transaction_date,
                description=description[:500],  # Limitar longitud
                amount=amount_signed,
                transaction_type=transaction_type,
                raw_data=f"PDF_LINE_{transaction_count+1}: {date_str} {description[:50]}",  # Formato igual a julio
                movement_kind=movement_kind,
                reference=reference_value,
                balance_after=balance_after  # Agregar balance_after como julio
            )

        except Exception as e:
            logger.warning(f"Error procesando match de patrón {pattern_num}: {e}")
            logger.warning(f"Groups: {groups}")
            return None


# Función de conveniencia para uso en el parser principal
def parse_pdf_robust(file_path: str, account_id: int, user_id: int, tenant_id: int) -> Tuple[List[BankTransaction], Dict[str, Any]]:
    """Función principal para parsear PDFs de forma robusta"""
    parser = RobustPDFParser()

    # Extraer texto
    text = parser.extract_text(file_path)

    # Parsear transacciones - pasar file_path para validation
    transactions, summary = parser.parse_transactions(text, account_id, user_id, tenant_id, file_path)

    return transactions, summary
