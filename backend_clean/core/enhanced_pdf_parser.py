#!/usr/bin/env python3
"""
Enhanced PDF parser with proper amount handling and AI categorization
"""
import re
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
from core.bank_statements_models import (
    BankTransaction,
    MovementKind,
    TransactionType,
    infer_movement_kind,
    should_skip_transaction,
)

logger = logging.getLogger(__name__)


class EnhancedPDFParser:
    def __init__(self):
        # Categorías automáticas basadas en patrones
        self.category_patterns = {
            'Ingreso': [
                r'deposito\s+spei', r'transferencia\s+recibida', r'balance\s+inicial',
                r'nomina', r'pago\s+cliente', r'reembolso', r'interes'
            ],
            'Gasto': [
                r'comision', r'anualidad', r'openai', r'apple\.com', r'amazon',
                r'uber', r'spotify', r'netflix', r'google', r'microsoft'
            ],
            'Transferencia': [
                r'traspaso', r'transferencia\s+a', r'spei\s+enviado'
            ],
            'Bancario': [
                r'cargo\s+por', r'iva', r'manejo\s+cuenta', r'disposicion'
            ]
        }

    def clean_description(self, raw_description: str) -> str:
        """Limpia y mejora la descripción de la transacción"""
        # Remover números de referencia largos del inicio
        desc = re.sub(r'^\d{8,12}\s+', '', raw_description)

        # Limpiar espacios múltiples
        desc = re.sub(r'\s+', ' ', desc).strip()

        # Mejorar descripciones conocidas
        improvements = {
            r'OPENAI \*CHATGPT SUBSCR.*': 'Suscripción OpenAI ChatGPT',
            r'APPLE\.COM/BILL.*': 'Compra Apple Store',
            r'DEPOSITO SPEI.*': 'Depósito SPEI',
            r'BALANCE INICIAL': 'Saldo inicial',
            r'COMISION.*MANEJO.*': 'Comisión manejo de cuenta',
        }

        for pattern, replacement in improvements.items():
            if re.search(pattern, desc, re.IGNORECASE):
                desc = replacement
                break

        return desc[:200]  # Limitar longitud

    def categorize_transaction(self, description: str, amount: float, transaction_type: TransactionType) -> Tuple[str, float]:
        """Categoriza automáticamente la transacción y asigna confianza"""
        desc_lower = description.lower()

        # Buscar patrones en categorías
        for category, patterns in self.category_patterns.items():
            for pattern in patterns:
                if re.search(pattern, desc_lower):
                    confidence = 0.9 if len(pattern) > 10 else 0.7
                    return category, confidence

        # Categorización por tipo y monto
        if transaction_type == TransactionType.CREDIT:
            if amount > 10000:
                return 'Ingreso', 0.6
            else:
                return 'Reembolso', 0.5
        else:
            if amount < 50:
                return 'Bancario', 0.6
            elif amount > 5000:
                return 'Gasto', 0.6
            else:
                return 'Gasto', 0.5

        return 'Sin categoría', 0.1

    def parse_banco_inbursa_line(self, line: str, account_id: int, user_id: int, tenant_id: int) -> Optional[BankTransaction]:
        """Parsea una línea específica del formato Banco Inbursa"""

        # Patrón mejorado: JUL. 01 3487607541 OPENAI *CHATGPT SUBSCR US 20.0 USD /TC 378.85 38,208.57
        pattern = r'(JUL\.\s+\d{1,2})\s+(\d{8,12})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)$'

        match = re.search(pattern, line.strip())
        if not match:
            # Patrón alternativo para líneas sin referencia: JUL. 01 BALANCE INICIAL 38,587.42
            pattern2 = r'(JUL\.\s+\d{1,2})\s+(BALANCE\s+INICIAL|DEPOSITO\s+SPEI[^0-9]*)\s+([\d,]+\.?\d*)$'
            match = re.search(pattern2, line.strip())

            if match:
                date_str, description, amount_str = match.groups()
                reference = None
            else:
                return None
        else:
            date_str, reference, description, amount_str, balance_str = match.groups()

        try:
            # Extraer fecha
            day = date_str.replace("JUL.", "").strip()
            transaction_date = datetime(2025, 7, int(day)).date()

            # Parsear monto correctamente (el primer número después de la descripción)
            amount = float(amount_str.replace(',', ''))

            # Validar que el monto sea razonable
            if amount <= 0 or amount > 1000000:
                logger.warning(f"Monto inválido detectado: {amount} en línea: {line[:100]}")
                return None

            # Determinar tipo de transacción
            transaction_type = TransactionType.CREDIT if any(keyword in description.lower() for keyword in
                ['deposito', 'spei', 'balance inicial', 'transferencia recibida']) else TransactionType.DEBIT

            # Limpiar descripción
            cleaned_desc = self.clean_description(description)

            # Categorizar automáticamente
            category, confidence = self.categorize_transaction(cleaned_desc, amount, transaction_type)

            # Crear descripción final con referencia si existe
            final_description = f"{cleaned_desc} (Ref: {reference})" if reference else cleaned_desc

            if should_skip_transaction(final_description):
                return None

            final_description = re.sub(r'\(\s*\)', '', final_description).strip()

            movement_kind = infer_movement_kind(transaction_type, final_description)

            return BankTransaction(
                account_id=account_id,
                user_id=user_id,
                tenant_id=tenant_id,
                date=transaction_date,
                description=final_description,
                amount=amount,
                transaction_type=transaction_type,
                raw_data=line[:1000],
                # Campos nuevos para categorización
                category=category,
                confidence=confidence,
                movement_kind=movement_kind
            )

        except Exception as e:
            logger.warning(f"Error parseando línea: {e} - Línea: {line[:100]}")
            return None

    def fix_existing_transactions(self, db_connection):
        """Corrige transacciones existentes con montos incorrectos"""
        cursor = db_connection.cursor()

        # Buscar transacciones con montos irreales
        cursor.execute("""
            SELECT id, raw_data, amount
            FROM bank_movements
            WHERE amount > 1000000 OR amount < 0
        """)

        problematic_transactions = cursor.fetchall()
        fixed_count = 0

        for trans_id, raw_data, current_amount in problematic_transactions:
            if raw_data:
                # Intentar re-parsear la línea original
                transaction = self.parse_banco_inbursa_line(raw_data, 1, 1, 1)

                if transaction and transaction.amount != current_amount:
                    # Actualizar con el monto correcto
                    cursor.execute("""
                        UPDATE bank_movements
                        SET amount = ?,
                            cleaned_description = ?,
                            category_auto = ?,
                            confidence_score = ?
                        WHERE id = ?
                    """, (
                        transaction.amount,
                        self.clean_description(transaction.description),
                        transaction.category,
                        transaction.confidence,
                        trans_id
                    ))
                    fixed_count += 1
                    logger.info(f"Corregido monto: ${current_amount:,.2f} → ${transaction.amount:,.2f}")

        db_connection.commit()
        logger.info(f"Se corrigieron {fixed_count} transacciones con montos incorrectos")
        return fixed_count


def fix_transaction_amounts():
    """Función para corregir montos de transacciones existentes"""
    import sqlite3

    parser = EnhancedPDFParser()

    with sqlite3.connect('unified_mcp_system.db') as conn:
        fixed_count = parser.fix_existing_transactions(conn)

        # También actualizar descripciones limpias para todas las transacciones
        cursor = conn.cursor()
        cursor.execute("SELECT id, description FROM bank_movements WHERE cleaned_description IS NULL")

        for trans_id, description in cursor.fetchall():
            cleaned = parser.clean_description(description)
            category, confidence = parser.categorize_transaction(cleaned, 100, TransactionType.DEBIT)

            cursor.execute("""
                UPDATE bank_movements
                SET cleaned_description = ?, category_auto = ?, confidence_score = ?
                WHERE id = ?
            """, (cleaned, category, confidence, trans_id))

        conn.commit()

    return fixed_count


if __name__ == "__main__":
    # Ejecutar corrección si se llama directamente
    fixed = fix_transaction_amounts()
    print(f"✅ Corregidas {fixed} transacciones")
