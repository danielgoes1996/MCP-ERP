#!/usr/bin/env python3
"""
Sistema de prevención de duplicados para transacciones bancarias
Evita insertar transacciones duplicadas durante el parsing
"""
import sqlite3
import hashlib
from datetime import datetime, date
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class DuplicateDetector:
    """Detector y prevención de transacciones duplicadas"""

    def __init__(self, db_path: str = "unified_mcp_system.db"):
        self.db_path = db_path
        self.tolerance = 0.01  # Tolerancia para comparar montos (1 centavo)

    def generate_transaction_hash(self, date: date, amount: float, description: str, account_id: int) -> str:
        """Generar hash único para una transacción"""
        # Normalizar descripción (remover espacios extra, convertir a mayúsculas)
        normalized_desc = " ".join(description.strip().upper().split())

        # Crear string único
        unique_string = f"{date}|{amount:.2f}|{normalized_desc}|{account_id}"

        # Generar hash SHA256
        return hashlib.sha256(unique_string.encode()).hexdigest()

    def find_potential_duplicates(self, account_id: int, user_id: int,
                                 new_transactions: List[Dict]) -> List[Dict]:
        """Buscar posibles duplicados en transacciones nuevas"""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Obtener transacciones existentes
        cursor.execute("""
            SELECT date, amount, description, id
            FROM bank_movements
            WHERE account_id = ? AND user_id = ?
        """, (account_id, user_id))

        existing = cursor.fetchall()
        conn.close()

        # Crear conjunto de hashes existentes
        existing_hashes = set()
        for date_str, amount, desc, txn_id in existing:
            if date_str and amount is not None and desc:
                try:
                    txn_date = datetime.fromisoformat(date_str).date()
                    hash_val = self.generate_transaction_hash(txn_date, amount, desc, account_id)
                    existing_hashes.add(hash_val)
                except:
                    continue

        # Filtrar transacciones nuevas
        filtered_transactions = []
        new_hashes = set()

        for txn in new_transactions:
            if not all(k in txn for k in ['date', 'amount', 'description']):
                continue

            try:
                txn_date = txn['date'] if isinstance(txn['date'], date) else datetime.fromisoformat(str(txn['date'])).date()
                hash_val = self.generate_transaction_hash(txn_date, txn['amount'], txn['description'], account_id)

                # Verificar si es duplicado
                if hash_val not in existing_hashes and hash_val not in new_hashes:
                    filtered_transactions.append(txn)
                    new_hashes.add(hash_val)
                else:
                    logger.warning(f"🚫 Duplicado detectado: {txn['description']} - ${txn['amount']}")

            except Exception as e:
                logger.error(f"Error procesando transacción: {e}")
                continue

        logger.info(f"✅ Filtradas {len(new_transactions) - len(filtered_transactions)} duplicaciones")
        return filtered_transactions

    def detect_spei_pairs(self, transactions: List[Dict]) -> List[Dict]:
        """Detectar y eliminar pares SPEI duplicados (positivo/negativo del mismo monto)"""

        # Agrupar por fecha y descripción similar
        groups = {}

        for i, txn in enumerate(transactions):
            if 'SPEI' in txn.get('description', '').upper():
                key = (
                    txn.get('date'),
                    abs(txn.get('amount', 0)),
                    'SPEI'  # Clave genérica para SPEI
                )

                if key not in groups:
                    groups[key] = []
                groups[key].append((i, txn))

        # Identificar duplicados
        to_remove = set()

        for key, group in groups.items():
            if len(group) > 1:
                # Si hay múltiples transacciones SPEI del mismo monto en la misma fecha
                [txn['amount'] for _, txn in group]

                # Buscar pares positivo/negativo
                for i, (idx1, txn1) in enumerate(group):
                    for j, (idx2, txn2) in enumerate(group[i+1:], i+1):
                        if abs(txn1['amount'] + txn2['amount']) < self.tolerance:
                            # Par encontrado - mantener solo el positivo o el más lógico
                            if txn1['amount'] < 0:
                                to_remove.add(idx1)
                            else:
                                to_remove.add(idx2)
                            logger.warning(f"🔄 Par SPEI detectado: ${txn1['amount']} / ${txn2['amount']}")

        # Filtrar transacciones
        filtered = [txn for i, txn in enumerate(transactions) if i not in to_remove]

        if to_remove:
            logger.info(f"✅ Eliminados {len(to_remove)} duplicados SPEI")

        return filtered

    def clean_existing_duplicates(self, account_id: int, user_id: int) -> int:
        """Limpiar duplicados existentes en la base de datos"""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Buscar duplicados exactos
        cursor.execute("""
            SELECT description, date, amount, COUNT(*) as count, GROUP_CONCAT(id) as ids
            FROM bank_movements
            WHERE account_id = ? AND user_id = ?
            GROUP BY description, date, amount
            HAVING COUNT(*) > 1
        """, (account_id, user_id))

        duplicates = cursor.fetchall()
        deleted_count = 0

        for desc, date, amount, count, ids_str in duplicates:
            ids = [int(id) for id in ids_str.split(',')]
            # Mantener solo el primer ID, eliminar el resto
            for id_to_delete in ids[1:]:
                cursor.execute("DELETE FROM bank_movements WHERE id = ?", (id_to_delete,))
                deleted_count += 1
                logger.info(f"🗑️ Eliminado duplicado ID {id_to_delete}: {desc}")

        conn.commit()
        conn.close()

        return deleted_count

def apply_duplicate_prevention():
    """Aplicar prevención de duplicados al sistema existente"""

    detector = DuplicateDetector()

    # Limpiar duplicados existentes
    print("🧹 Limpiando duplicados existentes...")
    deleted = detector.clean_existing_duplicates(5, 9)  # AMEX Gold

    if deleted > 0:
        print(f"✅ Eliminados {deleted} duplicados existentes")
    else:
        print("✅ No se encontraron duplicados existentes")

    print("\n🛡️ Sistema de prevención de duplicados configurado")
    return detector

if __name__ == "__main__":
    # Aplicar limpieza a las transacciones existentes
    apply_duplicate_prevention()