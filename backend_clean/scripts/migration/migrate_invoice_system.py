#!/usr/bin/env python3
"""
Migración para agregar sistema completo de facturas
"""

import sqlite3

def migrate_invoice_system():
    """Agregar columnas para manejo completo de facturas"""

    print("=== MIGRACIÓN: SISTEMA DE FACTURAS ===")

    conn = sqlite3.connect('./data/mcp_internal.db')
    cursor = conn.cursor()

    # Nuevas columnas para manejo de facturas
    migrations = [
        # Estado de la factura
        """ALTER TABLE tickets ADD COLUMN invoice_status TEXT DEFAULT 'pendiente'""",

        # Archivos adjuntos de factura (PDF)
        """ALTER TABLE tickets ADD COLUMN invoice_pdf_path TEXT""",

        # Archivos XML de factura
        """ALTER TABLE tickets ADD COLUMN invoice_xml_path TEXT""",

        # Metadatos de la factura
        """ALTER TABLE tickets ADD COLUMN invoice_metadata TEXT""",

        # Explicación del LLM cuando no se puede descargar
        """ALTER TABLE tickets ADD COLUMN invoice_failure_reason TEXT""",

        # Timestamp de última verificación
        """ALTER TABLE tickets ADD COLUMN invoice_last_check TEXT""",

        # UUID de factura real del SAT
        """ALTER TABLE tickets ADD COLUMN invoice_uuid TEXT""",

        # Estado de validación SAT
        """ALTER TABLE tickets ADD COLUMN invoice_sat_validation TEXT""",
    ]

    for migration in migrations:
        try:
            cursor.execute(migration)
            print(f"✅ {migration.split('ADD COLUMN')[1].split()[0] if 'ADD COLUMN' in migration else migration}")
        except sqlite3.Error as e:
            if "duplicate column name" in str(e).lower():
                print(f"⏭️ Columna ya existe: {migration.split('ADD COLUMN')[1].split()[0] if 'ADD COLUMN' in migration else 'N/A'}")
            else:
                print(f"❌ Error en migración: {e}")

    # Crear tabla de adjuntos de facturas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            file_type TEXT NOT NULL,  -- 'pdf', 'xml', 'image'
            file_path TEXT NOT NULL,
            file_size INTEGER,
            uploaded_at TEXT NOT NULL,
            is_valid BOOLEAN DEFAULT 0,
            validation_details TEXT,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id)
        )
    """)
    print("✅ Tabla invoice_attachments creada")

    # Índices para performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice_attachments_ticket_id ON invoice_attachments(ticket_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_invoice_status ON tickets(invoice_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_invoice_uuid ON tickets(invoice_uuid)")

    conn.commit()
    conn.close()

    print("✅ Migración completada exitosamente")

if __name__ == "__main__":
    migrate_invoice_system()