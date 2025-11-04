#!/usr/bin/env python3
"""
Agregar categorías automáticas a transacciones existentes basadas en descripción
"""
import sqlite3
import re

def categorize_transaction(description: str) -> str:
    """Categorizar transacción basada en la descripción"""
    desc_upper = description.upper()

    # Servicios Públicos
    if any(word in desc_upper for word in ['CFE', 'TELMEX', 'AGUA', 'GAS', 'LUZ', 'ELECTRICITY']):
        return 'Servicios Públicos'

    # Telecomunicaciones
    if any(word in desc_upper for word in ['TELCEL', 'MOVISTAR', 'SKY', 'INTERNET', 'DOMICILIACION']):
        return 'Telecomunicaciones'

    # Tecnología
    if any(word in desc_upper for word in ['OPENAI', 'CHATGPT', 'APPLE', 'MICROSOFT', 'GOOGLE', 'BUBBLE', 'PYTHAGORA']):
        return 'Tecnología'

    # Combustible
    if any(word in desc_upper for word in ['PEMEX', 'GASOLINA', 'COMBUSTIBLE', 'SHELL', 'BP']):
        return 'Combustible'

    # Alimentación
    if any(word in desc_upper for word in ['WALMART', 'SORIANA', 'COSTCO', 'STARBUCKS', 'MCDONALDS', 'RESTAURANT']):
        return 'Alimentación'

    # Oficina
    if any(word in desc_upper for word in ['OFFICE DEPOT', 'PAPELERIA', 'STAPLES', 'SUPPLIES']):
        return 'Oficina'

    # Transferencias
    if any(word in desc_upper for word in ['SPEI', 'TRANSFERENCIA', 'TRASPASO', 'DEPOSITO']):
        return 'Transferencias'

    # Servicios Bancarios
    if any(word in desc_upper for word in ['COMISION', 'IVA', 'INTERES', 'ISR', 'MANEJO']):
        return 'Servicios Bancarios'

    # Entretenimiento
    if any(word in desc_upper for word in ['NETFLIX', 'SPOTIFY', 'AMAZON', 'STRIPE']):
        return 'Entretenimiento'

    return 'Otros'

def improve_description(description: str) -> str:
    """Mejorar descripción para que sea más descriptiva"""
    desc = description.strip()

    # Mejorar descripciones genéricas
    if desc.upper() == 'DOMICILIACION':
        return 'Domiciliación de Servicios'

    if 'OPENAI' in desc.upper():
        return 'OPENAI ChatGPT Subscription'

    if 'APPLE.COM' in desc.upper():
        return 'Apple Services Billing'

    if 'OFFICE DEPOT' in desc.upper():
        return 'Office Depot Suministros'

    if 'DEPOSITO SPEI' in desc.upper():
        return 'Depósito SPEI'

    if 'TRASPASO SPEI' in desc.upper():
        return 'Traspaso SPEI'

    return desc

def main():
    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    print("🔄 Categorizando transacciones existentes...")

    # Obtener todas las transacciones
    cursor.execute("""
        SELECT id, description FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
    """)

    transactions = cursor.fetchall()
    print(f"📊 Encontradas {len(transactions)} transacciones para categorizar")

    updated_count = 0

    for txn_id, description in transactions:
        if description:
            # Mejorar descripción
            improved_desc = improve_description(description)

            # Categorizar
            category = categorize_transaction(description)

            # Actualizar en base de datos
            cursor.execute("""
                UPDATE bank_movements
                SET description = ?, category = ?
                WHERE id = ?
            """, (improved_desc, category, txn_id))

            updated_count += 1

            if updated_count <= 10:
                print(f"  {description[:50]}... → {category}")

    conn.commit()
    print(f"✅ Actualizadas {updated_count} transacciones con categorías")

    # Mostrar resumen de categorías
    cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9 AND category IS NOT NULL
        GROUP BY category
        ORDER BY count DESC
    """)

    categories = cursor.fetchall()
    print("\n📈 Resumen de categorías:")
    for category, count in categories:
        print(f"  {category}: {count} transacciones")

    conn.close()
    print("\n🎉 Categorización completada!")

if __name__ == "__main__":
    main()