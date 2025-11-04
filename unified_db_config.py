"""
Configuración para usar la nueva base de datos unificada
Reemplaza las múltiples conexiones de DB por una sola
"""

import sqlite3
from pathlib import Path
import os

# Ruta a la DB unificada
UNIFIED_DB_PATH = "/Users/danielgoes96/Desktop/mcp-server/unified_mcp_system.db"

class UnifiedDatabase:
    """Clase para manejar la conexión a la DB unificada"""

    def __init__(self):
        self.db_path = UNIFIED_DB_PATH
        self.ensure_db_exists()

    def ensure_db_exists(self):
        """Verifica que la DB existe"""
        if not Path(self.db_path).exists():
            raise FileNotFoundError(f"DB unificada no encontrada: {self.db_path}")

    def get_connection(self):
        """Obtiene una conexión a la DB unificada"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Para acceso por nombre de columna
        return conn

    def execute_query(self, query, params=None):
        """Ejecuta una query y retorna resultados"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()

    def execute_insert(self, query, params):
        """Ejecuta un INSERT y retorna el ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid

# Funciones de acceso específicas
def get_all_expenses(tenant_id=1):
    """Obtiene todos los gastos de un tenant"""
    db = UnifiedDatabase()
    return db.execute_query("""
        SELECT * FROM expense_records
        WHERE tenant_id = ?
        ORDER BY created_at DESC
    """, (tenant_id,))

def get_all_tickets(tenant_id=1):
    """Obtiene todos los tickets de un tenant"""
    db = UnifiedDatabase()
    return db.execute_query("""
        SELECT * FROM tickets
        WHERE tenant_id = ?
        ORDER BY created_at DESC
    """, (tenant_id,))

def get_automation_jobs(tenant_id=1, status=None):
    """Obtiene jobs de automatización"""
    db = UnifiedDatabase()
    query = "SELECT * FROM automation_jobs WHERE tenant_id = ?"
    params = [tenant_id]

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC"

    return db.execute_query(query, params)

def create_expense(amount, description, category, tenant_id=1, user_id=1):
    """Crea un nuevo gasto"""
    db = UnifiedDatabase()
    return db.execute_insert("""
        INSERT INTO expense_records
        (amount, description, category, tenant_id, user_id, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    """, (amount, description, category, tenant_id, user_id))

def get_gpt_usage_stats(tenant_id=1):
    """Obtiene estadísticas de uso de GPT"""
    db = UnifiedDatabase()
    return db.execute_query("""
        SELECT
            COUNT(*) as total_events,
            SUM(tokens_estimated) as total_tokens,
            SUM(cost_estimated_usd) as total_cost,
            AVG(confidence_after) as avg_confidence
        FROM gpt_usage_events
        WHERE tenant_id = ?
    """, (tenant_id,))

# Variable de configuración para el sistema
DB_CONFIG = {
    'type': 'sqlite',
    'path': UNIFIED_DB_PATH,
    'connection_class': UnifiedDatabase
}

if __name__ == "__main__":
    # Test de la conexión
    try:
        db = UnifiedDatabase()

        # Test queries
        expenses = get_all_expenses()
        print(f"✅ Gastos encontrados: {len(expenses)}")

        jobs = get_automation_jobs()
        print(f"✅ Jobs de automatización: {len(jobs)}")

        stats = get_gpt_usage_stats()
        print(f"✅ Stats de GPT: {stats}")

        print("🎉 Conexión a DB unificada exitosa!")

    except Exception as e:
        print(f"❌ Error: {e}")